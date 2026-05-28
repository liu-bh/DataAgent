"""Pydantic 数据模型单元测试。"""

from __future__ import annotations

import pytest

from datapilot_sqlgen.validation.models import CostEstimate, DryRunResult, ValidationResult


# ---------------------------------------------------------------------------
# DryRunResult 测试
# ---------------------------------------------------------------------------


class TestDryRunResult:
    """DryRunResult 模型测试。"""

    def test_default_values(self) -> None:
        """默认值应为 success=False，空列表。"""
        result = DryRunResult()
        assert result.success is False
        assert result.error == ""
        assert result.checked_tables == []
        assert result.warnings == []

    def test_success_result(self) -> None:
        """成功结果构造。"""
        result = DryRunResult(
            success=True,
            checked_tables=["orders", "users"],
            warnings=["表 orders 无主键"],
        )
        assert result.success is True
        assert result.error == ""
        assert len(result.checked_tables) == 2
        assert len(result.warnings) == 1

    def test_failure_result(self) -> None:
        """失败结果构造。"""
        result = DryRunResult(
            success=False,
            error="表 'orders' 不存在",
            checked_tables=[],
        )
        assert result.success is False
        assert "不存在" in result.error

    def test_from_attributes(self) -> None:
        """测试 ConfigDict(from_attributes=True) 配置。"""
        # 使用 dataclass 模拟 ORM 对象
        from dataclasses import dataclass

        @dataclass
        class MockRow:
            success: bool
            error: str
            checked_tables: list[str]
            warnings: list[str]

        mock = MockRow(
            success=True,
            error="",
            checked_tables=["t1"],
            warnings=[],
        )
        result = DryRunResult.model_validate(mock)
        assert result.success is True
        assert result.checked_tables == ["t1"]

    def test_serialization(self) -> None:
        """测试 JSON 序列化。"""
        result = DryRunResult(
            success=True,
            checked_tables=["orders"],
        )
        data = result.model_dump()
        assert data["success"] is True
        assert data["checked_tables"] == ["orders"]


# ---------------------------------------------------------------------------
# CostEstimate 测试
# ---------------------------------------------------------------------------


class TestCostEstimate:
    """CostEstimate 模型测试。"""

    def test_default_values(self) -> None:
        """默认值应为 medium 成本等级。"""
        cost = CostEstimate()
        assert cost.estimated_rows == 0
        assert cost.estimated_time_ms == 0.0
        assert cost.cost_level == "medium"
        assert cost.explain_output == ""

    def test_low_cost(self) -> None:
        """低成本预估。"""
        cost = CostEstimate(
            estimated_rows=500,
            estimated_time_ms=5.0,
            cost_level="low",
        )
        assert cost.cost_level == "low"

    def test_high_cost(self) -> None:
        """高成本预估。"""
        cost = CostEstimate(
            estimated_rows=500000,
            estimated_time_ms=5000.0,
            cost_level="high",
            explain_output="Seq Scan on orders",
        )
        assert cost.cost_level == "high"
        assert "Seq Scan" in cost.explain_output

    def test_invalid_cost_level_raises(self) -> None:
        """无效的成本等级应抛出验证错误。"""
        with pytest.raises(Exception):
            CostEstimate(cost_level="extreme")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ValidationResult 测试
# ---------------------------------------------------------------------------


class TestValidationResult:
    """ValidationResult 模型测试。"""

    def test_default_all_pass(self) -> None:
        """默认值应全部通过。"""
        result = ValidationResult()
        assert result.is_valid is True
        assert result.ast_valid is True
        assert result.dryrun_passed is True
        assert result.cost_estimate is None
        assert result.errors == []
        assert result.warnings == []

    def test_with_errors(self) -> None:
        """包含错误信息。"""
        result = ValidationResult(
            is_valid=False,
            ast_valid=False,
            errors=["SQL 语法解析失败: 语法错误"],
        )
        assert result.is_valid is False
        assert result.ast_valid is False
        assert len(result.errors) == 1

    def test_with_cost_estimate(self) -> None:
        """包含成本预估。"""
        cost = CostEstimate(
            estimated_rows=50000,
            estimated_time_ms=500.0,
            cost_level="medium",
        )
        result = ValidationResult(cost_estimate=cost)
        assert result.cost_estimate is not None
        assert result.cost_estimate.cost_level == "medium"

    def test_with_warnings(self) -> None:
        """包含警告信息。"""
        result = ValidationResult(
            warnings=["SQL 未包含 LIMIT", "未连接数据库，仅执行 AST 级别检查"],
        )
        assert len(result.warnings) == 2

    def test_from_attributes(self) -> None:
        """测试 ConfigDict(from_attributes=True) 配置。"""
        from dataclasses import dataclass

        @dataclass
        class MockResult:
            is_valid: bool
            ast_valid: bool
            dryrun_passed: bool
            cost_estimate: CostEstimate | None
            errors: list[str]
            warnings: list[str]

        cost = CostEstimate(estimated_rows=100, cost_level="low")
        mock = MockResult(
            is_valid=True,
            ast_valid=True,
            dryrun_passed=True,
            cost_estimate=cost,
            errors=[],
            warnings=["test warning"],
        )
        result = ValidationResult.model_validate(mock)
        assert result.is_valid is True
        assert result.cost_estimate is not None
        assert result.cost_estimate.estimated_rows == 100

    def test_serialization_roundtrip(self) -> None:
        """测试 model_dump 和 model_validate 往返。"""
        original = ValidationResult(
            is_valid=False,
            ast_valid=True,
            dryrun_passed=False,
            cost_estimate=CostEstimate(estimated_rows=1000, cost_level="medium"),
            errors=["表不存在"],
            warnings=["无 LIMIT"],
        )
        data = original.model_dump()
        restored = ValidationResult.model_validate(data)
        assert restored.is_valid == original.is_valid
        assert restored.cost_estimate is not None
        assert restored.cost_estimate.estimated_rows == 1000
        assert restored.errors == original.errors
