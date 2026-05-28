"""ChartDescriptionGenerator 描述生成器单元测试。"""

from __future__ import annotations

import pytest

from datapilot_agent.chart.description import ChartDescriptionGenerator


class TestRuleBasedTitle:
    """规则化标题生成测试。"""

    def _make_generator(self) -> ChartDescriptionGenerator:
        """创建描述生成器实例（无 LLM）。"""
        return ChartDescriptionGenerator()

    def test_line_title(self) -> None:
        """折线图标题。"""
        gen = self._make_generator()
        title = gen._generate_rule_based_title("line", "日期", ["销售额"])
        assert "销售额" in title
        assert "日期" in title
        assert "趋势" in title

    def test_bar_title(self) -> None:
        """柱状图标题。"""
        gen = self._make_generator()
        title = gen._generate_rule_based_title("bar", "区域", ["销售额"])
        assert "区域" in title
        assert "销售额" in title
        assert "对比" in title

    def test_pie_title(self) -> None:
        """饼图标题。"""
        gen = self._make_generator()
        title = gen._generate_rule_based_title("pie", "部门", ["预算"])
        assert "部门" in title
        assert "预算" in title
        assert "占比" in title

    def test_scatter_title_two_fields(self) -> None:
        """散点图标题（双字段）。"""
        gen = self._make_generator()
        title = gen._generate_rule_based_title("scatter", "category", ["价格", "数量"])
        assert "价格" in title
        assert "数量" in title
        assert "相关性" in title

    def test_scatter_title_single_field(self) -> None:
        """散点图标题（单字段）。"""
        gen = self._make_generator()
        title = gen._generate_rule_based_title("scatter", "x轴", ["值"])
        assert "x轴" in title
        assert "分布" in title

    def test_table_title(self) -> None:
        """表格标题。"""
        gen = self._make_generator()
        title = gen._generate_rule_based_title("table", "日期", ["销售额", "利润"])
        assert "日期" in title
        assert "明细" in title

    def test_area_title(self) -> None:
        """面积图标题。"""
        gen = self._make_generator()
        title = gen._generate_rule_based_title("area", "月份", ["累计销售额"])
        assert "月份" in title
        assert "累计" in title

    def test_heatmap_title(self) -> None:
        """热力图标题。"""
        gen = self._make_generator()
        title = gen._generate_rule_based_title("heatmap", "维度1", ["值"])
        assert "热力图" in title

    def test_unknown_chart_type_title(self) -> None:
        """未知图表类型标题。"""
        gen = self._make_generator()
        title = gen._generate_rule_based_title("funnel", "阶段", ["转化率"])
        assert "阶段" in title
        assert "转化率" in title

    def test_multiple_y_fields_title(self) -> None:
        """多个 Y 轴字段标题。"""
        gen = self._make_generator()
        title = gen._generate_rule_based_title("line", "日期", ["销售额", "利润", "成本"])
        assert "销售额" in title
        assert "利润" in title
        assert "成本" in title

    def test_empty_y_fields_title(self) -> None:
        """空 Y 轴字段标题。"""
        gen = self._make_generator()
        title = gen._generate_rule_based_title("bar", "类别", [])
        assert "类别" in title


class TestRuleBasedDescription:
    """规则化描述生成测试。"""

    def _make_generator(self) -> ChartDescriptionGenerator:
        """创建描述生成器实例（无 LLM）。"""
        return ChartDescriptionGenerator()

    def test_line_description(self) -> None:
        """折线图描述。"""
        gen = self._make_generator()
        desc = gen._generate_rule_based_description(
            "line", "日期", ["销售额"], {"count": 12}
        )
        assert "趋势" in desc
        assert "日期" in desc
        assert "12条记录" in desc

    def test_bar_description(self) -> None:
        """柱状图描述。"""
        gen = self._make_generator()
        desc = gen._generate_rule_based_description(
            "bar", "区域", ["销售额"], {"count": 4}
        )
        assert "对比" in desc
        assert "区域" in desc

    def test_pie_description(self) -> None:
        """饼图描述。"""
        gen = self._make_generator()
        desc = gen._generate_rule_based_description(
            "pie", "部门", ["预算"], {"count": 5}
        )
        assert "占比" in desc

    def test_scatter_description_two_fields(self) -> None:
        """散点图描述（双字段）。"""
        gen = self._make_generator()
        desc = gen._generate_rule_based_description(
            "scatter", "类别", ["价格", "数量"], {"count": 100}
        )
        assert "相关性" in desc

    def test_table_description(self) -> None:
        """表格描述。"""
        gen = self._make_generator()
        desc = gen._generate_rule_based_description(
            "table", "日期", ["销售额", "利润"], {"count": 10}
        )
        assert "明细" in desc

    def test_area_description(self) -> None:
        """面积图描述。"""
        gen = self._make_generator()
        desc = gen._generate_rule_based_description(
            "area", "月份", ["累计销售额"], {"count": 12}
        )
        assert "累计" in desc

    def test_heatmap_description(self) -> None:
        """热力图描述。"""
        gen = self._make_generator()
        desc = gen._generate_rule_based_description(
            "heatmap", "维度1", ["值"], {"count": 25}
        )
        assert "热力图" in desc

    def test_description_with_stats_max_min_avg(self) -> None:
        """包含 max/min/avg 统计的描述。"""
        gen = self._make_generator()
        stats = {
            "count": 10,
            "fields": {
                "销售额": {"max": 5000, "min": 1000, "avg": 3000},
            },
        }
        desc = gen._generate_rule_based_description("bar", "区域", ["销售额"], stats)
        assert "1000" in desc
        assert "5000" in desc
        assert "3000" in desc
        assert "范围" in desc

    def test_description_with_stats_avg_only(self) -> None:
        """仅有 avg 统计的描述。"""
        gen = self._make_generator()
        stats = {
            "count": 5,
            "fields": {
                "销售额": {"avg": 2500},
            },
        }
        desc = gen._generate_rule_based_description("bar", "区域", ["销售额"], stats)
        assert "2500" in desc
        assert "平均" in desc

    def test_description_empty_stats(self) -> None:
        """空统计信息的描述。"""
        gen = self._make_generator()
        desc = gen._generate_rule_based_description("line", "日期", ["值"], {})
        assert "趋势" in desc
        # 无记录数，不以数字结尾
        assert "趋势" in desc

    def test_description_no_row_count(self) -> None:
        """无行数的描述。"""
        gen = self._make_generator()
        desc = gen._generate_rule_based_description("line", "日期", ["值"], {"fields": {}})
        assert "趋势" in desc

    def test_description_multiple_fields_stats(self) -> None:
        """多字段统计的描述。"""
        gen = self._make_generator()
        stats = {
            "count": 10,
            "fields": {
                "销售额": {"max": 5000, "min": 1000, "avg": 3000},
                "利润": {"max": 1500, "min": 200, "avg": 800},
            },
        }
        desc = gen._generate_rule_based_description("line", "日期", ["销售额", "利润"], stats)
        assert "销售额" in desc
        assert "利润" in desc
        assert "3000" in desc
        assert "800" in desc


class TestStatsSummary:
    """统计摘要构建测试。"""

    def _make_generator(self) -> ChartDescriptionGenerator:
        """创建描述生成器实例（无 LLM）。"""
        return ChartDescriptionGenerator()

    def test_empty_fields(self) -> None:
        """空字段返回空字符串。"""
        gen = self._make_generator()
        result = gen._build_stats_summary([], {})
        assert result == ""

    def test_empty_stats(self) -> None:
        """空统计返回空字符串。"""
        gen = self._make_generator()
        result = gen._build_stats_summary(["销售额"], {})
        assert result == ""

    def test_full_stats(self) -> None:
        """完整统计信息。"""
        gen = self._make_generator()
        stats = {"fields": {"值": {"max": 100, "min": 0, "avg": 50}}}
        result = gen._build_stats_summary(["值"], stats)
        assert "0" in result
        assert "100" in result
        assert "50" in result


class TestAsyncTitleWithLLM:
    """LLM 标题生成测试（降级场景）。"""

    @pytest.mark.asyncio
    async def test_generate_title_no_llm(self) -> None:
        """无 LLM 时使用规则生成标题。"""
        gen = ChartDescriptionGenerator()
        title = await gen.generate_title("line", "日期", ["销售额"], {})
        assert isinstance(title, str)
        assert len(title) > 0

    @pytest.mark.asyncio
    async def test_generate_title_llm_failure_degrades(self) -> None:
        """LLM 失败时降级为规则标题。"""
        from unittest.mock import AsyncMock

        mock_router = AsyncMock()
        mock_router.generate.side_effect = Exception("LLM 不可用")
        gen = ChartDescriptionGenerator(llm_router=mock_router)
        title = await gen.generate_title("bar", "区域", ["销售额"], {})
        assert isinstance(title, str)
        assert "区域" in title


class TestAsyncDescriptionWithLLM:
    """LLM 描述生成测试（降级场景）。"""

    @pytest.mark.asyncio
    async def test_generate_description_no_llm(self) -> None:
        """无 LLM 时使用规则生成描述。"""
        gen = ChartDescriptionGenerator()
        desc = await gen.generate_description(
            "pie", "部门", ["预算"], {}, {}
        )
        assert isinstance(desc, str)
        assert "占比" in desc

    @pytest.mark.asyncio
    async def test_generate_description_llm_failure_degrades(self) -> None:
        """LLM 失败时降级为规则描述。"""
        from unittest.mock import AsyncMock

        mock_router = AsyncMock()
        mock_router.generate.side_effect = Exception("LLM 不可用")
        gen = ChartDescriptionGenerator(llm_router=mock_router)
        desc = await gen.generate_description(
            "line", "日期", ["值"], {}, {}
        )
        assert isinstance(desc, str)
        assert "趋势" in desc
