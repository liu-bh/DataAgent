"""图表推荐 Prompt 模板单元测试。"""

from __future__ import annotations

from datapilot_agent.chart.prompts import (
    CHART_DESCRIPTION_PROMPT,
    CHART_RECOMMEND_PROMPT,
    CHART_TITLE_PROMPT,
)


class TestChartRecommendPrompt:
    """图表推荐 Prompt 模板测试。"""

    def test_recommend_prompt_has_placeholder(self) -> None:
        """推荐 Prompt 包含所有必要占位符。"""
        assert "{columns}" in CHART_RECOMMEND_PROMPT
        assert "{row_count}" in CHART_RECOMMEND_PROMPT
        assert "{question}" in CHART_RECOMMEND_PROMPT

    def test_recommend_prompt_mentions_chart_types(self) -> None:
        """推荐 Prompt 提及常见图表类型。"""
        assert "line" in CHART_RECOMMEND_PROMPT
        assert "bar" in CHART_RECOMMEND_PROMPT
        assert "pie" in CHART_RECOMMEND_PROMPT
        assert "scatter" in CHART_RECOMMEND_PROMPT
        assert "table" in CHART_RECOMMEND_PROMPT

    def test_recommend_prompt_asks_json_format(self) -> None:
        """推荐 Prompt 要求 JSON 格式输出。"""
        assert "JSON" in CHART_RECOMMEND_PROMPT
        assert "confidence" in CHART_RECOMMEND_PROMPT

    def test_recommend_prompt_format_successful(self) -> None:
        """推荐 Prompt 格式化成功。"""
        formatted = CHART_RECOMMEND_PROMPT.format(
            columns="[{'name': 'date', 'type': 'date'}]",
            row_count=10,
            question="销售趋势",
        )
        assert "date" in formatted
        assert "10" in formatted
        assert "销售趋势" in formatted

    def test_recommend_prompt_empty_question(self) -> None:
        """空问题也能成功格式化。"""
        formatted = CHART_RECOMMEND_PROMPT.format(
            columns="[]",
            row_count=0,
            question="无",
        )
        assert "无" in formatted


class TestChartDescriptionPrompt:
    """图表描述 Prompt 模板测试。"""

    def test_description_prompt_has_placeholders(self) -> None:
        """描述 Prompt 包含所有必要占位符。"""
        assert "{chart_type}" in CHART_DESCRIPTION_PROMPT
        assert "{x_field}" in CHART_DESCRIPTION_PROMPT
        assert "{y_fields}" in CHART_DESCRIPTION_PROMPT
        assert "{data_summary}" in CHART_DESCRIPTION_PROMPT
        assert "{result_stats}" in CHART_DESCRIPTION_PROMPT

    def test_description_prompt_has_constraints(self) -> None:
        """描述 Prompt 包含长度约束。"""
        assert "100" in CHART_DESCRIPTION_PROMPT

    def test_description_prompt_format_successful(self) -> None:
        """描述 Prompt 格式化成功。"""
        formatted = CHART_DESCRIPTION_PROMPT.format(
            chart_type="折线图",
            x_field="日期",
            y_fields="销售额",
            data_summary="共12条记录",
            result_stats="avg=3000",
        )
        assert "折线图" in formatted
        assert "日期" in formatted
        assert "销售额" in formatted


class TestChartTitlePrompt:
    """图表标题 Prompt 模板测试。"""

    def test_title_prompt_has_placeholders(self) -> None:
        """标题 Prompt 包含所有必要占位符。"""
        assert "{chart_type}" in CHART_TITLE_PROMPT
        assert "{x_field}" in CHART_TITLE_PROMPT
        assert "{y_fields}" in CHART_TITLE_PROMPT
        assert "{data_summary}" in CHART_TITLE_PROMPT

    def test_title_prompt_has_constraints(self) -> None:
        """标题 Prompt 包含长度约束。"""
        assert "20" in CHART_TITLE_PROMPT

    def test_title_prompt_format_successful(self) -> None:
        """标题 Prompt 格式化成功。"""
        formatted = CHART_TITLE_PROMPT.format(
            chart_type="柱状图",
            x_field="区域",
            y_fields="销售额, 利润",
            data_summary="共4个区域",
        )
        assert "柱状图" in formatted
        assert "区域" in formatted
