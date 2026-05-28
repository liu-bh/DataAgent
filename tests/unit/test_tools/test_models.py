"""工具数据模型单元测试。"""

from __future__ import annotations

from datapilot_tools.models import (
    ToolCategory,
    ToolDefinition,
    ToolExecutionResult,
    ToolParameter,
)


class TestToolCategory:
    """ToolCategory 枚举测试。"""

    def test_sql_value(self) -> None:
        """测试 SQL 类别值。"""
        assert ToolCategory.SQL == "sql"

    def test_python_value(self) -> None:
        """测试 Python 类别值。"""
        assert ToolCategory.PYTHON == "python"

    def test_search_value(self) -> None:
        """测试 Search 类别值。"""
        assert ToolCategory.SEARCH == "search"

    def test_analysis_value(self) -> None:
        """测试 Analysis 类别值。"""
        assert ToolCategory.ANALYSIS == "analysis"

    def test_system_value(self) -> None:
        """测试 System 类别值。"""
        assert ToolCategory.SYSTEM == "system"

    def test_has_five_members(self) -> None:
        """ToolCategory 应有五个成员。"""
        assert len(ToolCategory) == 5

    def test_members_are_unique(self) -> None:
        """枚举成员值应唯一。"""
        values = [cat.value for cat in ToolCategory]
        assert len(values) == len(set(values))

    def test_is_str_subclass(self) -> None:
        """ToolCategory 应继承 str。"""
        assert issubclass(ToolCategory, str)


class TestToolParameter:
    """ToolParameter 测试。"""

    def test_required_parameter(self) -> None:
        """测试必填参数。"""
        param = ToolParameter(
            name="sql",
            type="string",
            description="SQL 查询语句",
        )
        assert param.name == "sql"
        assert param.type == "string"
        assert param.required is True
        assert param.default is None
        assert param.enum is None
        assert param.minimum is None
        assert param.maximum is None

    def test_optional_parameter(self) -> None:
        """测试可选参数。"""
        param = ToolParameter(
            name="limit",
            type="integer",
            description="返回数量",
            required=False,
            default=10,
        )
        assert param.required is False
        assert param.default == 10

    def test_parameter_with_enum(self) -> None:
        """测试带枚举约束的参数。"""
        param = ToolParameter(
            name="dialect",
            type="string",
            description="SQL 方言",
            enum=["mysql", "postgresql"],
        )
        assert param.enum == ["mysql", "postgresql"]

    def test_parameter_with_range(self) -> None:
        """测试带数值范围的参数。"""
        param = ToolParameter(
            name="timeout",
            type="integer",
            description="超时时间",
            minimum=1,
            maximum=300,
        )
        assert param.minimum == 1
        assert param.maximum == 300

    def test_all_parameter_types(self) -> None:
        """测试所有支持的参数类型。"""
        for ptype in ["string", "integer", "float", "boolean", "array", "object"]:
            param = ToolParameter(name="x", type=ptype, description="test")
            assert param.type == ptype


class TestToolDefinition:
    """ToolDefinition 测试。"""

    def test_minimal_definition(self) -> None:
        """测试最小定义。"""
        tool = ToolDefinition(
            name="test_tool",
            description="测试工具",
            category=ToolCategory.SYSTEM,
        )
        assert tool.name == "test_tool"
        assert tool.description == "测试工具"
        assert tool.category == ToolCategory.SYSTEM
        assert tool.parameters == []
        assert tool.examples == []
        assert tool.version == "1.0.0"
        assert tool.timeout_seconds == 30.0
        assert tool.required_permissions == []

    def test_full_definition(self) -> None:
        """测试完整定义。"""
        tool = ToolDefinition(
            name="full_tool",
            description="完整工具",
            category=ToolCategory.SQL,
            parameters=[
                ToolParameter(name="a", type="string", description="参数A"),
                ToolParameter(name="b", type="integer", description="参数B", required=False, default=1),
            ],
            examples=[{"a": "test", "b": 2}],
            version="2.0.0",
            timeout_seconds=60.0,
            required_permissions=["admin"],
        )
        assert tool.name == "full_tool"
        assert len(tool.parameters) == 2
        assert tool.version == "2.0.0"
        assert tool.timeout_seconds == 60.0
        assert tool.required_permissions == ["admin"]

    def test_parameters_mutable_default(self) -> None:
        """测试 parameters 默认值独立于其他实例。"""
        tool1 = ToolDefinition(name="t1", description="d", category=ToolCategory.SYSTEM)
        tool2 = ToolDefinition(name="t2", description="d", category=ToolCategory.SYSTEM)
        tool1.parameters.append(ToolParameter(name="x", type="string", description="x"))
        assert len(tool2.parameters) == 0

    def test_examples_mutable_default(self) -> None:
        """测试 examples 默认值独立于其他实例。"""
        tool1 = ToolDefinition(name="t1", description="d", category=ToolCategory.SYSTEM)
        tool2 = ToolDefinition(name="t2", description="d", category=ToolCategory.SYSTEM)
        tool1.examples.append({"key": "value"})
        assert len(tool2.examples) == 0

    def test_required_permissions_mutable_default(self) -> None:
        """测试 required_permissions 默认值独立于其他实例。"""
        tool1 = ToolDefinition(name="t1", description="d", category=ToolCategory.SYSTEM)
        tool2 = ToolDefinition(name="t2", description="d", category=ToolCategory.SYSTEM)
        tool1.required_permissions.append("perm")
        assert len(tool2.required_permissions) == 0

    def test_category_comparison(self) -> None:
        """测试类别比较。"""
        tool = ToolDefinition(name="t", description="d", category=ToolCategory.SQL)
        assert tool.category == ToolCategory.SQL
        assert tool.category != ToolCategory.PYTHON


class TestToolExecutionResult:
    """ToolExecutionResult 测试。"""

    def test_success_result(self) -> None:
        """测试成功结果。"""
        result = ToolExecutionResult(
            tool_name="test_tool",
            success=True,
            output={"data": [1, 2, 3]},
            execution_time_ms=50.0,
        )
        assert result.tool_name == "test_tool"
        assert result.success is True
        assert result.output == {"data": [1, 2, 3]}
        assert result.error == ""
        assert result.execution_time_ms == 50.0

    def test_failure_result(self) -> None:
        """测试失败结果。"""
        result = ToolExecutionResult(
            tool_name="test_tool",
            success=False,
            error="参数校验失败",
            execution_time_ms=10.0,
        )
        assert result.success is False
        assert result.error == "参数校验失败"
        assert result.output is None

    def test_default_values(self) -> None:
        """测试默认值。"""
        result = ToolExecutionResult(tool_name="t", success=True)
        assert result.output is None
        assert result.error == ""
        assert result.execution_time_ms == 0.0

    def test_execution_time_can_be_float(self) -> None:
        """测试执行时间支持浮点数。"""
        result = ToolExecutionResult(tool_name="t", success=True, execution_time_ms=123.456)
        assert result.execution_time_ms == 123.456
