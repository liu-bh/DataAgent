"""分级缓存策略。

根据查询结果大小自动选择 Redis（<1MB）或 MinIO（>=1MB）作为缓存后端，
并提供基于 SQL + tenant + dialect 的缓存 key 生成。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum

import structlog


class CacheTier(StrEnum):
    """缓存层级枚举。"""

    NONE = "none"  # 不缓存
    REDIS = "redis"  # 小结果缓存到 Redis（<1MB）
    MINIO = "minio"  # 大结果缓存到 MinIO（>=1MB）


logger = structlog.get_logger(__name__)


@dataclass
class CachePolicy:
    """缓存策略配置。

    Attributes:
        tier: 强制指定的缓存层级，默认 NONE 表示由策略自动决定。
        ttl_seconds: 缓存过期时间（秒），默认 300 秒（5 分钟）。
        max_size_bytes: Redis / MinIO 分级阈值（字节），默认 1MB。
    """

    tier: CacheTier = CacheTier.NONE
    ttl_seconds: int = 300
    max_size_bytes: int = 1048576  # 1MB


class CacheStrategy:
    """缓存策略决策器。

    根据数据大小和缓存策略配置，决定使用哪个缓存层级，
    并生成统一的缓存 key。
    """

    def __init__(self, default_policy: CachePolicy | None = None) -> None:
        """初始化缓存策略。

        Args:
            default_policy: 默认缓存策略，为空时使用 CachePolicy 默认值。
        """
        self._default_policy = default_policy or CachePolicy()

    def determine_tier(
        self,
        data_size_bytes: int,
        policy: CachePolicy | None = None,
    ) -> CacheTier:
        """根据数据大小决定缓存层级。

        优先使用 policy 中强制指定的 tier；若为 NONE 则按大小自动选择：
        - 小于 max_size_bytes 使用 Redis
        - 大于等于 max_size_bytes 使用 MinIO

        Args:
            data_size_bytes: 数据大小（字节）。
            policy: 缓存策略，为空时使用默认策略。

        Returns:
            选中的缓存层级。
        """
        effective_policy = policy or self._default_policy

        # 如果策略已强制指定非 NONE 的 tier，直接使用
        if effective_policy.tier != CacheTier.NONE:
            logger.debug(
                "缓存层级由策略强制指定",
                tier=effective_policy.tier,
                data_size_bytes=data_size_bytes,
            )
            return effective_policy.tier

        # 按大小自动选择
        if data_size_bytes < effective_policy.max_size_bytes:
            logger.debug(
                "数据量较小，选择 Redis 缓存",
                data_size_bytes=data_size_bytes,
                threshold=effective_policy.max_size_bytes,
            )
            return CacheTier.REDIS
        else:
            logger.debug(
                "数据量较大，选择 MinIO 缓存",
                data_size_bytes=data_size_bytes,
                threshold=effective_policy.max_size_bytes,
            )
            return CacheTier.MINIO

    def build_cache_key(self, sql: str, tenant_id: str, dialect: str) -> str:
        """生成缓存 key。

        使用 SQL 内容 + tenant_id + dialect 的 MD5 哈希作为唯一标识，
        确保不同租户、不同 SQL、不同方言的查询互不干扰。

        Args:
            sql: SQL 语句。
            tenant_id: 租户 ID。
            dialect: SQL 方言（如 mysql、postgresql、clickhouse）。

        Returns:
            格式为 ``query_cache:<md5hex>`` 的缓存 key。
        """
        raw = f"{sql}:{tenant_id}:{dialect}"
        md5_hex = hashlib.md5(raw.encode()).hexdigest()
        key = f"query_cache:{md5_hex}"
        logger.debug("生成缓存 key", key=key, tenant_id=tenant_id, dialect=dialect)
        return key
