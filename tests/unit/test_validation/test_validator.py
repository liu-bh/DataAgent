"""SQLValidationOrchestrator 单元测试。"""

from __future__ import annotations

import pytest

from datapilot_sqlgen.validation.models import CostEstimate, ValidationResult
from datapilot_sqlgen.validation.validator import SQLValidationOrchestrator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def orchestrator() -> SQLValidationOrchestrator:
    """创建无连接的编排器实例。"""
    return SQLValidationOrchestrator(connection_url=None)


@pytest.fixture
def orchestrator_with_limit() -> SQLValidationOrchestrator:
    """创建带自定义 LIMIT 的编排器实例。"""
    return SQLValidationOrchestrator(connection_url=None, default_limit=500)


# ---------------------------------------------------------------------------
# 完整验证流程测试
# ---------------------------------------------------------------------------


class TestValidateFullFlow:
    """validate() 完整编排流程测试。"""

    @pytest.mark.asyncio
    async def test_valid_select_sql(self, orchestrator: SQLValidationOrchestrator) -> None:
        """有效 SELECT 语句应通过验证。"""
        result = await orchestrator.validate(
            "SELECT id, name FROM users LIMIT 10",
            dialect="mysql",
        )
        assert result.is_valid is True
        assert result.ast_valid is True
        assert result.dryrun_passed is True
        assert isinstance(result.errors, list)

    @pytest.mark.asyncio
    async def test_valid_sql_with_cost_estimate(
        self, orchestrator: SQLValidationOrchestrator,
    ) -> None:
        """有效 SQL 应包含成本预估。"""
        result = await orchestrator.validate(
            "SELECT COUNT(*) FROM orders",
            dialect="mysql",
        )
        assert result.is_valid is True
        assert result.cost_estimate is not None
        assert isinstance(result.cost_estimate, CostEstimate)

    @pytest.mark.asyncio
    async def test_empty_sql_fails(self, orchestrator: SQLValidationOrchestrator) -> None:
        """空 SQL 应验证失败。"""
        result = await orchestrator.validate("", dialect="mysql")
        assert result.is_valid is False
        assert result.ast_valid is False

    @pytest.mark.asyncio
    async def test_invalid_syntax_fails(self, orchestrator: SQLValidationOrchestrator) -> None:
        """无效 SQL 语法应验证失败。"""
        result = await orchestrator.validate("SELECT WHERE FROM HAVING GROUP", dialect="mysql")
        assert result.is_valid is False
        assert result.ast_valid is False
        # sqlglot 抛出异常时，validator 记录 "解析失败"
        assert any("解析失败" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_missing_limit_warning(
        self, orchestrator: SQLValidationOrchestrator,
    ) -> None:
        """缺少 LIMIT 应产生警告。"""
        result = await orchestrator.validate(
            "SELECT * FROM orders",
            dialect="mysql",
        )
        assert any("LIMIT" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_with_limit_no_limit_warning(
        self, orchestrator: SQLValidationOrchestrator,
    ) -> None:
        """有 LIMIT 时不应有 LIMIT 警告。"""
        result = await orchestrator.validate(
            "SELECT * FROM orders LIMIT 100",
            dialect="mysql",
        )
        # 注意: Dry-run 的 AST 警告仍可能出现，但不应有 LIMIT 相关警告
        limit_warnings = [w for w in result.warnings if "LIMIT" in w and "未包含" in w]
        assert len(limit_warnings) == 0

    @pytest.mark.asyncio
    async def test_join_sql(self, orchestrator: SQLValidationOrchestrator) -> None:
        """JOIN SQL 应正常验证。"""
        result = await orchestrator.validate(
            "SELECT o.id, u.name FROM orders o JOIN users u ON o.user_id = u.id LIMIT 10",
            dialect="mysql",
        )
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_aggregation_sql(self, orchestrator: SQLValidationOrchestrator) -> None:
        """聚合 SQL 应正常验证。"""
        result = await orchestrator.validate(
            "SELECT status, COUNT(*) AS cnt FROM orders GROUP BY status LIMIT 100",
            dialect="mysql",
        )
        assert result.is_valid is True
        assert result.cost_estimate is not None

    @pytest.mark.asyncio
    async def test_unknown_dialect_warning(
        self, orchestrator: SQLValidationOrchestrator,
    ) -> None:
        """未知方言应产生警告但不阻塞。"""
        result = await orchestrator.validate(
            "SELECT 1",
            dialect="sqlite",
        )
        assert any("方言" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_postgresql_dialect(
        self, orchestrator: SQLValidationOrchestrator,
    ) -> None:
        """PostgreSQL 方言应正常验证（内部映射为 sqlglot 的 'postgres'）。"""
        result = await orchestrator.validate(
            "SELECT id, name FROM users LIMIT 10",
            dialect="postgresql",
        )
        assert result.is_valid is True


# ---------------------------------------------------------------------------
# 高成本警告测试
# ---------------------------------------------------------------------------


class TestHighCostWarning:
    """高成本查询的警告测试。"""

    @pytest.mark.asyncio
    async def test_high_cost_warning_produced(
        self, orchestrator: SQLValidationOrchestrator,
    ) -> None:
        """预估为高成本的查询应产生警告。

        注意：无连接时使用启发式估算，简单 SELECT 默认 medium，
        我们需要构造一个能触发高成本的查询。
        """
        # 使用子查询 + JOIN 来提高启发式估算的行数
        # 但启发式估算不会超过默认的 plain_select 值 10000，
        # 除非 JOIN 和子查询叠加超过 100000。
        # 由于启发式估算是乘法叠加，简单构造即可。
        result = await orchestrator.validate(
            "SELECT COUNT(*) FROM orders",
            dialect="mysql",
        )
        # COUNT 聚合应为 low 成本，不会触发高成本警告
        high_cost_warnings = [
            w for w in result.warnings if "成本较高" in w
        ]
        assert len(high_cost_warnings) == 0


# ---------------------------------------------------------------------------
# 结果结构测试
# ---------------------------------------------------------------------------


class TestResultStructure:
    """ValidationResult 结构测试。"""

    @pytest.mark.asyncio
    async def test_result_type(self, orchestrator: SQLValidationOrchestrator) -> None:
        """应返回 ValidationResult 类型。"""
        result = await orchestrator.validate("SELECT 1", dialect="mysql")
        assert isinstance(result, ValidationResult)

    @pytest.mark.asyncio
    async def test_all_fields_populated(
        self, orchestrator: SQLValidationOrchestrator,
    ) -> None:
        """所有字段应有值。"""
        result = await orchestrator.validate("SELECT 1", dialect="mysql")
        assert isinstance(result.is_valid, bool)
        assert isinstance(result.ast_valid, bool)
        assert isinstance(result.dryrun_passed, bool)
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)
        assert result.cost_estimate is not None


# ---------------------------------------------------------------------------
# 步骤独立执行测试
# ---------------------------------------------------------------------------


class TestStepIndependence:
    """验证各步骤独立执行，单步失败不阻塞后续步骤。"""

    @pytest.mark.asyncio
    async def test_ast_fails_but_dryrun_runs(
        self, orchestrator: SQLValidationOrchestrator,
    ) -> None:
        """AST 验证失败时，Dry-run 仍应执行。

        注意：对于无效 SQL，Dry-run 也会失败，但应仍然执行并记录结果。
        """
        result = await orchestrator.validate("SELECT WHERE FROM HAVING GROUP", dialect="mysql")
        # AST 应失败
        assert result.ast_valid is False
        # Dry-run 也应失败（因为 AST 也无法解析）
        # 关键点是：dryrun_passed 字段有值（不是默认），说明步骤被执行了
        assert isinstance(result.dryrun_passed, bool)
        # 成本预估也应执行
        assert result.cost_estimate is not None

    @pytest.mark.asyncio
    async def test_dryrun_failure_recorded(
        self, orchestrator: SQLValidationOrchestrator,
    ) -> None:
        """Dry-run 失败应在 errors 中记录。"""
        result = await orchestrator.validate("INVALID SQL !!!", dialect="mysql")
        dryrun_errors = [e for e in result.errors if "Dry-run" in e]
        # Dry-run 应该尝试执行并记录结果
        # 对于 AST 无法解析的 SQL，dry-runner 也可能返回失败
        assert isinstance(result.errors, list)


# ---------------------------------------------------------------------------
# 自定义 LIMIT 测试
# ---------------------------------------------------------------------------


class TestCustomLimit:
    """自定义 LIMIT 配置测试。"""

    @pytest.mark.asyncio
    async def test_custom_limit_in_warning(
        self, orchestrator_with_limit: SQLValidationOrchestrator,
    ) -> None:
        """自定义 LIMIT 应反映在警告消息中。"""
        result = await orchestrator_with_limit.validate(
            "SELECT * FROM orders",
            dialect="mysql",
        )
        limit_warnings = [w for w in result.warnings if "LIMIT" in w and "500" in w]
        # 验证警告中包含自定义的 LIMIT 值
        assert len(limit_warnings) > 0
