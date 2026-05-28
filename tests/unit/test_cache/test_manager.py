"""缓存管理器单元测试。

测试 Redis / MinIO 编排逻辑、缓存命中/未命中、降级等场景。
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from datapilot_queryexec.cache.manager import CacheResult, ResultCacheManager
from datapilot_queryexec.cache.strategy import CachePolicy, CacheStrategy, CacheTier


class TestCacheResult:
    """CacheResult 数据类测试。"""

    def test_miss_result(self) -> None:
        """缓存未命中结果。"""
        result = CacheResult(hit=False, key="test_key", source="miss")
        assert result.hit is False
        assert result.data is None
        assert result.source == "miss"
        assert result.size_bytes == 0

    def test_hit_result(self) -> None:
        """缓存命中结果。"""
        result = CacheResult(
            hit=True,
            data=b'{"rows": []}',
            source="redis",
            key="test_key",
            size_bytes=11,
        )
        assert result.hit is True
        assert result.data == b'{"rows": []}'
        assert result.source == "redis"
        assert result.size_bytes == 11


class TestResultCacheManagerGet:
    """缓存管理器 GET 测试。"""

    @pytest.mark.asyncio
    async def test_get_redis_hit(self, sample_sql: str, tenant_id: str) -> None:
        """Redis 命中。"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b'{"data": [1]}'
        mock_minio = AsyncMock()

        manager = ResultCacheManager(
            strategy=CacheStrategy(),
            redis_cache=mock_redis,
            minio_cache=mock_minio,
        )

        result = await manager.get(sample_sql, tenant_id, "mysql")
        assert result.hit is True
        assert result.source == "redis"
        assert result.data == b'{"data": [1]}'
        # Redis 命中后不应查询 MinIO
        mock_minio.get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_redis_miss_minio_hit(self, sample_sql: str, tenant_id: str) -> None:
        """Redis 未命中，MinIO 命中。"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_minio = AsyncMock()
        mock_minio.get.return_value = b'{"data": [2]}'

        manager = ResultCacheManager(
            strategy=CacheStrategy(),
            redis_cache=mock_redis,
            minio_cache=mock_minio,
        )

        result = await manager.get(sample_sql, tenant_id, "mysql")
        assert result.hit is True
        assert result.source == "minio"
        assert result.data == b'{"data": [2]}'

    @pytest.mark.asyncio
    async def test_get_both_miss(self, sample_sql: str, tenant_id: str) -> None:
        """Redis 和 MinIO 均未命中。"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_minio = AsyncMock()
        mock_minio.get.return_value = None

        manager = ResultCacheManager(
            strategy=CacheStrategy(),
            redis_cache=mock_redis,
            minio_cache=mock_minio,
        )

        result = await manager.get(sample_sql, tenant_id, "mysql")
        assert result.hit is False
        assert result.source == "miss"
        assert result.data is None

    @pytest.mark.asyncio
    async def test_get_no_backends(self, sample_sql: str, tenant_id: str) -> None:
        """无可用后端时返回 miss。"""
        manager = ResultCacheManager(
            strategy=CacheStrategy(),
            redis_cache=None,
            minio_cache=None,
        )

        result = await manager.get(sample_sql, tenant_id, "mysql")
        assert result.hit is False
        assert result.source == "miss"

    @pytest.mark.asyncio
    async def test_get_only_redis(self, sample_sql: str, tenant_id: str) -> None:
        """只有 Redis 后端，命中。"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"cached_data"

        manager = ResultCacheManager(
            strategy=CacheStrategy(),
            redis_cache=mock_redis,
            minio_cache=None,
        )

        result = await manager.get(sample_sql, tenant_id, "mysql")
        assert result.hit is True
        assert result.source == "redis"

    @pytest.mark.asyncio
    async def test_get_only_minio(self, sample_sql: str, tenant_id: str) -> None:
        """只有 MinIO 后端，命中。"""
        mock_minio = AsyncMock()
        mock_minio.get.return_value = b"cached_data"

        manager = ResultCacheManager(
            strategy=CacheStrategy(),
            redis_cache=None,
            minio_cache=mock_minio,
        )

        result = await manager.get(sample_sql, tenant_id, "mysql")
        assert result.hit is True
        assert result.source == "minio"


class TestResultCacheManagerSet:
    """缓存管理器 SET 测试。"""

    @pytest.mark.asyncio
    async def test_set_small_data_to_redis(
        self, sample_sql: str, tenant_id: str, sample_data_small: bytes
    ) -> None:
        """小数据写入 Redis。"""
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        mock_minio = AsyncMock()

        manager = ResultCacheManager(
            strategy=CacheStrategy(),
            redis_cache=mock_redis,
            minio_cache=mock_minio,
        )

        result = await manager.set(sample_sql, tenant_id, "mysql", sample_data_small)
        assert result.source == "redis"
        assert result.size_bytes == len(sample_data_small)
        mock_redis.set.assert_awaited_once()
        mock_minio.set.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_set_large_data_to_minio(
        self, sample_sql: str, tenant_id: str, sample_data_large: bytes
    ) -> None:
        """大数据写入 MinIO。"""
        mock_redis = AsyncMock()
        mock_minio = AsyncMock()
        mock_minio.set.return_value = True

        manager = ResultCacheManager(
            strategy=CacheStrategy(),
            redis_cache=mock_redis,
            minio_cache=mock_minio,
        )

        result = await manager.set(sample_sql, tenant_id, "mysql", sample_data_large)
        assert result.source == "minio"
        assert result.size_bytes == len(sample_data_large)
        mock_minio.set.assert_awaited_once()
        mock_redis.set.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_set_with_custom_ttl(self, sample_sql: str, tenant_id: str) -> None:
        """自定义 TTL 传递给 Redis。"""
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        policy = CachePolicy(tier=CacheTier.REDIS, ttl_seconds=600)
        manager = ResultCacheManager(
            strategy=CacheStrategy(),
            redis_cache=mock_redis,
        )

        await manager.set(sample_sql, tenant_id, "mysql", b"data", policy=policy)
        call_args = mock_redis.set.call_args
        # 参数顺序: key, data, ttl_seconds
        assert call_args[0][2] == 600  # ttl_seconds

    @pytest.mark.asyncio
    async def test_set_redis_failure(
        self, sample_sql: str, tenant_id: str, sample_data_small: bytes
    ) -> None:
        """Redis 写入失败时返回 miss 结果。"""
        mock_redis = AsyncMock()
        mock_redis.set.return_value = False

        manager = ResultCacheManager(
            strategy=CacheStrategy(),
            redis_cache=mock_redis,
            minio_cache=None,
        )

        result = await manager.set(sample_sql, tenant_id, "mysql", sample_data_small)
        assert result.source == "miss"

    @pytest.mark.asyncio
    async def test_set_no_backends(
        self, sample_sql: str, tenant_id: str, sample_data_small: bytes
    ) -> None:
        """无可用后端时返回 miss。"""
        manager = ResultCacheManager(
            strategy=CacheStrategy(),
            redis_cache=None,
            minio_cache=None,
        )

        result = await manager.set(sample_sql, tenant_id, "mysql", sample_data_small)
        assert result.source == "miss"


class TestResultCacheManagerInvalidate:
    """缓存管理器 invalidate 测试。"""

    @pytest.mark.asyncio
    async def test_invalidate_both(self, sample_sql: str, tenant_id: str) -> None:
        """同时失效 Redis 和 MinIO。"""
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = True
        mock_minio = AsyncMock()
        mock_minio.delete.return_value = True

        manager = ResultCacheManager(
            strategy=CacheStrategy(),
            redis_cache=mock_redis,
            minio_cache=mock_minio,
        )

        result = await manager.invalidate(sample_sql, tenant_id, "mysql")
        assert result is True
        mock_redis.delete.assert_awaited_once()
        mock_minio.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalidate_redis_only(self, sample_sql: str, tenant_id: str) -> None:
        """只有 Redis 后端，失效成功。"""
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = True

        manager = ResultCacheManager(
            strategy=CacheStrategy(),
            redis_cache=mock_redis,
            minio_cache=None,
        )

        result = await manager.invalidate(sample_sql, tenant_id, "mysql")
        assert result is True

    @pytest.mark.asyncio
    async def test_invalidate_none_hit(self, sample_sql: str, tenant_id: str) -> None:
        """所有后端都未命中，返回 False。"""
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = False
        mock_minio = AsyncMock()
        mock_minio.delete.return_value = False

        manager = ResultCacheManager(
            strategy=CacheStrategy(),
            redis_cache=mock_redis,
            minio_cache=mock_minio,
        )

        result = await manager.invalidate(sample_sql, tenant_id, "mysql")
        assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_partial_hit(self, sample_sql: str, tenant_id: str) -> None:
        """一个后端命中即返回 True。"""
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = True
        mock_minio = AsyncMock()
        mock_minio.delete.return_value = False

        manager = ResultCacheManager(
            strategy=CacheStrategy(),
            redis_cache=mock_redis,
            minio_cache=mock_minio,
        )

        result = await manager.invalidate(sample_sql, tenant_id, "mysql")
        assert result is True


class TestResultCacheManagerClose:
    """缓存管理器关闭测试。"""

    @pytest.mark.asyncio
    async def test_close_both(self) -> None:
        """关闭所有后端。"""
        mock_redis = AsyncMock()
        mock_minio = AsyncMock()

        manager = ResultCacheManager(
            redis_cache=mock_redis,
            minio_cache=mock_minio,
        )

        await manager.close()
        mock_redis.close.assert_awaited_once()
        mock_minio.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_no_backends(self) -> None:
        """无后端时关闭不报错。"""
        manager = ResultCacheManager()
        await manager.close()  # 不应抛异常
