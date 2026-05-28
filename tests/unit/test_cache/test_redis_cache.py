"""Redis 缓存单元测试。

使用 mock 测试 Redis 缓存的各种操作和降级行为。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datapilot_queryexec.cache.redis_cache import RedisResultCache


class TestRedisResultCacheInit:
    """初始化测试。"""

    def test_default_url(self) -> None:
        """默认 Redis URL。"""
        cache = RedisResultCache()
        assert cache._redis_url == "redis://localhost:6379/0"
        assert cache._client is None
        assert cache._pool is None

    def test_custom_url(self) -> None:
        """自定义 Redis URL。"""
        cache = RedisResultCache(redis_url="redis://custom:6380/1")
        assert cache._redis_url == "redis://custom:6380/1"


class TestRedisResultCacheGet:
    """Redis GET 操作测试。"""

    @pytest.mark.asyncio
    async def test_get_hit(self) -> None:
        """缓存命中。"""
        cache = RedisResultCache()
        mock_client = AsyncMock()
        mock_client.get.return_value = b'{"data": [1, 2, 3]}'
        cache._client = mock_client

        result = await cache.get("test_key")
        assert result == b'{"data": [1, 2, 3]}'
        mock_client.get.assert_awaited_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_miss(self) -> None:
        """缓存未命中（key 不存在）。"""
        cache = RedisResultCache()
        mock_client = AsyncMock()
        mock_client.get.return_value = None
        cache._client = mock_client

        result = await cache.get("nonexistent_key")
        assert result is None
        mock_client.get.assert_awaited_once_with("nonexistent_key")

    @pytest.mark.asyncio
    async def test_get_connection_failure_degradation(self) -> None:
        """连接失败时降级返回 None。"""
        cache = RedisResultCache(redis_url="redis://invalid:9999/0")
        # 不设置 client，_ensure_client 将尝试连接并失败
        result = await cache.get("any_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_runtime_error_degradation(self) -> None:
        """运行时异常时降级返回 None。"""
        cache = RedisResultCache()
        mock_client = AsyncMock()
        mock_client.get.side_effect = ConnectionError("连接已断开")
        cache._client = mock_client

        result = await cache.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_none_client(self) -> None:
        """client 为 None 时返回 None（_ensure_client 模拟失败）。"""
        cache = RedisResultCache()

        async def mock_ensure():
            return None

        cache._ensure_client = mock_ensure
        result = await cache.get("any_key")
        assert result is None


class TestRedisResultCacheSet:
    """Redis SET 操作测试。"""

    @pytest.mark.asyncio
    async def test_set_success(self) -> None:
        """写入成功返回 True。"""
        cache = RedisResultCache()
        mock_client = AsyncMock()
        mock_client.set.return_value = True
        cache._client = mock_client

        result = await cache.set("test_key", b"hello", ttl_seconds=60)
        assert result is True
        mock_client.set.assert_awaited_once_with("test_key", b"hello", ex=60)

    @pytest.mark.asyncio
    async def test_set_default_ttl(self) -> None:
        """默认 TTL 为 300 秒。"""
        cache = RedisResultCache()
        mock_client = AsyncMock()
        cache._client = mock_client

        await cache.set("test_key", b"data")
        mock_client.set.assert_awaited_once_with("test_key", b"data", ex=300)

    @pytest.mark.asyncio
    async def test_set_connection_failure(self) -> None:
        """连接失败时返回 False。"""
        cache = RedisResultCache(redis_url="redis://invalid:9999/0")
        result = await cache.set("any_key", b"data")
        assert result is False

    @pytest.mark.asyncio
    async def test_set_runtime_error(self) -> None:
        """运行时异常时返回 False。"""
        cache = RedisResultCache()
        mock_client = AsyncMock()
        mock_client.set.side_effect = RuntimeError("写入超时")
        cache._client = mock_client

        result = await cache.set("test_key", b"data")
        assert result is False


class TestRedisResultCacheDelete:
    """Redis DELETE 操作测试。"""

    @pytest.mark.asyncio
    async def test_delete_success(self) -> None:
        """删除成功返回 True。"""
        cache = RedisResultCache()
        mock_client = AsyncMock()
        mock_client.delete.return_value = 1
        cache._client = mock_client

        result = await cache.delete("test_key")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_not_exists(self) -> None:
        """删除不存在的 key 返回 False。"""
        cache = RedisResultCache()
        mock_client = AsyncMock()
        mock_client.delete.return_value = 0
        cache._client = mock_client

        result = await cache.delete("nonexistent_key")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_connection_failure(self) -> None:
        """连接失败时返回 False。"""
        cache = RedisResultCache(redis_url="redis://invalid:9999/0")
        result = await cache.delete("any_key")
        assert result is False


class TestRedisResultCacheExists:
    """Redis EXISTS 操作测试。"""

    @pytest.mark.asyncio
    async def test_exists_true(self) -> None:
        """key 存在返回 True。"""
        cache = RedisResultCache()
        mock_client = AsyncMock()
        mock_client.exists.return_value = 1
        cache._client = mock_client

        result = await cache.exists("test_key")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self) -> None:
        """key 不存在返回 False。"""
        cache = RedisResultCache()
        mock_client = AsyncMock()
        mock_client.exists.return_value = 0
        cache._client = mock_client

        result = await cache.exists("nonexistent_key")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_connection_failure(self) -> None:
        """连接失败时返回 False。"""
        cache = RedisResultCache(redis_url="redis://invalid:9999/0")
        result = await cache.exists("any_key")
        assert result is False


class TestRedisResultCacheGetTtl:
    """Redis TTL 操作测试。"""

    @pytest.mark.asyncio
    async def test_get_ttl_positive(self) -> None:
        """返回正数 TTL。"""
        cache = RedisResultCache()
        mock_client = AsyncMock()
        mock_client.ttl.return_value = 120
        cache._client = mock_client

        result = await cache.get_ttl("test_key")
        assert result == 120

    @pytest.mark.asyncio
    async def test_get_ttl_not_exists(self) -> None:
        """key 不存在返回 -2。"""
        cache = RedisResultCache()
        mock_client = AsyncMock()
        mock_client.ttl.return_value = -2
        cache._client = mock_client

        result = await cache.get_ttl("nonexistent_key")
        assert result == -2

    @pytest.mark.asyncio
    async def test_get_ttl_no_expiry(self) -> None:
        """无过期时间返回 -1。"""
        cache = RedisResultCache()
        mock_client = AsyncMock()
        mock_client.ttl.return_value = -1
        cache._client = mock_client

        result = await cache.get_ttl("test_key")
        assert result == -1

    @pytest.mark.asyncio
    async def test_get_ttl_connection_failure(self) -> None:
        """连接失败时返回 -3。"""
        cache = RedisResultCache(redis_url="redis://invalid:9999/0")
        result = await cache.get_ttl("any_key")
        assert result == -3


class TestRedisResultCacheClose:
    """关闭连接测试。"""

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        """正常关闭连接。"""
        cache = RedisResultCache()
        mock_client = AsyncMock()
        cache._client = mock_client

        await cache.close()
        mock_client.aclose.assert_awaited_once()
        assert cache._client is None
        assert cache._pool is None

    @pytest.mark.asyncio
    async def test_close_no_client(self) -> None:
        """client 为 None 时关闭不报错。"""
        cache = RedisResultCache()
        cache._client = None

        await cache.close()  # 不应抛异常
        assert cache._client is None

    @pytest.mark.asyncio
    async def test_close_with_error(self) -> None:
        """关闭时异常不抛出。"""
        cache = RedisResultCache()
        mock_client = AsyncMock()
        mock_client.aclose.side_effect = RuntimeError("连接已断开")
        cache._client = mock_client

        await cache.close()  # 不应抛异常
        assert cache._client is None
