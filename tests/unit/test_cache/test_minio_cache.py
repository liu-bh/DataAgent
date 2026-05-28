"""MinIO 缓存单元测试。

使用 mock 测试 MinIO 缓存的各种操作和降级行为。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest

from datapilot_queryexec.cache.minio_cache import MinIOResultCache


class TestMinIOResultCacheInit:
    """初始化测试。"""

    def test_default_config(self) -> None:
        """验证默认配置。"""
        cache = MinIOResultCache()
        assert cache._endpoint == "localhost:9000"
        assert cache._access_key == "minioadmin"
        assert cache._secret_key == "minioadmin"
        assert cache._bucket_name == "query-cache"
        assert cache._secure is False
        assert cache._client is None

    def test_custom_config(self) -> None:
        """验证自定义配置。"""
        cache = MinIOResultCache(
            endpoint="minio.example.com:9000",
            access_key="custom-key",
            secret_key="custom-secret",
            bucket_name="custom-bucket",
            secure=True,
        )
        assert cache._endpoint == "minio.example.com:9000"
        assert cache._access_key == "custom-key"
        assert cache._secret_key == "custom-secret"
        assert cache._bucket_name == "custom-bucket"
        assert cache._secure is True


class TestMinIOResultCacheEnsureBucket:
    """ensure_bucket 测试。"""

    @pytest.mark.asyncio
    async def test_ensure_bucket_creates_new(self) -> None:
        """存储桶不存在时创建。"""
        cache = MinIOResultCache()
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = False
        cache._client = mock_client

        await cache.ensure_bucket()
        mock_client.bucket_exists.assert_called_once_with("query-cache")
        mock_client.make_bucket.assert_called_once_with("query-cache")

    @pytest.mark.asyncio
    async def test_ensure_bucket_already_exists(self) -> None:
        """存储桶已存在时不重复创建。"""
        cache = MinIOResultCache()
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        cache._client = mock_client

        await cache.ensure_bucket()
        mock_client.bucket_exists.assert_called_once_with("query-cache")
        mock_client.make_bucket.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_bucket_connection_failure(self) -> None:
        """连接失败时不抛异常。"""
        cache = MinIOResultCache(endpoint="invalid:9999")
        # _ensure_client 会失败，_client 为 None
        await cache.ensure_bucket()  # 不应抛异常


class TestMinIOResultCacheGet:
    """MinIO GET 操作测试。"""

    @pytest.mark.asyncio
    async def test_get_hit(self) -> None:
        """缓存命中。"""
        cache = MinIOResultCache()
        expected_data = b'{"data": [1, 2, 3]}'
        mock_response = MagicMock()
        mock_response.read.return_value = expected_data
        mock_response.close = MagicMock()
        mock_response.release_conn = MagicMock()

        mock_client = MagicMock()
        mock_client.get_object.return_value = mock_response
        cache._client = mock_client

        result = await cache.get("test_key")
        assert result == expected_data
        mock_client.get_object.assert_called_once_with("query-cache", "test_key")
        mock_response.close.assert_called_once()
        mock_response.release_conn.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_miss(self) -> None:
        """缓存未命中（对象不存在）。"""
        cache = MinIOResultCache()
        mock_client = MagicMock()
        mock_client.get_object.side_effect = Exception("NoSuchKey")
        cache._client = mock_client

        result = await cache.get("nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_connection_failure(self) -> None:
        """连接失败时降级返回 None。"""
        cache = MinIOResultCache(endpoint="invalid:9999")
        result = await cache.get("any_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_runtime_error(self) -> None:
        """运行时异常时降级返回 None。"""
        cache = MinIOResultCache()
        mock_client = MagicMock()
        mock_client.get_object.side_effect = ConnectionError("连接超时")
        cache._client = mock_client

        result = await cache.get("test_key")
        assert result is None


class TestMinIOResultCacheSet:
    """MinIO SET 操作测试。"""

    @pytest.mark.asyncio
    async def test_set_success(self) -> None:
        """写入成功返回 True。"""
        cache = MinIOResultCache()
        mock_client = MagicMock()
        cache._client = mock_client

        result = await cache.set("test_key", b"hello world")
        assert result is True
        mock_client.put_object.assert_called_once()
        call_args = mock_client.put_object.call_args
        assert call_args.kwargs["bucket_name"] == "query-cache"
        assert call_args.kwargs["object_name"] == "test_key"
        assert call_args.kwargs["length"] == 11

    @pytest.mark.asyncio
    async def test_set_large_data(self) -> None:
        """写入大数据。"""
        cache = MinIOResultCache()
        mock_client = MagicMock()
        cache._client = mock_client

        large_data = b"x" * (5 * 1024 * 1024)  # 5MB
        result = await cache.set("large_key", large_data)
        assert result is True
        call_args = mock_client.put_object.call_args
        assert call_args.kwargs["length"] == 5 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_set_connection_failure(self) -> None:
        """连接失败时返回 False。"""
        cache = MinIOResultCache(endpoint="invalid:9999")
        result = await cache.set("any_key", b"data")
        assert result is False

    @pytest.mark.asyncio
    async def test_set_runtime_error(self) -> None:
        """运行时异常时返回 False。"""
        cache = MinIOResultCache()
        mock_client = MagicMock()
        mock_client.put_object.side_effect = RuntimeError("磁盘满")
        cache._client = mock_client

        result = await cache.set("test_key", b"data")
        assert result is False


class TestMinIOResultCacheDelete:
    """MinIO DELETE 操作测试。"""

    @pytest.mark.asyncio
    async def test_delete_success(self) -> None:
        """删除成功返回 True。"""
        cache = MinIOResultCache()
        mock_client = MagicMock()
        cache._client = mock_client

        result = await cache.delete("test_key")
        assert result is True
        mock_client.remove_object.assert_called_once_with("query-cache", "test_key")

    @pytest.mark.asyncio
    async def test_delete_connection_failure(self) -> None:
        """连接失败时返回 False。"""
        cache = MinIOResultCache(endpoint="invalid:9999")
        result = await cache.delete("any_key")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_not_exists(self) -> None:
        """删除不存在的对象不报错（MinIO 不抛异常）。"""
        cache = MinIOResultCache()
        mock_client = MagicMock()
        # MinIO remove_object 对不存在的对象不抛异常
        cache._client = mock_client

        result = await cache.delete("nonexistent_key")
        assert result is True


class TestMinIOResultCacheExists:
    """MinIO EXISTS 操作测试。"""

    @pytest.mark.asyncio
    async def test_exists_true(self) -> None:
        """对象存在返回 True。"""
        cache = MinIOResultCache()
        mock_client = MagicMock()
        cache._client = mock_client

        result = await cache.exists("test_key")
        assert result is True
        mock_client.stat_object.assert_called_once_with("query-cache", "test_key")

    @pytest.mark.asyncio
    async def test_exists_false(self) -> None:
        """对象不存在返回 False。"""
        cache = MinIOResultCache()
        mock_client = MagicMock()
        mock_client.stat_object.side_effect = Exception("NoSuchKey")
        cache._client = mock_client

        result = await cache.exists("nonexistent_key")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_connection_failure(self) -> None:
        """连接失败时返回 False。"""
        cache = MinIOResultCache(endpoint="invalid:9999")
        result = await cache.exists("any_key")
        assert result is False


class TestMinIOResultCacheClose:
    """关闭连接测试。"""

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        """正常关闭。"""
        cache = MinIOResultCache()
        mock_client = MagicMock()
        cache._client = mock_client

        await cache.close()
        assert cache._client is None

    @pytest.mark.asyncio
    async def test_close_no_client(self) -> None:
        """client 为 None 时关闭不报错。"""
        cache = MinIOResultCache()
        cache._client = None

        await cache.close()  # 不应抛异常
        assert cache._client is None
