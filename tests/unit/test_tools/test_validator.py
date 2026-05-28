"""ToolParameterValidator 参数校验单元测试。"""

from __future__ import annotations

from datapilot_tools.models import (
    ToolCategory,
    ToolDefinition,
    ToolParameter,
)
from datapilot_tools.validator import ToolParameterValidator


def _make_tool(parameters: list[ToolParameter]) -> ToolDefinition:
    """创建带指定参数的工具定义。"""
    return ToolDefinition(
        name="test_tool",
        description="测试工具",
        category=ToolCategory.SYSTEM,
        parameters=parameters,
    )


class TestRequiredValidation:
    """必填参数校验测试。"""

    def test_missing_required_param(self) -> None:
        """测试缺少必填参数返回错误。"""
        tool = _make_tool([
            ToolParameter(name="sql", type="string", description="SQL"),
            ToolParameter(name="dialect", type="string", description="方言", required=False),
        ])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"dialect": "mysql"})
        assert len(errors) == 1
        assert "sql" in errors[0]

    def test_all_required_present(self) -> None:
        """测试所有必填参数存在时通过。"""
        tool = _make_tool([
            ToolParameter(name="a", type="string", description="A"),
            ToolParameter(name="b", type="integer", description="B"),
        ])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"a": "hello", "b": 42})
        assert errors == []

    def test_optional_param_not_provided(self) -> None:
        """测试可选参数未提供时通过。"""
        tool = _make_tool([
            ToolParameter(name="a", type="string", description="A"),
            ToolParameter(name="b", type="string", description="B", required=False),
        ])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"a": "hello"})
        assert errors == []

    def test_empty_params_dict_with_required(self) -> None:
        """测试空参数字典但存在必填参数。"""
        tool = _make_tool([
            ToolParameter(name="sql", type="string", description="SQL"),
        ])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {})
        assert len(errors) == 1

    def test_no_params_required(self) -> None:
        """测试无参数时通过。"""
        tool = _make_tool([])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {})
        assert errors == []


class TestTypeValidation:
    """参数类型校验测试。"""

    def test_string_type_correct(self) -> None:
        """测试字符串类型正确。"""
        tool = _make_tool([ToolParameter(name="s", type="string", description="S")])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"s": "hello"})
        assert errors == []

    def test_string_type_wrong(self) -> None:
        """测试字符串类型错误。"""
        tool = _make_tool([ToolParameter(name="s", type="string", description="S")])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"s": 123})
        assert len(errors) == 1
        assert "string" in errors[0]

    def test_integer_type_correct(self) -> None:
        """测试整数类型正确。"""
        tool = _make_tool([ToolParameter(name="n", type="integer", description="N")])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"n": 42})
        assert errors == []

    def test_integer_type_accepts_float_whole(self) -> None:
        """测试整数类型接受整数值的浮点表示（如 1.0）。"""
        tool = _make_tool([ToolParameter(name="n", type="integer", description="N")])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"n": 10.0})
        assert errors == []

    def test_integer_type_rejects_float_fractional(self) -> None:
        """测试整数类型拒绝小数浮点值（如 1.5）。"""
        tool = _make_tool([ToolParameter(name="n", type="integer", description="N")])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"n": 1.5})
        assert len(errors) == 1

    def test_boolean_type_correct(self) -> None:
        """测试布尔类型正确。"""
        tool = _make_tool([ToolParameter(name="flag", type="boolean", description="Flag")])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"flag": True})
        assert errors == []

    def test_array_type_correct(self) -> None:
        """测试数组类型正确。"""
        tool = _make_tool([ToolParameter(name="items", type="array", description="Items")])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"items": [1, 2, 3]})
        assert errors == []

    def test_object_type_correct(self) -> None:
        """测试对象类型正确。"""
        tool = _make_tool([ToolParameter(name="config", type="object", description="Config")])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"config": {"key": "value"}})
        assert errors == []


class TestEnumValidation:
    """枚举值校验测试。"""

    def test_valid_enum_value(self) -> None:
        """测试合法枚举值。"""
        tool = _make_tool([
            ToolParameter(name="dialect", type="string", description="方言", enum=["mysql", "postgresql"]),
        ])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"dialect": "mysql"})
        assert errors == []

    def test_invalid_enum_value(self) -> None:
        """测试非法枚举值。"""
        tool = _make_tool([
            ToolParameter(name="dialect", type="string", description="方言", enum=["mysql", "postgresql"]),
        ])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"dialect": "oracle"})
        assert len(errors) == 1
        assert "枚举" in errors[0]


class TestRangeValidation:
    """数值范围校验测试。"""

    def test_value_within_range(self) -> None:
        """测试值在范围内。"""
        tool = _make_tool([
            ToolParameter(name="limit", type="integer", description="限制", minimum=1, maximum=100),
        ])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"limit": 50})
        assert errors == []

    def test_value_below_minimum(self) -> None:
        """测试值小于最小值。"""
        tool = _make_tool([
            ToolParameter(name="limit", type="integer", description="限制", minimum=1, maximum=100),
        ])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"limit": 0})
        assert len(errors) == 1
        assert "最小值" in errors[0]

    def test_value_above_maximum(self) -> None:
        """测试值大于最大值。"""
        tool = _make_tool([
            ToolParameter(name="limit", type="integer", description="限制", minimum=1, maximum=100),
        ])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"limit": 101})
        assert len(errors) == 1
        assert "最大值" in errors[0]

    def test_range_with_float(self) -> None:
        """测试浮点数范围校验。"""
        tool = _make_tool([
            ToolParameter(name="rate", type="float", description="比率", minimum=0.0, maximum=1.0),
        ])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"rate": 0.5})
        assert errors == []


class TestUnknownParameter:
    """未知参数校验测试。"""

    def test_unknown_param(self) -> None:
        """测试未知参数返回错误。"""
        tool = _make_tool([ToolParameter(name="a", type="string", description="A")])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"a": "hello", "b": "world"})
        assert any("未知参数" in e for e in errors)

    def test_multiple_errors(self) -> None:
        """测试多个错误同时返回。"""
        tool = _make_tool([
            ToolParameter(name="sql", type="string", description="SQL"),
            ToolParameter(name="limit", type="integer", description="限制", minimum=1, maximum=100),
        ])
        validator = ToolParameterValidator()
        errors = validator.validate(tool, {"limit": 200})
        assert len(errors) >= 2  # 缺少必填参数 + 超出最大值
