"""Guardrail 安全拦截集成测试。

测试 Guardrail Service 的完整安全检查流程：
SQL 风险检测 → 行数限制 → 配额检查。
覆盖安全 SELECT、DDL 拦截、DML 拦截、系统表风险、配额和行数限制等场景。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from datapilot_guardrail.checker import GuardrailChecker
from datapilot_guardrail.models import QuotaConfig, RiskLevel
from datapilot_guardrail.sql_risk import SQLRiskDetector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def checker_with_mock_quota() -> GuardrailChecker:
    """创建配额管理器已 mock 的 GuardrailChecker。"""
    c = GuardrailChecker()
    c.quota_manager.check_quota = AsyncMock(return_value=(True, 500))
    return c


@pytest.fixture
def checker_no_redis() -> GuardrailChecker:
    """创建 Redis 不可用的 GuardrailChecker（降级放行）。"""
    return GuardrailChecker(redis_url="redis://nonexistent-host:6379/0")


# ---------------------------------------------------------------------------
# 安全拦截集成测试
# ---------------------------------------------------------------------------


class TestGuardrailFlow:
    """Guardrail 安全拦截集成测试。"""

    @pytest.mark.asyncio
    async def test_safe_select_passed(
        self, checker_with_mock_quota: GuardrailChecker
    ) -> None:
        """安全的 SELECT 查询应通过所有检查。"""
        result = await checker_with_mock_quota.check(
            sql="SELECT id, name FROM users WHERE status = 'active' LIMIT 10",
            tenant_id="tenant-001",
        )

        assert result.passed is True
        assert result.risk_level == RiskLevel.SAFE
        assert result.blocked_reason == ""
        assert result.quota_remaining == 500
        assert result.max_rows == 10

    @pytest.mark.asyncio
    async def test_ddl_blocked(
        self, checker_with_mock_quota: GuardrailChecker
    ) -> None:
        """CREATE TABLE 应被拦截。"""
        result = await checker_with_mock_quota.check(
            sql="CREATE TABLE test_table (id INT PRIMARY KEY)",
            tenant_id="tenant-001",
        )

        assert result.passed is False
        assert result.risk_level == RiskLevel.BLOCKED
        assert "DDL" in result.blocked_reason.upper() or "CREATE" in result.blocked_reason.upper()

    @pytest.mark.asyncio
    async def test_drop_blocked(
        self, checker_with_mock_quota: GuardrailChecker
    ) -> None:
        """DROP TABLE 应被拦截。"""
        result = await checker_with_mock_quota.check(
            sql="DROP TABLE orders",
            tenant_id="tenant-001",
        )

        assert result.passed is False
        assert result.risk_level == RiskLevel.BLOCKED
        assert "DROP" in result.blocked_reason.upper() or "DDL" in result.blocked_reason.upper()

    @pytest.mark.asyncio
    async def test_insert_blocked(
        self, checker_with_mock_quota: GuardrailChecker
    ) -> None:
        """INSERT 语句应被拦截。"""
        result = await checker_with_mock_quota.check(
            sql="INSERT INTO users (name, email) VALUES ('test', 'test@example.com')",
            tenant_id="tenant-001",
        )

        assert result.passed is False
        assert result.risk_level == RiskLevel.BLOCKED
        assert "INSERT" in result.blocked_reason.upper() or "写操作" in result.blocked_reason

    @pytest.mark.asyncio
    async def test_update_blocked(
        self, checker_with_mock_quota: GuardrailChecker
    ) -> None:
        """UPDATE 语句应被拦截。"""
        result = await checker_with_mock_quota.check(
            sql="UPDATE users SET name = 'hacked' WHERE id = 1",
            tenant_id="tenant-001",
        )

        assert result.passed is False
        assert result.risk_level == RiskLevel.BLOCKED
        assert "UPDATE" in result.blocked_reason.upper() or "写操作" in result.blocked_reason

    @pytest.mark.asyncio
    async def test_delete_blocked(
        self, checker_with_mock_quota: GuardrailChecker
    ) -> None:
        """DELETE 语句应被拦截。"""
        result = await checker_with_mock_quota.check(
            sql="DELETE FROM orders WHERE id = 1",
            tenant_id="tenant-001",
        )

        assert result.passed is False
        assert result.risk_level == RiskLevel.BLOCKED
        assert "DELETE" in result.blocked_reason.upper() or "写操作" in result.blocked_reason

    @pytest.mark.asyncio
    async def test_system_table_high_risk(
        self, checker_no_redis: GuardrailChecker
    ) -> None:
        """访问系统表应标记为 HIGH 风险，但仍通过（不拦截）。"""
        result = await checker_no_redis.check(
            sql="SELECT table_name FROM information_schema.tables LIMIT 10",
            tenant_id="tenant-001",
        )

        assert result.passed is True
        assert result.risk_level == RiskLevel.HIGH
        assert len(result.warnings) > 0
        assert any("系统表" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_mysql_system_table_high_risk(
        self, checker_no_redis: GuardrailChecker
    ) -> None:
        """访问 MySQL 系统表应标记为 HIGH 风险。"""
        result = await checker_no_redis.check(
            sql="SELECT user, host FROM mysql.user LIMIT 10",
            tenant_id="tenant-001",
        )

        assert result.passed is True
        assert result.risk_level == RiskLevel.HIGH

    @pytest.mark.asyncio
    async def test_quota_check(
        self, checker_with_mock_quota: GuardrailChecker
    ) -> None:
        """配额检查应正确反映剩余配额。"""
        # 模拟配额充足
        checker_with_mock_quota.quota_manager.check_quota = AsyncMock(
            return_value=(True, 200)
        )

        result = await checker_with_mock_quota.check(
            sql="SELECT id FROM users LIMIT 5",
            tenant_id="tenant-001",
        )

        assert result.passed is True
        assert result.quota_remaining == 200

    @pytest.mark.asyncio
    async def test_quota_exhausted(
        self, checker_with_mock_quota: GuardrailChecker
    ) -> None:
        """配额耗尽时应拒绝请求。"""
        checker_with_mock_quota.quota_manager.check_quota = AsyncMock(
            return_value=(False, 0)
        )

        result = await checker_with_mock_quota.check(
            sql="SELECT id FROM users LIMIT 5",
            tenant_id="tenant-001",
        )

        assert result.passed is False
        assert "配额" in result.blocked_reason
        assert result.quota_remaining == 0

    @pytest.mark.asyncio
    async def test_row_limit_check(
        self, checker_no_redis: GuardrailChecker
    ) -> None:
        """无 LIMIT 的 SQL 应触发行数限制警告。"""
        result = await checker_no_redis.check(
            sql="SELECT id, name, email FROM users WHERE status = 'active'",
            tenant_id="tenant-001",
        )

        assert result.passed is True
        assert any("LIMIT" in w for w in result.warnings)
        assert result.max_rows == 10000

    @pytest.mark.asyncio
    async def test_row_limit_custom_config(
        self, checker_with_mock_quota: GuardrailChecker
    ) -> None:
        """自定义行数限制配置应生效。"""
        config = QuotaConfig(
            daily_limit=100,
            hourly_limit=20,
            max_rows_per_query=500,
        )

        result = await checker_with_mock_quota.check(
            sql="SELECT * FROM orders",
            tenant_id="tenant-001",
            quota_config=config,
        )

        assert result.passed is True
        assert result.max_rows == 500

    @pytest.mark.asyncio
    async def test_select_with_existing_limit(
        self, checker_with_mock_quota: GuardrailChecker
    ) -> None:
        """已有合理 LIMIT 的 SELECT 不应添加额外警告。"""
        result = await checker_with_mock_quota.check(
            sql="SELECT id, name FROM users LIMIT 50",
            tenant_id="tenant-001",
        )

        assert result.passed is True
        assert result.risk_level == RiskLevel.SAFE
        assert not any("LIMIT" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_blocked_sql_skips_quota(
        self, checker_with_mock_quota: GuardrailChecker
    ) -> None:
        """BLOCKED 的 SQL 不应触发配额检查（提前返回节省 Redis 调用）。"""
        # 设置配额检查标记，如果被调用则为异常
        checker_with_mock_quota.quota_manager.check_quota = AsyncMock(
            side_effect=AssertionError("配额检查不应被调用")
        )

        result = await checker_with_mock_quota.check(
            sql="DROP TABLE users",
            tenant_id="tenant-001",
        )

        assert result.passed is False
        assert result.risk_level == RiskLevel.BLOCKED

    @pytest.mark.asyncio
    async def test_complex_select_low_risk(
        self, checker_no_redis: GuardrailChecker
    ) -> None:
        """包含 JOIN + GROUP BY + ORDER BY 的复杂 SELECT 标记为 LOW 风险。"""
        result = await checker_no_redis.check(
            sql=(
                "SELECT u.region, SUM(o.amount) AS revenue "
                "FROM orders o LEFT JOIN users u ON o.user_id = u.id "
                "WHERE o.created_at >= '2024-01-01' "
                "GROUP BY u.region "
                "ORDER BY revenue DESC "
                "LIMIT 100"
            ),
            tenant_id="tenant-001",
        )

        assert result.passed is True
        assert result.risk_level == RiskLevel.LOW

    @pytest.mark.asyncio
    async def test_truncate_blocked(
        self, checker_with_mock_quota: GuardrailChecker
    ) -> None:
        """TRUNCATE TABLE 应被拦截。"""
        result = await checker_with_mock_quota.check(
            sql="TRUNCATE TABLE orders",
            tenant_id="tenant-001",
        )

        assert result.passed is False
        assert result.risk_level == RiskLevel.BLOCKED

    @pytest.mark.asyncio
    async def test_alter_blocked(
        self, checker_with_mock_quota: GuardrailChecker
    ) -> None:
        """ALTER TABLE 应被拦截。"""
        result = await checker_with_mock_quota.check(
            sql="ALTER TABLE users ADD COLUMN phone VARCHAR(20)",
            tenant_id="tenant-001",
        )

        assert result.passed is False
        assert result.risk_level == RiskLevel.BLOCKED

    @pytest.mark.asyncio
    async def test_redis_unavailable_graceful(
        self, checker_no_redis: GuardrailChecker
    ) -> None:
        """Redis 不可用时应降级放行，不阻塞请求。"""
        result = await checker_no_redis.check(
            sql="SELECT id FROM users LIMIT 10",
            tenant_id="tenant-001",
        )

        assert result.passed is True
        # Redis 不可用时 quota_remaining 为 -1
        assert result.quota_remaining == -1


# ---------------------------------------------------------------------------
# Guardrail API 集成测试
# ---------------------------------------------------------------------------


class TestGuardrailAPI:
    """Guardrail API 端点集成测试。"""

    @pytest.fixture
    def guardrail_app(self) -> object:
        """创建 Guardrail Service 测试应用。"""
        from fastapi import FastAPI

        from datapilot_guardrail.api.routes.guardrail import (
            router as guardrail_router,
            set_checker,
        )

        app = FastAPI()
        app.include_router(guardrail_router)

        # 注入 mock 配额的 checker
        checker = GuardrailChecker()
        checker.quota_manager.check_quota = AsyncMock(return_value=(True, 500))
        set_checker(checker)

        return app

    @pytest.fixture
    async def guardrail_client(self, guardrail_app: object) -> AsyncClient:
        """创建 Guardrail 异步客户端。"""
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=guardrail_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_check_sql_safe(
        self, guardrail_client: AsyncClient
    ) -> None:
        """API: 安全 SQL 应通过预检。"""
        response = await guardrail_client.post(
            "/api/v1/guardrail/check-sql",
            json={
                "sql": "SELECT id FROM users LIMIT 10",
                "dialect": "mysql",
                "tenant_id": "tenant-001",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["passed"] is True
        assert data["risk_level"] == "safe"

    @pytest.mark.asyncio
    async def test_check_sql_blocked(
        self, guardrail_client: AsyncClient
    ) -> None:
        """API: DDL SQL 应被拦截。"""
        response = await guardrail_client.post(
            "/api/v1/guardrail/check-sql",
            json={
                "sql": "DROP TABLE users",
                "dialect": "mysql",
                "tenant_id": "tenant-001",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["passed"] is False
        assert data["risk_level"] == "blocked"

    @pytest.mark.asyncio
    async def test_check_sql_high_risk(
        self, guardrail_client: AsyncClient
    ) -> None:
        """API: 系统表 SQL 应标记为 HIGH 风险。"""
        response = await guardrail_client.post(
            "/api/v1/guardrail/check-sql",
            json={
                "sql": "SELECT * FROM information_schema.tables LIMIT 5",
                "dialect": "mysql",
                "tenant_id": "tenant-001",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["passed"] is True
        assert data["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_quota_endpoint(
        self, guardrail_client: AsyncClient
    ) -> None:
        """API: 配额查询端点应返回配额信息。"""
        response = await guardrail_client.get(
            "/api/v1/guardrail/quota/tenant-001",
        )

        assert response.status_code == 200
        data = response.json()
        assert "tenant_id" in data
        assert "passed" in data
        assert "quota_remaining" in data

    @pytest.mark.asyncio
    async def test_check_sql_missing_fields(
        self, guardrail_client: AsyncClient
    ) -> None:
        """API: 缺少必填字段应返回 422。"""
        response = await guardrail_client.post(
            "/api/v1/guardrail/check-sql",
            json={"sql": "SELECT 1"},  # 缺少 tenant_id
        )

        assert response.status_code == 422
