"""IntentParser 结构化输出单元测试。"""

from __future__ import annotations

from datetime import date

import pytest

from datapilot_sqlgen.intent.parser import IntentParser
from datapilot_sqlgen.intent.types import (
    FilterCondition,
    ParsedIntent,
    QueryType,
    SortDirection,
    SortSpec,
    TimeRange,
)


class TestIntentParser:
    """IntentParser 测试。"""

    @pytest.fixture
    def parser(self) -> IntentParser:
        """创建禁用 LLM 的解析器（仅规则解析）。"""
        return IntentParser(enable_llm=False)

    # ---- 空输入 ----

    def test_empty_input(self, parser: IntentParser) -> None:
        """测试空输入返回默认结果。"""
        result = parser.parse("")
        assert result.query_type == QueryType.DETAIL
        assert result.limit == 100
        assert result.target_metrics == []
        assert result.raw_question == ""

    def test_none_like_input(self, parser: IntentParser) -> None:
        """测试空格输入。"""
        result = parser.parse("   ")
        assert result.query_type == QueryType.DETAIL

    # ---- 查询类型检测 ----

    def test_detect_aggregation(self, parser: IntentParser) -> None:
        """测试聚合查询类型检测。"""
        result = parser.parse("统计各地区的总销售额")
        assert result.query_type == QueryType.AGGREGATION

    def test_detect_detail(self, parser: IntentParser) -> None:
        """测试明细查询类型检测（默认）。"""
        result = parser.parse("查看订单列表")
        assert result.query_type == QueryType.DETAIL

    def test_detect_ranking(self, parser: IntentParser) -> None:
        """测试排名查询类型检测。"""
        result = parser.parse("销售额排名前10的城市")
        assert result.query_type == QueryType.RANKING

    def test_detect_comparison(self, parser: IntentParser) -> None:
        """测试对比查询类型检测。"""
        result = parser.parse("本月和上月销售额对比")
        assert result.query_type == QueryType.COMPARISON

    def test_detect_trend(self, parser: IntentParser) -> None:
        """测试趋势查询类型检测。"""
        result = parser.parse("最近7天GMV增长趋势")
        assert result.query_type == QueryType.TREND

    def test_detect_trend_by_keyword_变化(self, parser: IntentParser) -> None:
        """测试"变化"关键词触发趋势查询。"""
        result = parser.parse("用户数的变化情况")
        assert result.query_type == QueryType.TREND

    def test_detect_trend_by_keyword_下降(self, parser: IntentParser) -> None:
        """测试"下降"关键词触发趋势查询。"""
        result = parser.parse("利润率下降趋势")
        assert result.query_type == QueryType.TREND

    # ---- 时间范围解析 ----

    def test_parse_time_today(self, parser: IntentParser) -> None:
        """测试解析"今天"。"""
        result = parser.parse("今天的订单量")
        assert result.time_range.raw_text == "今天"
        assert result.time_range.start == date.today()
        assert result.time_range.end == date.today()
        assert result.time_range.granularity == "day"

    def test_parse_time_yesterday(self, parser: IntentParser) -> None:
        """测试解析"昨天"。"""
        result = parser.parse("昨天的销售额")
        assert result.time_range.raw_text == "昨天"
        assert result.time_range.granularity == "day"

    def test_parse_time_this_month(self, parser: IntentParser) -> None:
        """测试解析"本月"。"""
        result = parser.parse("本月的GMV")
        assert result.time_range.raw_text == "本月"
        assert result.time_range.start is not None
        assert result.time_range.start.day == 1

    def test_parse_time_last_month(self, parser: IntentParser) -> None:
        """测试解析"上月"。"""
        result = parser.parse("上月华东区销售额")
        assert result.time_range.raw_text == "上月"
        assert result.time_range.granularity == "month"

    def test_parse_time_this_year(self, parser: IntentParser) -> None:
        """测试解析"今年"。"""
        result = parser.parse("今年的总订单量")
        assert result.time_range.raw_text == "今年"
        assert result.time_range.start is not None
        assert result.time_range.start.month == 1
        assert result.time_range.start.day == 1

    def test_parse_time_last_year(self, parser: IntentParser) -> None:
        """测试解析"去年"。"""
        result = parser.parse("去年的利润")
        assert result.time_range.raw_text == "去年"
        assert result.time_range.granularity == "month"

    def test_parse_time_last_n_days(self, parser: IntentParser) -> None:
        """测试解析"最近N天"。"""
        result = parser.parse("最近7天的订单趋势")
        assert result.time_range.raw_text == "最近7天"
        assert result.time_range.end == date.today()

    def test_parse_time_quarter(self, parser: IntentParser) -> None:
        """测试解析季度。"""
        result = parser.parse("今年Q1的GMV")
        assert "Q1" in result.time_range.raw_text
        assert result.time_range.granularity == "quarter"

    def test_parse_time_no_time(self, parser: IntentParser) -> None:
        """测试无时间描述时不生成时间范围。"""
        result = parser.parse("华东区的销售额")
        assert result.time_range.raw_text == ""

    # ---- LIMIT 解析 ----

    def test_parse_limit_top_n(self, parser: IntentParser) -> None:
        """测试解析 top N。"""
        result = parser.parse("top 10 销售城市")
        assert result.limit == 10

    def test_parse_limit_前n(self, parser: IntentParser) -> None:
        """测试解析"前N"。"""
        result = parser.parse("销售额排名前20")
        assert result.limit == 20

    def test_parse_limit_n条(self, parser: IntentParser) -> None:
        """测试解析"N条"。"""
        result = parser.parse("最近50条订单")
        assert result.limit == 50

    def test_parse_limit_default(self, parser: IntentParser) -> None:
        """测试默认 LIMIT。"""
        result = parser.parse("今天的订单量")
        assert result.limit == 100

    def test_parse_limit_exceeds_max(self, parser: IntentParser) -> None:
        """测试 LIMIT 超过最大值被截断。"""
        result = parser.parse("前99999条记录")
        assert result.limit <= 10000

    # ---- 排序解析 ----

    def test_parse_sort_desc(self, parser: IntentParser) -> None:
        """测试降序解析。"""
        result = parser.parse("销售额从高到低排名")
        assert len(result.sort_by) > 0
        assert result.sort_by[0].direction == SortDirection.DESC

    def test_parse_sort_asc(self, parser: IntentParser) -> None:
        """测试升序解析。"""
        result = parser.parse("按金额从低到高排列")
        assert len(result.sort_by) > 0
        assert result.sort_by[0].direction == SortDirection.ASC

    def test_parse_sort_降序(self, parser: IntentParser) -> None:
        """测试"降序"关键词。"""
        result = parser.parse("GMV降序排列")
        assert len(result.sort_by) > 0
        assert result.sort_by[0].direction == SortDirection.DESC

    # ---- 过滤条件解析 ----

    def test_parse_filter_region(self, parser: IntentParser) -> None:
        """测试地区过滤条件。"""
        result = parser.parse("华东区销售额")
        assert any(f.value == "华东" for f in result.filters)

    def test_parse_filter_amount_gt(self, parser: IntentParser) -> None:
        """测试金额大于过滤条件。"""
        result = parser.parse("金额大于1000的订单")
        assert any(f.column == "amount" and f.operator == ">" for f in result.filters)

    def test_parse_filter_amount_lt(self, parser: IntentParser) -> None:
        """测试金额小于过滤条件。"""
        result = parser.parse("金额<500的订单")
        assert any(f.column == "amount" and f.operator == "<" for f in result.filters)

    # ---- 指标/维度关键词提取 ----

    def test_extract_metric_GMV(self, parser: IntentParser) -> None:
        """测试提取 GMV 指标。"""
        result = parser.parse("各地区的GMV")
        assert "GMV" in result.target_metrics

    def test_extract_metric_销售额(self, parser: IntentParser) -> None:
        """测试提取销售额指标。"""
        result = parser.parse("统计销售额")
        assert "销售额" in result.target_metrics

    def test_extract_dimension_地区(self, parser: IntentParser) -> None:
        """测试提取地区维度。"""
        result = parser.parse("各地区的销售额")
        assert "地区" in result.target_dimensions

    def test_extract_dimension_时间(self, parser: IntentParser) -> None:
        """测试提取时间维度。"""
        result = parser.parse("按时间统计订单量")
        assert "时间" in result.target_dimensions

    # ---- 综合测试 ----

    def test_complex_query(self, parser: IntentParser) -> None:
        """测试复杂查询的综合解析。"""
        result = parser.parse("上月华东区GMV排名前10")
        assert result.query_type == QueryType.RANKING
        assert result.time_range.raw_text == "上月"
        assert result.limit == 10
        assert "GMV" in result.target_metrics
        assert any(f.value == "华东" for f in result.filters)
        assert "地区" in result.target_dimensions

    def test_raw_question_preserved(self, parser: IntentParser) -> None:
        """测试原始问题被保留。"""
        question = "今天的订单量是多少？"
        result = parser.parse(question)
        assert result.raw_question == question


class TestIntentParserLLMFallback:
    """IntentParser LLM 回退行为测试。"""

    def test_llm_disabled_uses_rules(self) -> None:
        """测试 LLM 禁用时使用规则解析。"""
        parser = IntentParser(enable_llm=False)
        result = parser.parse("上月华东区GMV")
        # "上月华东区GMV" 无显式聚合关键词，规则应能解析时间、过滤、指标
        assert result.time_range.raw_text == "上月"
        assert result.raw_question == "上月华东区GMV"

    def test_llm_enabled_but_import_fails(self) -> None:
        """测试 LLM 启用但 import 失败时回退到规则。"""
        parser = IntentParser(enable_llm=True)
        # 由于 datapilot_llm 未安装，应自动回退
        result = parser.parse("上月销售额统计")
        assert result is not None
        assert result.raw_question == "上月销售额统计"

    def test_parse_with_context(self) -> None:
        """测试带上下文消息的解析。"""
        parser = IntentParser(enable_llm=False)
        context = [
            {"role": "user", "content": "华东区销售额是多少？"},
            {"role": "assistant", "content": "华东区销售额为 1000 万"},
        ]
        result = parser.parse("那华南区呢？", context=context)
        # 规则模式下上下文不影响结果
        assert result.raw_question == "那华南区呢？"


class TestParsedIntentModel:
    """ParsedIntent Pydantic 模型测试。"""

    def test_model_creation(self) -> None:
        """测试模型创建。"""
        intent = ParsedIntent(
            query_type=QueryType.AGGREGATION,
            target_metrics=["GMV"],
            target_dimensions=["地区"],
            limit=10,
        )
        assert intent.query_type == QueryType.AGGREGATION
        assert intent.target_metrics == ["GMV"]
        assert intent.limit == 10

    def test_model_defaults(self) -> None:
        """测试模型默认值。"""
        intent = ParsedIntent()
        assert intent.query_type == QueryType.DETAIL
        assert intent.target_metrics == []
        assert intent.target_dimensions == []
        assert intent.limit == 100
        assert intent.raw_question == ""
        assert intent.time_range == TimeRange()
        assert intent.filters == []
        assert intent.sort_by == []

    def test_model_from_attributes(self) -> None:
        """测试 from_attributes 配置。"""
        intent = ParsedIntent()
        # 验证 model_config 允许 from_attributes
        assert intent.model_config.get("from_attributes") is True

    def test_limit_validation_min(self) -> None:
        """测试 limit 最小值约束。"""
        # limit 应 >= 1
        intent = ParsedIntent(limit=1)
        assert intent.limit == 1

    def test_limit_validation_max(self) -> None:
        """测试 limit 最大值约束。"""
        # limit 应 <= 10000
        intent = ParsedIntent(limit=10000)
        assert intent.limit == 10000
