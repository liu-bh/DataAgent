"""datapilot_guardrail.checker 单元测试。

覆盖 GuardrailChecker 的编排逻辑：SQL 风险检测、行数限制、配额检查。
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from datapilot_guardrail.checker import GuardrailChecker
from datapilot_guardrail.models import QuotaConfig, RiskLevel


class TestGuardrailCheckerInit:
    """GuardrailChecker 初始化测试。"""

    def test_default_init(self) -> None:
        """默认初始化。"""
        checker = GuardrailChecker()
        assert checker.sql_risk_detector is not None
        assert checker.row_limit_enforcer is not None
        assert checker.quota_manager is not None

    def test_custom_redis_url(self) -> None:
        """自定义 Redis URL。"""
        checker = GuardrailChecker(redis_url="redis://custom:6380/1")
        assert checker.quota_manager.redis_url == "redis://custom:6380/1"


class TestCheckBlockedSQL:
    """BLOCKED SQL 的检查流程。"""

    @pytest.fixture()
    def checker(self) -> GuardrailChecker:
        """创建检查器实例。"""
        return GuardrailChecker()

    @pytest.mark.asyncio
    async def test_ddl_blocked(self, checker: GuardrailChecker) -> None:
        """DDL 语句直接返回 passed=False。"""
        result = await checker.check(
            sql="DROP TABLE users",
            tenant_id="test-tenant",
        )

        assert result.passed is False
        assert result.risk_level == RiskLevel.BLOCKED
        assert "DROP" in result.blocked_reason.upper() or "DDL" in result.blocked_reason.upper()

    @pytest.mark.asyncio
    async def test_insert_blocked(self, checker: GuardrailChecker) -> None:
        """INSERT 语句直接返回 passed=False。"""
        result = await checker.check(
            sql="INSERT INTO users (name) VALUES ('test')",
            tenant_id="test-tenant",
        )

        assert result.passed is False
        assert result.risk_level == RiskLevel.BLOCKED

    @pytest.mark.asyncio
    async def test_delete_blocked(self, checker: GuardrailChecker) -> None:
        """DELETE 语句直接返回 passed=False。"""
        result = await checker.check(
            sql="DELETE FROM users WHERE id = 1",
            tenant_id="test-tenant",
        )

        assert result.passed is False
        assert result.risk_level == RiskLevel.BLOCKED

    @pytest.mark.asyncio
    async def test_blocked_sql_no_quota_check(self, checker: GuardrailChecker) -> None:
        """BLOCKED 的 SQL 不应触发配额检查（提前返回）。"""
        # Mock 配额管理器，如果被调用则标记
        original_check = checker.quota_manager.check_quota
        called = False

        async def mock_check(*args, **kwargs):
            nonlocal called
            called = True
            return True, -1

        checker.quota_manager.check_quota = mock_check

        result = await checker.check(
            sql="DROP TABLE users",
            tenant_id="test-tenant",
        )

        assert result.passed is False
        # BLOCKED 后提前返回，不应调用配额检查
        assert called is False

        # 恢复
        checker.quota_manager.check_quota = original_check


class TestCheckSafeSQL:
    """SAFE SQL 的检查流程（Redis 不可用）。"""

    @pytest.fixture()
    def checker(self) -> GuardrailChecker:
        """创建检查器实例（Redis 不可用，降级放行）。"""
        return GuardrailChecker(redis_url="redis://nonexistent:6379/0")

    @pytest.mark.asyncio
    async def test_simple_select_passes(self, checker: GuardrailChecker) -> None:
        """简单 SELECT 通过所有检查。"""
        result = await checker.check(
            sql="SELECT id FROM users LIMIT 10",
            tenant_id="test-tenant",
        )

        assert result.passed is True
        assert result.risk_level == RiskLevel.SAFE
        assert result.quota_remaining == -1  # Redis 不可用

    @pytest.mark.asyncio
    async def test_select_without_limit_adds_warning(self, checker: GuardrailChecker) -> None:
        """无 LIMIT 的 SELECT 添加行数限制警告。"""
        result = await checker.check(
            sql="SELECT id FROM users",
            tenant_id="test-tenant",
        )

        assert result.passed is True
        assert any("LIMIT" in w for w in result.warnings)
        assert result.max_rows == 10000


class TestCheckWithMockQuota:
    """使用 Mock 配额管理器测试完整流程。"""

    @pytest.mark.asyncio
    async def test_quota_exhausted(self) -> None:
        """配额耗尽时返回 passed=False。"""
        checker = GuardrailChecker()

        # Mock 配额管理器返回耗尽
        checker.quota_manager.check_quota = AsyncMock(return_value=(False, 0))

        result = await checker.check(
            sql="SELECT id FROM users LIMIT 10",
            tenant_id="test-tenant",
        )

        assert result.passed is False
        assert "配额" in result.blocked_reason
        assert result.quota_remaining == 0

    @pytest.mark.asyncio
    async def test_all_checks_pass(self) -> None:
        """所有检查通过。"""
        checker = GuardrailChecker()

        checker.quota_manager.check_quota = AsyncMock(return_value=(True, 500))

        result = await checker.check(
            sql="SELECT id FROM users LIMIT 10",
            tenant_id="test-tenant",
        )

        assert result.passed is True
        assert result.risk_level == RiskLevel.SAFE
        assert result.quota_remaining == 500


class TestCheckWithCustomConfig:
    """自定义配额配置测试。"""

    @pytest.mark.asyncio
    async def test_custom_quota_config(self) -> None:
        """使用自定义配额配置。"""
        checker = GuardrailChecker()
        config = QuotaConfig(daily_limit=500, hourly_limit=100, max_rows_per_query=1000)

        checker.quota_manager.check_quota = AsyncMock(return_value=(True, 300))

        result = await checker.check(
            sql="SELECT id FROM users",
            tenant_id="test-tenant",
            quota_config=config,
        )

        # 自定义 max_rows_per_query = 1000
        assert result.max_rows == 1000
        assert result.quota_remaining == 300


class TestCheckPostgresDialect:
    """PostgreSQL 方言测试。"""

    @pytest.fixture()
    def checker(self) -> GuardrailChecker:
        """创建检查器实例。"""
        return GuardrailChecker(redis_url="redis://nonexistent:6379/0")

    @pytest.mark.asyncio
    async def test_postgres_select(self, checker: GuardrailChecker) -> None:
        """PostgreSQL 方言的 SELECT 通过检查。"""
        result = await checker.check(
            sql="SELECT id FROM users LIMIT 10",
            tenant_id="test-tenant",
            dialect="postgres",
        )

        assert result.passed is True
        assert result.risk_level == RiskLevel.SAFE

    @pytest.mark.asyncio
    async def test_postgres_ddl_blocked(self, checker: GuardrailChecker) -> None:
        """PostgreSQL 方言的 DDL 被拦截。"""
        result = await checker.check(
            sql="DROP TABLE users",
            tenant_id="test-tenant",
            dialect="postgres",
        )

        assert result.passed is False
        assert result.risk_level == RiskLevel.BLOCKED


class TestCheckHighRiskSQL:
    """HIGH 风险 SQL 的检查流程。"""

    @pytest.fixture()
    def checker(self) -> GuardrailChecker:
        """创建检查器实例。"""
        return GuardrailChecker(redis_url="redis://nonexistent:6379/0")

    @pytest.mark.asyncio
    async def test_system_table_select_has_warning(self, checker: GuardrailChecker) -> None:
        """访问系统表的 SELECT 产生警告但仍通过。"""
        result = await checker.check(
            sql="SELECT * FROM information_schema.tables LIMIT 10",
            tenant_id="test-tenant",
        )

        # HIGH 风险不拦截，但应有警告
        assert result.passed is True
        assert result.risk_level == RiskLevel.HIGH
        assert len(result.warnings) > 0
