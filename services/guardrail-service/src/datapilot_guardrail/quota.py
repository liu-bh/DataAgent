"""查询配额管理器。

使用 Redis INCR + EXPIRE 实现滑动窗口计数，管理租户的查询频率配额。
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from datapilot_guardrail.models import QuotaConfig

logger = structlog.get_logger(__name__)


class QueryQuotaManager:
    """查询配额管理器。

    基于 Redis 实现租户级别的查询频率控制：
    - 每日查询次数上限
    - 每小时查询次数上限

    当 Redis 不可用时，降级放行并记录警告日志。
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        """初始化配额管理器。

        Args:
            redis_url: Redis 连接 URL。
        """
        self.redis_url = redis_url
        self._redis = None

    async def _get_redis(self):
        """延迟获取 Redis 连接。

        Returns:
            Redis 客户端实例，连接失败时返回 None。

        Raises:
            Exception: Redis 连接异常。
        """
        if self._redis is not None:
            return self._redis

        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
            # 测试连接
            await self._redis.ping()
            return self._redis
        except Exception as exc:
            logger.warning(
                "Redis 连接失败，配额检查将降级放行",
                redis_url=self.redis_url,
                error=str(exc),
            )
            self._redis = None
            return None

    async def check_quota(
        self,
        tenant_id: str,
        config: QuotaConfig | None = None,
    ) -> tuple[bool, int]:
        """检查租户查询配额。

        同时检查每日和每小时限制，取剩余配额的最小值。
        Redis 不可用时降级返回 (True, -1)。

        Args:
            tenant_id: 租户 ID。
            config: 配额配置，None 时使用默认值。

        Returns:
            (是否通过, 剩余配额)。剩余配额 -1 表示降级放行。
        """
        if config is None:
            config = QuotaConfig()

        try:
            redis_client = await self._get_redis()
            if redis_client is None:
                # Redis 不可用，降级放行
                return True, -1

            now = datetime.now(tz=UTC)

            # 检查每日配额
            daily_remaining = await self._check_window(
                redis_client,
                tenant_id=tenant_id,
                window_type="daily",
                window_key=f"quota:{tenant_id}:daily:{now.strftime('%Y-%m-%d')}",
                limit=config.daily_limit,
                ttl_seconds=86400,  # 24 小时
            )

            # 检查每小时配额
            hourly_remaining = await self._check_window(
                redis_client,
                tenant_id=tenant_id,
                window_type="hourly",
                window_key=f"quota:{tenant_id}:hourly:{now.strftime('%Y-%m-%d-%H')}",
                limit=config.hourly_limit,
                ttl_seconds=3600,  # 1 小时
            )

            passed = daily_remaining > 0 and hourly_remaining > 0
            remaining = min(daily_remaining, hourly_remaining)

            if not passed:
                logger.info(
                    "租户配额已耗尽",
                    tenant_id=tenant_id,
                    daily_remaining=daily_remaining,
                    hourly_remaining=hourly_remaining,
                )

            return passed, remaining

        except Exception as exc:
            logger.warning(
                "配额检查异常，降级放行",
                tenant_id=tenant_id,
                error=str(exc),
            )
            return True, -1

    @staticmethod
    async def _check_window(
        redis_client,
        tenant_id: str,
        window_type: str,
        window_key: str,
        limit: int,
        ttl_seconds: int,
    ) -> int:
        """检查单个时间窗口的配额。

        使用 Redis INCR + EXPIRE 实现计数器。

        Args:
            redis_client: Redis 客户端。
            tenant_id: 租户 ID（仅用于日志）。
            window_type: 窗口类型描述（"daily" 或 "hourly"）。
            window_key: Redis key。
            limit: 窗口内允许的最大次数。
            ttl_seconds: key 过期时间（秒）。

        Returns:
            剩余配额。
        """
        pipe = redis_client.pipeline(transaction=True)
        pipe.incr(window_key)
        pipe.expire(window_key, ttl_seconds, nx=True)
        results = await pipe.execute()

        current_count = results[0]
        remaining = max(0, limit - current_count)

        logger.debug(
            "配额窗口检查",
            tenant_id=tenant_id,
            window_type=window_type,
            current_count=current_count,
            limit=limit,
            remaining=remaining,
        )

        return remaining
