"""ToolRegistry 工具注册表单元测试。"""

from __future__ import annotations

from datapilot_tools.models import (
    ToolCategory,
    ToolDefinition,
    ToolExecutionResult,
    ToolParameter,
)
from datapilot_tools.registry import ToolRegistry


def _make_tool(
    name: str = "test_tool",
    category: ToolCategory = ToolCategory.SYSTEM,
    description: str = "测试工具",
) -> ToolDefinition:
    """创建测试用工具定义。"""
    return ToolDefinition(name=name, description=description, category=category)


def _make_sql_tool() -> ToolDefinition:
    """创建 SQL 类别的工具定义。"""
    return ToolDefinition(
        name="execute_sql",
        description="执行 SQL 查询",
        category=ToolCategory.SQL,
        parameters=[
            ToolParameter(name="sql", type="string", description="SQL 语句"),
        ],
    )


class TestRegister:
    """register 方法测试。"""

    def test_register_tool(self) -> None:
        """测试注册工具。"""
        registry = ToolRegistry()
        tool = _make_tool()
        registry.register(tool)
        assert registry.get("test_tool") is tool

    def test_register_with_executor(self) -> None:
        """测试注册工具及执行器。"""
        registry = ToolRegistry()
        tool = _make_tool()
        executor = lambda name, params: None  # noqa: E731
        registry.register(tool, executor)
        assert registry.get_executor("test_tool") is executor

    def test_register_without_executor(self) -> None:
        """测试注册工具但不提供执行器。"""
        registry = ToolRegistry()
        tool = _make_tool()
        registry.register(tool)
        assert registry.get_executor("test_tool") is None

    def test_register_replaces_existing(self) -> None:
        """测试重复注册同一名称工具会覆盖。"""
        registry = ToolRegistry()
        tool1 = _make_tool(description="旧工具")
        tool2 = _make_tool(description="新工具")
        registry.register(tool1)
        registry.register(tool2)
        assert registry.get("test_tool").description == "新工具"

    def test_register_multiple_tools(self) -> None:
        """测试注册多个工具。"""
        registry = ToolRegistry()
        registry.register(_make_tool("tool_a"))
        registry.register(_make_tool("tool_b"))
        registry.register(_make_tool("tool_c"))
        assert len(registry.discover()) == 3


class TestUnregister:
    """unregister 方法测试。"""

    def test_unregister_existing(self) -> None:
        """测试注销已存在的工具。"""
        registry = ToolRegistry()
        registry.register(_make_tool())
        assert registry.unregister("test_tool") is True
        assert registry.get("test_tool") is None

    def test_unregister_non_existing(self) -> None:
        """测试注销不存在的工具。"""
        registry = ToolRegistry()
        assert registry.unregister("nonexistent") is False

    def test_unregister_also_removes_executor(self) -> None:
        """测试注销工具同时移除执行器。"""
        registry = ToolRegistry()
        tool = _make_tool()
        executor = lambda name, params: None  # noqa: E731
        registry.register(tool, executor)
        registry.unregister("test_tool")
        assert registry.get_executor("test_tool") is None


class TestDiscover:
    """discover 方法测试。"""

    def test_discover_empty(self) -> None:
        """测试空注册表发现。"""
        registry = ToolRegistry()
        assert registry.discover() == []

    def test_discover_returns_all(self) -> None:
        """测试发现所有工具。"""
        registry = ToolRegistry()
        tools = [_make_tool("a"), _make_tool("b"), _make_tool("c")]
        for t in tools:
            registry.register(t)
        discovered = registry.discover()
        assert len(discovered) == 3
        names = {t.name for t in discovered}
        assert names == {"a", "b", "c"}


class TestGet:
    """get 方法测试。"""

    def test_get_existing(self) -> None:
        """测试获取已存在的工具。"""
        registry = ToolRegistry()
        tool = _make_tool()
        registry.register(tool)
        assert registry.get("test_tool") is tool

    def test_get_non_existing(self) -> None:
        """测试获取不存在的工具。"""
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None


class TestSearchByCategory:
    """search_by_category 方法测试。"""

    def test_search_sql_tools(self) -> None:
        """测试搜索 SQL 类别工具。"""
        registry = ToolRegistry()
        registry.register(_make_sql_tool())
        registry.register(_make_tool("python_tool", ToolCategory.PYTHON))
        results = registry.search_by_category(ToolCategory.SQL)
        assert len(results) == 1
        assert results[0].name == "execute_sql"

    def test_search_empty_category(self) -> None:
        """测试搜索空类别返回空列表。"""
        registry = ToolRegistry()
        registry.register(_make_sql_tool())
        results = registry.search_by_category(ToolCategory.PYTHON)
        assert results == []

    def test_search_returns_multiple_in_same_category(self) -> None:
        """测试同一类别多个工具。"""
        registry = ToolRegistry()
        registry.register(_make_tool("sql_1", ToolCategory.SQL))
        registry.register(_make_tool("sql_2", ToolCategory.SQL))
        registry.register(_make_tool("py_1", ToolCategory.PYTHON))
        results = registry.search_by_category(ToolCategory.SQL)
        assert len(results) == 2


class TestSearchByCapability:
    """search_by_capability 方法测试。"""

    def test_search_by_description(self) -> None:
        """测试通过描述搜索。"""
        registry = ToolRegistry()
        registry.register(_make_sql_tool())
        registry.register(_make_tool("python_tool", ToolCategory.PYTHON, description="执行 Python"))
        results = registry.search_by_capability("SQL")
        assert len(results) == 1
        assert results[0].name == "execute_sql"

    def test_search_by_parameter_name(self) -> None:
        """测试通过参数名搜索。"""
        registry = ToolRegistry()
        registry.register(_make_sql_tool())
        registry.register(_make_tool("other", ToolCategory.SYSTEM, description="其他工具"))
        results = registry.search_by_capability("sql")
        assert len(results) >= 1

    def test_search_case_insensitive(self) -> None:
        """测试关键词搜索大小写不敏感。"""
        registry = ToolRegistry()
        registry.register(_make_sql_tool())
        results_lower = registry.search_by_capability("sql")
        results_upper = registry.search_by_capability("SQL")
        assert len(results_lower) == len(results_upper)

    def test_search_no_match(self) -> None:
        """测试无匹配结果。"""
        registry = ToolRegistry()
        registry.register(_make_sql_tool())
        results = registry.search_by_capability("nonexistent_keyword_xyz")
        assert results == []


class TestToFunctionSchemas:
    """to_function_schemas 方法测试。"""

    def test_generates_openai_format(self) -> None:
        """测试生成 OpenAI Function Calling 格式。"""
        registry = ToolRegistry()
        registry.register(_make_sql_tool())
        schemas = registry.to_function_schemas()
        assert len(schemas) == 1
        schema = schemas[0]
        assert schema["type"] == "function"
        assert "function" in schema
        assert schema["function"]["name"] == "execute_sql"

    def test_generates_schema_for_multiple_tools(self) -> None:
        """测试为多个工具生成 Schema。"""
        registry = ToolRegistry()
        registry.register(_make_tool("tool_a", ToolCategory.SYSTEM, "工具A"))
        registry.register(_make_tool("tool_b", ToolCategory.SYSTEM, "工具B"))
        schemas = registry.to_function_schemas()
        assert len(schemas) == 2

    def test_empty_registry_empty_schemas(self) -> None:
        """测试空注册表返回空 Schema 列表。"""
        registry = ToolRegistry()
        schemas = registry.to_function_schemas()
        assert schemas == []
