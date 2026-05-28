"""工具选择器单元测试。

使用 mock registry 测试 ToolSelector 的工具选择和评分逻辑。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from datapilot_llm.tool_selector import ToolSelector


# ---------- mock 工具对象 ----------


@dataclass
class MockTool:
    """模拟工具对象。"""

    name: str
    description: str = ""
    parameters: dict[str, Any] | None = None


class MockRegistry:
    """模拟工具注册表。"""

    def __init__(self, tools: list[MockTool] | None = None) -> None:
        self._tools = tools or []

    def list_tools(self) -> list[MockTool]:
        """返回所有已注册工具。"""
        return self._tools


# ---------- ToolSelector.select 测试 ----------


class TestToolSelectorSelect:
    """ToolSelector.select 方法测试。"""

    @pytest.fixture
    def selector(self) -> ToolSelector:
        """创建带 mock registry 的选择器。"""
        tools = [
            MockTool(
                name="sql_query",
                description="执行 SQL 查询语句，返回查询结果",
                parameters={
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string"},
                        "database": {"type": "string"},
                    },
                },
            ),
            MockTool(
                name="list_tables",
                description="列出数据库中所有表",
                parameters={
                    "type": "object",
                    "properties": {
                        "database": {"type": "string"},
                    },
                },
            ),
            MockTool(
                name="python_exec",
                description="执行 Python 代码进行数据分析",
                parameters={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "timeout": {"type": "integer"},
                    },
                },
            ),
            MockTool(
                name="search_data",
                description="搜索和过滤数据",
                parameters={
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string"},
                        "filter": {"type": "object"},
                    },
                },
            ),
        ]
        registry = MockRegistry(tools)
        return ToolSelector(registry)

    @pytest.mark.asyncio
    async def test_select_sql_tool_for_sql_query(self, selector: ToolSelector) -> None:
        """包含 SQL 关键词的消息应选中 sql_query 工具。"""
        selected = await selector.select("帮我执行 SQL 查询上个月的销售额")
        assert "sql_query" in selected

    @pytest.mark.asyncio
    async def test_select_list_tables_for_table_query(self, selector: ToolSelector) -> None:
        """询问表的列表时应选中 list_tables 工具。"""
        selected = await selector.select("数据库里有哪些表")
        assert "list_tables" in selected

    @pytest.mark.asyncio
    async def test_select_python_for_code_request(self, selector: ToolSelector) -> None:
        """请求 Python 分析时应选中 python_exec 工具。"""
        selected = await selector.select("用 Python 分析这份数据的趋势")
        assert "python_exec" in selected

    @pytest.mark.asyncio
    async def test_select_search_for_keyword_search(self, selector: ToolSelector) -> None:
        """搜索请求应选中 search_data 工具。"""
        selected = await selector.select("搜索销售额超过一万的订单")
        assert "search_data" in selected

    @pytest.mark.asyncio
    async def test_no_match_below_threshold(self) -> None:
        """无匹配时返回空列表。"""
        tools = [
            MockTool(name="image_generate", description="生成图片"),
        ]
        registry = MockRegistry(tools)
        selector = ToolSelector(registry, min_score=0.8)

        selected = await selector.select("查询数据库中的用户信息")
        assert selected == []

    @pytest.mark.asyncio
    async def test_empty_registry(self) -> None:
        """空注册表返回空列表。"""
        registry = MockRegistry([])
        selector = ToolSelector(registry)
        selected = await selector.select("查询数据")
        assert selected == []

    @pytest.mark.asyncio
    async def test_max_tools_limit(self) -> None:
        """返回的工具数量不超过 max_tools。"""
        # 创建多个工具
        tools = [
            MockTool(
                name=f"tool_{i}",
                description=f"通用工具{i} 查询 分析 数据",
            )
            for i in range(20)
        ]
        registry = MockRegistry(tools)
        selector = ToolSelector(registry, max_tools=5)

        selected = await selector.select("查询分析数据")
        assert len(selected) <= 5

    @pytest.mark.asyncio
    async def test_results_sorted_by_score(self) -> None:
        """结果按分数降序排列。"""
        tools = [
            MockTool(name="data_query", description="查询数据"),
            MockTool(name="data", description="数据"),
        ]
        registry = MockRegistry(tools)
        selector = ToolSelector(registry)

        selected = await selector.select("查询数据")
        # data_query 匹配度应该更高（名称和描述都匹配"查询"和"数据"）
        assert selected[0] == "data_query"


# ---------- ToolSelector._score_tool 测试 ----------


class TestToolSelectorScore:
    """ToolSelector._score_tool 评分逻辑测试。"""

    @pytest.fixture
    def selector(self) -> ToolSelector:
        """创建选择器。"""
        registry = MockRegistry([])
        return ToolSelector(registry)

    def test_perfect_name_match(self, selector: ToolSelector) -> None:
        """工具名称完全匹配消息关键词。"""
        tool = MockTool(name="sql查询", description="执行查询", parameters={})
        score = selector._score_tool(tool, "执行sql查询")
        assert score > 0.3  # 名称匹配权重 0.4

    def test_no_match(self, selector: ToolSelector) -> None:
        """完全不相关的消息。"""
        tool = MockTool(name="image_generate", description="生成图片")
        score = selector._score_tool(tool, "查询数据库用户表")
        assert score < 0.1

    def test_description_match(self, selector: ToolSelector) -> None:
        """工具描述匹配。"""
        tool = MockTool(name="abc", description="查询数据库中的表结构")
        score = selector._score_tool(tool, "帮我查询表结构")
        assert score > 0

    def test_parameter_match(self, selector: ToolSelector) -> None:
        """参数名称匹配。"""
        tool = MockTool(
            name="xyz",
            description="工具",
            parameters={
                "type": "object",
                "properties": {
                    "database": {"type": "string"},
                    "sql": {"type": "string"},
                },
            },
        )
        score = selector._score_tool(tool, "查询数据库的sql语句")
        assert score > 0

    def test_score_capped_at_one(self, selector: ToolSelector) -> None:
        """分数不超过 1.0。"""
        tool = MockTool(
            name="sql查询数据",
            description="sql查询数据分析",
            parameters={
                "type": "object",
                "properties": {
                    "sql": {"type": "string"},
                    "data": {"type": "string"},
                },
            },
        )
        score = selector._score_tool(tool, "sql查询数据分析data")
        assert score <= 1.0

    def test_chinese_tokenization(self, selector: ToolSelector) -> None:
        """中文分词正确。"""
        tokens = ToolSelector._tokenize("查询数据库")
        assert "查" in tokens
        assert "询" in tokens
        assert "数" in tokens
        assert "据" in tokens

    def test_english_tokenization(self, selector: ToolSelector) -> None:
        """英文分词正确。"""
        tokens = ToolSelector._tokenize("execute SQL query")
        assert "execute" in tokens
        assert "sql" in tokens
        assert "query" in tokens

    def test_mixed_language_tokenization(self, selector: ToolSelector) -> None:
        """中英文混合分词。"""
        tokens = ToolSelector._tokenize("用Python执行sql查询")
        assert "python" in tokens
        assert "sql" in tokens

    def test_stop_words_removed(self, selector: ToolSelector) -> None:
        """停用词被移除。"""
        tokens = ToolSelector._tokenize("我的数据在一个数据库里")
        # "的", "在", "一个", "里" 应该被移除
        assert "的" not in tokens
        assert "在" not in tokens
        assert "我" not in tokens
