"""datapilot_guardrail.quota 单元测试。

覆盖 QueryQuotaManager 的配额检查逻辑，包括 Redis 不可用时的降级。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from datapilot_guardrail.models import QuotaConfig
from datapilot_guardrail.quota import QueryQuotaManager


class TestQueryQuotaManagerInit:
    """QueryQuotaManager 初始化测试。"""

    def test_default_redis_url(self) -> None:
        """默认 Redis URL。"""
        manager = QueryQuotaManager()
        assert manager.redis_url == "redis://localhost:6379/0"

    def test_custom_redis_url(self) -> None:
        """自定义 Redis URL。"""
        manager = QueryQuotaManager(redis_url="redis://custom-host:6380/1")
        assert manager.redis_url == "redis://custom-host:6380/1"


class TestCheckQuotaRedisUnavailable:
    """Redis 不可用时的降级行为。"""

    @pytest.mark.asyncio
    async def test_redis_connection_failure_degrades(self) -> None:
        """Redis 连接失败时，降级返回 (True, -1)。"""
        manager = QueryQuotaManager(redis_url="redis://nonexistent-host:6379/0")

        passed, remaining = await manager.check_quota(tenant_id="test-tenant")

        assert passed is True
        assert remaining == -1

    @pytest.mark.asyncio
    async def test_redis_connection_failure_with_custom_config(self) -> None:
        """Redis 连接失败时，即使传入自定义配置也降级放行。"""
        manager = QueryQuotaManager(redis_url="redis://nonexistent-host:6379/0")
        config = QuotaConfig(daily_limit=10, hourly_limit=5)

        passed, remaining = await manager.check_quota(
            tenant_id="test-tenant", config=config
        )

        assert passed is True
        assert remaining == -1


class TestCheckQuotaWithMockRedis:
    """使用 Mock Redis 测试配额检查逻辑。"""

    @pytest.fixture()
    def mock_redis(self) -> AsyncMock:
        """创建 Mock Redis 客户端。"""
        redis_mock = AsyncMock()
        redis_mock.ping = AsyncMock(return_value=True)
        # pipeline 返回 pipeline mock
        pipeline_mock = MagicMock()
        pipeline_mock.execute = AsyncMock(return_value=[5, True])  # count=5, expire=True
        redis_mock.pipeline = MagicMock(return_value=pipeline_mock)
        return redis_mock

    @pytest.mark.asyncio
    async def test_quota_within_limit(self, mock_redis: AsyncMock) -> None:
        """配额未耗尽时返回 passed=True。"""
        manager = QueryQuotaManager()
        manager._redis = mock_redis

        passed, remaining = await manager.check_quota(
            tenant_id="test-tenant",
            config=QuotaConfig(daily_limit=1000, hourly_limit=200),
        )

        assert passed is True
        assert remaining > 0

    @pytest.mark.asyncio
    async def test_quota_exhausted_daily(self) -> None:
        """每日配额耗尽时返回 passed=False。"""
        # 模拟 daily count = 1001 (超过 limit 1000)
        pipeline_mock_daily = MagicMock()
        pipeline_mock_daily.execute = AsyncMock(return_value=[1001, True])

        pipeline_mock_hourly = MagicMock()
        pipeline_mock_hourly.execute = AsyncMock(return_value=[50, True])

        redis_mock = AsyncMock()
        redis_mock.ping = AsyncMock(return_value=True)
        redis_mock.pipeline = MagicMock(
            side_effect=[pipeline_mock_daily, pipeline_mock_hourly]
        )

        manager = QueryQuotaManager()
        manager._redis = redis_mock

        passed, remaining = await manager.check_quota(
            tenant_id="test-tenant",
            config=QuotaConfig(daily_limit=1000, hourly_limit=200),
        )

        assert passed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_quota_exhausted_hourly(self) -> None:
        """每小时配额耗尽时返回 passed=False。"""
        pipeline_mock_daily = MagicMock()
        pipeline_mock_daily.execute = AsyncMock(return_value=[100, True])

        pipeline_mock_hourly = MagicMock()
        pipeline_mock_hourly.execute = AsyncMock(return_value=[201, True])

        redis_mock = AsyncMock()
        redis_mock.ping = AsyncMock(return_value=True)
        redis_mock.pipeline = MagicMock(
            side_effect=[pipeline_mock_daily, pipeline_mock_hourly]
        )

        manager = QueryQuotaManager()
        manager._redis = redis_mock

        passed, remaining = await manager.check_quota(
            tenant_id="test-tenant",
            config=QuotaConfig(daily_limit=1000, hourly_limit=200),
        )

        assert passed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_default_config_used_when_none(self, mock_redis: AsyncMock) -> None:
        """未传入 config 时使用默认配置。"""
        manager = QueryQuotaManager()
        manager._redis = mock_redis

        passed, remaining = await manager.check_quota(tenant_id="test-tenant")

        assert passed is True
        assert remaining > 0


class TestCheckWindow:
    """_check_window 静态方法测试。"""

    @pytest.mark.asyncio
    async def test_remaining_calculation(self) -> None:
        """正确计算剩余配额。"""
        mock_redis = AsyncMock()
        pipeline_mock = MagicMock()
        pipeline_mock.execute = AsyncMock(return_value=[42, True])  # count=42
        mock_redis.pipeline = MagicMock(return_value=pipeline_mock)

        remaining = await QueryQuotaManager._check_window(
            redis_client=mock_redis,
            tenant_id="test",
            window_type="daily",
            window_key="quota:test:daily:2024-01-01",
            limit=100,
            ttl_seconds=86400,
        )

        assert remaining == 58  # 100 - 42

    @pytest.mark.asyncio
    async def test_remaining_zero_when_exhausted(self) -> None:
        """配额耗尽时剩余为 0。"""
        mock_redis = AsyncMock()
        pipeline_mock = MagicMock()
        pipeline_mock.execute = AsyncMock(return_value=[100, True])  # count=100
        mock_redis.pipeline = MagicMock(return_value=pipeline_mock)

        remaining = await QueryQuotaManager._check_window(
            redis_client=mock_redis,
            tenant_id="test",
            window_type="daily",
            window_key="quota:test:daily:2024-01-01",
            limit=100,
            ttl_seconds=86400,
        )

        assert remaining == 0

    @pytest.mark.asyncio
    async def test_remaining_non_negative(self) -> None:
        """剩余配额不低于 0。"""
        mock_redis = AsyncMock()
        pipeline_mock = MagicMock()
        pipeline_mock.execute = AsyncMock(return_value=[150, True])  # count=150 > limit=100
        mock_redis.pipeline = MagicMock(return_value=pipeline_mock)

        remaining = await QueryQuotaManager._check_window(
            redis_client=mock_redis,
            tenant_id="test",
            window_type="daily",
            window_key="quota:test:daily:2024-01-01",
            limit=100,
            ttl_seconds=86400,
        )

        assert remaining == 0  # max(0, 100-150) = 0


class TestGetRedisConnection:
    """Redis 连接获取测试。"""

    @pytest.mark.asyncio
    async def test_lazy_connection(self) -> None:
        """首次调用时创建连接。"""
        manager = QueryQuotaManager(redis_url="redis://nonexistent:6379/0")
        # 清除缓存
        manager._redis = None

        # 连接失败但不会抛出异常
        result = await manager._get_redis()
        assert result is None

    @pytest.mark.asyncio
    async def test_cached_connection(self) -> None:
        """已有连接时直接返回。"""
        mock_redis = AsyncMock()
        manager = QueryQuotaManager()
        manager._redis = mock_redis

        result = await manager._get_redis()
        assert result is mock_redis
