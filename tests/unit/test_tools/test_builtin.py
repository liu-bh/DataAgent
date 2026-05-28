"""内置工具注册和结构单元测试。"""

from __future__ import annotations

from datapilot_tools.builtin import create_builtins
from datapilot_tools.models import ToolCategory


class TestCreateBuiltins:
    """create_builtins 测试。"""

    def test_returns_registry(self) -> None:
        """测试返回 ToolRegistry 实例。"""
        from datapilot_tools.registry import ToolRegistry

        registry = create_builtins()
        assert isinstance(registry, ToolRegistry)

    def test_has_four_tools(self) -> None:
        """测试内置工具数量为 4。"""
        registry = create_builtins()
        tools = registry.discover()
        assert len(tools) == 4

    def test_has_execute_sql(self) -> None:
        """测试包含 execute_sql 工具。"""
        registry = create_builtins()
        assert registry.get("execute_sql") is not None

    def test_has_execute_python(self) -> None:
        """测试包含 execute_python 工具。"""
        registry = create_builtins()
        assert registry.get("execute_python") is not None

    def test_has_search_semantic(self) -> None:
        """测试包含 search_semantic 工具。"""
        registry = create_builtins()
        assert registry.get("search_semantic") is not None

    def test_has_check_datasource_health(self) -> None:
        """测试包含 check_datasource_health 工具。"""
        registry = create_builtins()
        assert registry.get("check_datasource_health") is not None


class TestBuiltinToolDefinitions:
    """内置工具定义结构测试。"""

    def setup_method(self) -> None:
        """初始化内置注册表。"""
        self.registry = create_builtins()

    def test_execute_sql_category(self) -> None:
        """测试 execute_sql 类别为 SQL。"""
        tool = self.registry.get("execute_sql")
        assert tool is not None
        assert tool.category == ToolCategory.SQL

    def test_execute_sql_has_required_params(self) -> None:
        """测试 execute_sql 包含 sql 和 data_source_id 必填参数。"""
        tool = self.registry.get("execute_sql")
        assert tool is not None
        param_names = {p.name: p for p in tool.parameters}
        assert "sql" in param_names
        assert param_names["sql"].required is True
        assert "data_source_id" in param_names
        assert param_names["data_source_id"].required is True

    def test_execute_sql_dialect_has_enum(self) -> None:
        """测试 execute_sql 的 dialect 参数有枚举值。"""
        tool = self.registry.get("execute_sql")
        assert tool is not None
        param_names = {p.name: p for p in tool.parameters}
        dialect = param_names["dialect"]
        assert dialect.enum is not None
        assert "mysql" in dialect.enum
        assert "postgresql" in dialect.enum

    def test_execute_python_category(self) -> None:
        """测试 execute_python 类别为 PYTHON。"""
        tool = self.registry.get("execute_python")
        assert tool is not None
        assert tool.category == ToolCategory.PYTHON

    def test_execute_python_timeout_range(self) -> None:
        """测试 execute_python 的 timeout 参数有范围约束。"""
        tool = self.registry.get("execute_python")
        assert tool is not None
        param_names = {p.name: p for p in tool.parameters}
        timeout = param_names["timeout"]
        assert timeout.minimum is not None
        assert timeout.maximum is not None

    def test_search_semantic_category(self) -> None:
        """测试 search_semantic 类别为 SEARCH。"""
        tool = self.registry.get("search_semantic")
        assert tool is not None
        assert tool.category == ToolCategory.SEARCH

    def test_check_datasource_health_category(self) -> None:
        """测试 check_datasource_health 类别为 SYSTEM。"""
        tool = self.registry.get("check_datasource_health")
        assert tool is not None
        assert tool.category == ToolCategory.SYSTEM

    def test_builtin_tools_have_non_empty_descriptions(self) -> None:
        """测试所有内置工具描述不为空。"""
        tools = self.registry.discover()
        for tool in tools:
            assert len(tool.description) > 0, f"工具 '{tool.name}' 描述为空"

    def test_builtin_tools_can_generate_schemas(self) -> None:
        """测试所有内置工具可以生成 JSON Schema。"""
        schemas = self.registry.to_function_schemas()
        assert len(schemas) == 4
        for schema in schemas:
            assert schema["type"] == "function"
            assert "name" in schema["function"]
