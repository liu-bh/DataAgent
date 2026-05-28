"""ToolDescriptionBuilder JSON Schema 生成单元测试。"""

from __future__ import annotations

from datapilot_tools.models import (
    ToolCategory,
    ToolDefinition,
    ToolParameter,
)
from datapilot_tools.description import ToolDescriptionBuilder
from datapilot_tools.registry import ToolRegistry


def _make_tool(
    name: str = "test_tool",
    description: str = "测试工具",
    parameters: list[ToolParameter] | None = None,
) -> ToolDefinition:
    """创建测试用工具定义。"""
    return ToolDefinition(
        name=name,
        description=description,
        category=ToolCategory.SYSTEM,
        parameters=parameters or [],
    )


class TestBuildToolSchema:
    """build_tool_schema 单工具 Schema 生成测试。"""

    def setup_method(self) -> None:
        """初始化构建器。"""
        self.builder = ToolDescriptionBuilder()

    def test_schema_type_is_function(self) -> None:
        """测试 Schema 顶层 type 为 function。"""
        tool = _make_tool()
        schema = self.builder.build_tool_schema(tool)
        assert schema["type"] == "function"

    def test_schema_has_function_key(self) -> None:
        """测试 Schema 包含 function 键。"""
        tool = _make_tool()
        schema = self.builder.build_tool_schema(tool)
        assert "function" in schema

    def test_schema_function_name(self) -> None:
        """测试 function.name 与工具名称一致。"""
        tool = _make_tool(name="my_tool")
        schema = self.builder.build_tool_schema(tool)
        assert schema["function"]["name"] == "my_tool"

    def test_schema_function_description(self) -> None:
        """测试 function.description 与工具描述一致。"""
        tool = _make_tool(description="执行 SQL 查询")
        schema = self.builder.build_tool_schema(tool)
        assert schema["function"]["description"] == "执行 SQL 查询"

    def test_schema_parameters_type_is_object(self) -> None:
        """测试 parameters.type 为 object。"""
        tool = _make_tool()
        schema = self.builder.build_tool_schema(tool)
        assert schema["function"]["parameters"]["type"] == "object"

    def test_schema_no_required_when_no_params(self) -> None:
        """测试无参数时 Schema 的 required 列表为空。"""
        tool = _make_tool()
        schema = self.builder.build_tool_schema(tool)
        params_schema = schema["function"]["parameters"]
        assert params_schema["required"] == []

    def test_schema_string_parameter(self) -> None:
        """测试字符串参数 Schema。"""
        tool = _make_tool(
            parameters=[
                ToolParameter(name="query", type="string", description="搜索查询"),
            ],
        )
        schema = self.builder.build_tool_schema(tool)
        props = schema["function"]["parameters"]["properties"]
        assert "query" in props
        assert props["query"]["type"] == "string"
        assert props["query"]["description"] == "搜索查询"

    def test_schema_required_parameter_in_required_list(self) -> None:
        """测试必填参数出现在 required 列表中。"""
        tool = _make_tool(
            parameters=[
                ToolParameter(name="sql", type="string", description="SQL 语句", required=True),
            ],
        )
        schema = self.builder.build_tool_schema(tool)
        required = schema["function"]["parameters"]["required"]
        assert "sql" in required

    def test_schema_optional_parameter_not_in_required(self) -> None:
        """测试可选参数不出现在 required 列表中。"""
        tool = _make_tool(
            parameters=[
                ToolParameter(
                    name="limit", type="integer", description="限制", required=False, default=10
                ),
            ],
        )
        schema = self.builder.build_tool_schema(tool)
        required = schema["function"]["parameters"]["required"]
        assert "limit" not in required

    def test_schema_enum_parameter(self) -> None:
        """测试带枚举的参数 Schema。"""
        tool = _make_tool(
            parameters=[
                ToolParameter(
                    name="dialect",
                    type="string",
                    description="SQL 方言",
                    enum=["mysql", "postgresql"],
                ),
            ],
        )
        schema = self.builder.build_tool_schema(tool)
        props = schema["function"]["parameters"]["properties"]
        assert props["dialect"]["enum"] == ["mysql", "postgresql"]

    def test_schema_range_parameter(self) -> None:
        """测试带范围的参数 Schema。"""
        tool = _make_tool(
            parameters=[
                ToolParameter(
                    name="timeout", type="integer", description="超时", minimum=1, maximum=300
                ),
            ],
        )
        schema = self.builder.build_tool_schema(tool)
        props = schema["function"]["parameters"]["properties"]
        assert props["timeout"]["minimum"] == 1
        assert props["timeout"]["maximum"] == 300

    def test_schema_mixed_required_optional(self) -> None:
        """测试混合必填和可选参数的 required 列表。"""
        tool = _make_tool(
            parameters=[
                ToolParameter(name="a", type="string", description="必填A"),
                ToolParameter(name="b", type="string", description="必填B"),
                ToolParameter(name="c", type="string", description="可选C", required=False),
            ],
        )
        schema = self.builder.build_tool_schema(tool)
        required = schema["function"]["parameters"]["required"]
        assert "a" in required
        assert "b" in required
        assert "c" not in required

    def test_schema_properties_is_dict(self) -> None:
        """测试 properties 为字典。"""
        tool = _make_tool(
            parameters=[
                ToolParameter(name="x", type="string", description="X"),
            ],
        )
        schema = self.builder.build_tool_schema(tool)
        props = schema["function"]["parameters"]["properties"]
        assert isinstance(props, dict)

    def test_schema_required_is_list(self) -> None:
        """测试 required 为列表。"""
        tool = _make_tool(
            parameters=[
                ToolParameter(name="x", type="string", description="X"),
            ],
        )
        schema = self.builder.build_tool_schema(tool)
        required = schema["function"]["parameters"]["required"]
        assert isinstance(required, list)


class TestBuildAllSchemas:
    """build_all_schemas 批量生成测试。"""

    def setup_method(self) -> None:
        """初始化构建器。"""
        self.builder = ToolDescriptionBuilder()

    def test_empty_registry(self) -> None:
        """测试空注册表返回空列表。"""
        registry = ToolRegistry()
        schemas = self.builder.build_all_schemas(registry)
        assert schemas == []

    def test_multiple_tools(self) -> None:
        """测试多个工具的 Schema 生成。"""
        registry = ToolRegistry()
        registry.register(_make_tool("tool_a", "工具A"))
        registry.register(_make_tool("tool_b", "工具B"))
        schemas = self.builder.build_all_schemas(registry)
        assert len(schemas) == 2
        names = [s["function"]["name"] for s in schemas]
        assert "tool_a" in names
        assert "tool_b" in names

    def test_schema_order_matches_registry_order(self) -> None:
        """测试 Schema 顺序与注册顺序一致。"""
        registry = ToolRegistry()
        registry.register(_make_tool("first"))
        registry.register(_make_tool("second"))
        registry.register(_make_tool("third"))
        schemas = self.builder.build_all_schemas(registry)
        names = [s["function"]["name"] for s in schemas]
        assert names == ["first", "second", "third"]
