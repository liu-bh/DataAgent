"""内置工具定义。"""

from __future__ import annotations

from datapilot_tools.models import (
    ToolCategory,
    ToolDefinition,
    ToolParameter,
)
from datapilot_tools.registry import ToolRegistry


def _build_execute_sql() -> ToolDefinition:
    """构建 execute_sql 工具定义。"""
    return ToolDefinition(
        name="execute_sql",
        description="执行 SQL 查询，支持多种数据库方言",
        category=ToolCategory.SQL,
        parameters=[
            ToolParameter(
                name="sql",
                type="string",
                description="SQL 查询语句",
            ),
            ToolParameter(
                name="dialect",
                type="string",
                description="SQL 方言",
                required=False,
                default="postgresql",
                enum=["mysql", "postgresql", "clickhouse", "doris"],
            ),
            ToolParameter(
                name="data_source_id",
                type="string",
                description="数据源 ID",
            ),
        ],
        examples=[
            {"sql": "SELECT * FROM users LIMIT 10", "dialect": "postgresql"},
        ],
        version="1.0.0",
        timeout_seconds=60.0,
        required_permissions=["query:execute"],
    )


def _build_execute_python() -> ToolDefinition:
    """构建 execute_python 工具定义。"""
    return ToolDefinition(
        name="execute_python",
        description="在沙箱中执行 Python 代码",
        category=ToolCategory.PYTHON,
        parameters=[
            ToolParameter(
                name="code",
                type="string",
                description="Python 代码",
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="超时时间（秒）",
                required=False,
                default=30,
                minimum=1,
                maximum=300,
            ),
        ],
        examples=[
            {"code": "print('hello')", "timeout": 10},
        ],
        version="1.0.0",
        timeout_seconds=60.0,
        required_permissions=["sandbox:execute"],
    )


def _build_search_semantic() -> ToolDefinition:
    """构建 search_semantic 工具定义。"""
    return ToolDefinition(
        name="search_semantic",
        description="语义模型搜索，根据自然语言描述查找相关语义模型",
        category=ToolCategory.SEARCH,
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="搜索查询关键词",
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="返回结果数量上限",
                required=False,
                default=10,
                minimum=1,
                maximum=100,
            ),
        ],
        examples=[
            {"query": "用户订单统计", "limit": 5},
        ],
        version="1.0.0",
        timeout_seconds=10.0,
    )


def _build_check_datasource_health() -> ToolDefinition:
    """构建 check_datasource_health 工具定义。"""
    return ToolDefinition(
        name="check_datasource_health",
        description="检查数据源健康状态",
        category=ToolCategory.SYSTEM,
        parameters=[
            ToolParameter(
                name="data_source_id",
                type="string",
                description="数据源 ID",
            ),
        ],
        version="1.0.0",
        timeout_seconds=15.0,
    )


def create_builtins() -> ToolRegistry:
    """创建包含所有内置工具的注册表。

    Returns:
        包含内置工具定义的 ToolRegistry 实例。
    """
    registry = ToolRegistry()
    builtin_builders = [
        _build_execute_sql,
        _build_execute_python,
        _build_search_semantic,
        _build_check_datasource_health,
    ]
    for builder in builtin_builders:
        registry.register(builder())
    return registry
