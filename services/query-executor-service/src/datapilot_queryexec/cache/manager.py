"""缓存管理器。

统一调度 Redis 和 MinIO 两个缓存后端，对外提供 get / set / invalidate 接口。
根据数据大小自动选择缓存层级：小结果走 Redis，大结果走 MinIO。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from .strategy import CachePolicy, CacheStrategy, CacheTier

if TYPE_CHECKING:
    from .minio_cache import MinIOResultCache
    from .redis_cache import RedisResultCache

logger = structlog.get_logger(__name__)


@dataclass
class CacheResult:
    """缓存操作结果。

    Attributes:
        hit: 是否命中缓存。
        data: 缓存数据（命中时非空）。
        source: 数据来源，取值 ``"redis"`` / ``"minio"`` / ``"miss"``。
        key: 使用的缓存 key。
        size_bytes: 数据大小（字节）。
    """

    hit: bool
    data: bytes | None = None
    source: str = ""
    key: str = ""
    size_bytes: int = 0


class ResultCacheManager:
    """统一缓存管理器。

    编排 Redis 和 MinIO 两个后端，对外暴露简洁的 get / set / invalidate 接口。
    查询时先查 Redis，miss 后查 MinIO；写入时根据数据大小自动选择后端。

    Args:
        strategy: 缓存策略决策器，为空时使用默认策略。
        redis_cache: Redis 缓存客户端，为空时 Redis 层不可用。
        minio_cache: MinIO 缓存客户端，为空时 MinIO 层不可用。
    """

    def __init__(
        self,
        strategy: CacheStrategy | None = None,
        redis_cache: RedisResultCache | None = None,
        minio_cache: MinIOResultCache | None = None,
    ) -> None:
        self._strategy = strategy or CacheStrategy()
        self._redis_cache = redis_cache
        self._minio_cache = minio_cache

    async def get(
        self,
        sql: str,
        tenant_id: str,
        dialect: str,
        policy: CachePolicy | None = None,
    ) -> CacheResult:
        """查询缓存。

        生成缓存 key 后，先查 Redis，若 miss 再查 MinIO。
        若两个后端均不可用或均未命中，返回 miss 结果。

        Args:
            sql: SQL 语句。
            tenant_id: 租户 ID。
            dialect: SQL 方言。
            policy: 缓存策略，为空时使用默认策略。

        Returns:
            CacheResult 实例，包含命中状态和数据。
        """
        key = self._strategy.build_cache_key(sql, tenant_id, dialect)

        # 1. 先查 Redis
        if self._redis_cache is not None:
            redis_data = await self._redis_cache.get(key)
            if redis_data is not None:
                logger.info(
                    "缓存命中（Redis）",
                    key=key,
                    tenant_id=tenant_id,
                    size_bytes=len(redis_data),
                )
                return CacheResult(
                    hit=True,
                    data=redis_data,
                    source="redis",
                    key=key,
                    size_bytes=len(redis_data),
                )

        # 2. Redis miss，查 MinIO
        if self._minio_cache is not None:
            minio_data = await self._minio_cache.get(key)
            if minio_data is not None:
                logger.info(
                    "缓存命中（MinIO）",
                    key=key,
                    tenant_id=tenant_id,
                    size_bytes=len(minio_data),
                )
                return CacheResult(
                    hit=True,
                    data=minio_data,
                    source="minio",
                    key=key,
                    size_bytes=len(minio_data),
                )

        logger.debug("缓存未命中", key=key, tenant_id=tenant_id)
        return CacheResult(hit=False, key=key, source="miss")

    async def set(
        self,
        sql: str,
        tenant_id: str,
        dialect: str,
        data: bytes,
        policy: CachePolicy | None = None,
    ) -> CacheResult:
        """写入缓存。

        根据数据大小自动选择 Redis 或 MinIO 作为缓存后端。

        Args:
            sql: SQL 语句。
            tenant_id: 租户 ID。
            dialect: SQL 方言。
            data: 要缓存的数据。
            policy: 缓存策略，为空时使用默认策略。

        Returns:
            CacheResult 实例，包含写入结果信息。
        """
        key = self._strategy.build_cache_key(sql, tenant_id, dialect)
        data_size = len(data)
        tier = self._strategy.determine_tier(data_size, policy)
        effective_policy = policy or self._strategy._default_policy

        if tier == CacheTier.REDIS and self._redis_cache is not None:
            success = await self._redis_cache.set(key, data, effective_policy.ttl_seconds)
            if success:
                logger.info(
                    "缓存写入成功（Redis）",
                    key=key,
                    tenant_id=tenant_id,
                    size_bytes=data_size,
                )
                return CacheResult(
                    hit=False,
                    data=data,
                    source="redis",
                    key=key,
                    size_bytes=data_size,
                )
            logger.warning("Redis 写入失败", key=key)
        elif tier == CacheTier.MINIO and self._minio_cache is not None:
            success = await self._minio_cache.set(key, data)
            if success:
                logger.info(
                    "缓存写入成功（MinIO）",
                    key=key,
                    tenant_id=tenant_id,
                    size_bytes=data_size,
                )
                return CacheResult(
                    hit=False,
                    data=data,
                    source="minio",
                    key=key,
                    size_bytes=data_size,
                )
            logger.warning("MinIO 写入失败", key=key)
        else:
            logger.warning(
                "无可用缓存后端",
                key=key,
                tier=tier,
                has_redis=self._redis_cache is not None,
                has_minio=self._minio_cache is not None,
            )

        return CacheResult(hit=False, key=key, source="miss", size_bytes=data_size)

    async def invalidate(
        self,
        sql: str,
        tenant_id: str,
        dialect: str,
    ) -> bool:
        """使指定查询的缓存失效。

        同时尝试从 Redis 和 MinIO 中删除缓存 key，任一成功即返回 True。

        Args:
            sql: SQL 语句。
            tenant_id: 租户 ID。
            dialect: SQL 方言。

        Returns:
            至少一个后端删除成功返回 True，否则返回 False。
        """
        key = self._strategy.build_cache_key(sql, tenant_id, dialect)
        any_success = False

        if self._redis_cache is not None:
            redis_ok = await self._redis_cache.delete(key)
            if redis_ok:
                any_success = True
                logger.info("Redis 缓存已失效", key=key, tenant_id=tenant_id)

        if self._minio_cache is not None:
            minio_ok = await self._minio_cache.delete(key)
            if minio_ok:
                any_success = True
                logger.info("MinIO 缓存已失效", key=key, tenant_id=tenant_id)

        if not any_success:
            logger.debug("缓存失效操作未命中任何后端", key=key)

        return any_success

    async def close(self) -> None:
        """关闭所有缓存客户端连接。"""
        if self._redis_cache is not None:
            await self._redis_cache.close()
        if self._minio_cache is not None:
            await self._minio_cache.close()
        logger.info("缓存管理器已关闭")
