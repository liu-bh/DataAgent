"""IntentType 枚举和 IntentRouter 规则分类单元测试。"""

from __future__ import annotations

import pytest

from datapilot_sqlgen.intent.types import IntentResult, IntentType, QueryType
from datapilot_sqlgen.intent.router import IntentRouter


class TestIntentType:
    """IntentType 枚举测试。"""

    def test_all_values(self) -> None:
        """验证所有意图类型值。"""
        assert IntentType.SQL_QUERY.value == "sql_query"
        assert IntentType.CHITCHAT.value == "chitchat"
        assert IntentType.OUT_OF_SCOPE.value == "out_of_scope"
        assert IntentType.ESCALATE_TO_HUMAN.value == "escalate_to_human"

    def test_enum_members_count(self) -> None:
        """验证枚举成员数量。"""
        assert len(IntentType) == 4

    def test_from_string(self) -> None:
        """测试从字符串创建枚举。"""
        assert IntentType("sql_query") == IntentType.SQL_QUERY
        assert IntentType("chitchat") == IntentType.CHITCHAT

    def test_invalid_string(self) -> None:
        """测试无效字符串抛出异常。"""
        with pytest.raises(ValueError):
            IntentType("invalid_type")


class TestIntentResult:
    """IntentResult 数据模型测试。"""

    def test_create_sql_query(self) -> None:
        """测试创建 SQL 查询结果。"""
        result = IntentResult(
            intent_type=IntentType.SQL_QUERY,
            confidence=0.95,
            reason="包含数据查询关键词",
            extracted_entities=["GMV"],
        )
        assert result.intent_type == IntentType.SQL_QUERY
        assert result.confidence == 0.95
        assert result.reason == "包含数据查询关键词"
        assert result.extracted_entities == ["GMV"]

    def test_default_values(self) -> None:
        """测试默认值。"""
        result = IntentResult(intent_type=IntentType.CHITCHAT)
        assert result.confidence == 0.0  # 默认 0
        assert result.reason == ""
        assert result.extracted_entities == []

    def test_confidence_bounds(self) -> None:
        """测试置信度边界。"""
        # 边界值
        r1 = IntentResult(intent_type=IntentType.SQL_QUERY, confidence=0.0)
        assert r1.confidence == 0.0

        r2 = IntentResult(intent_type=IntentType.SQL_QUERY, confidence=1.0)
        assert r2.confidence == 1.0


class TestQueryType:
    """QueryType 枚举测试。"""

    def test_all_values(self) -> None:
        """验证所有查询类型值。"""
        assert QueryType.AGGREGATION.value == "aggregation"
        assert QueryType.DETAIL.value == "detail"
        assert QueryType.RANKING.value == "ranking"
        assert QueryType.COMPARISON.value == "comparison"
        assert QueryType.TREND.value == "trend"

    def test_from_string(self) -> None:
        """测试从字符串创建枚举。"""
        assert QueryType("aggregation") == QueryType.AGGREGATION
        assert QueryType("detail") == QueryType.DETAIL


class TestIntentRouterRules:
    """IntentRouter 规则分类测试。"""

    @pytest.fixture
    def router(self) -> IntentRouter:
        """创建禁用 LLM 的路由器（仅规则匹配）。"""
        return IntentRouter(enable_llm=False, enable_cache=False)

    # ---- 数据查询分类 ----

    def test_sql_query_by_keyword_多少(self, router: IntentRouter) -> None:
        """测试"多少"关键词识别为 SQL_QUERY。"""
        result = router.classify("上个月销售额是多少？")
        assert result.intent_type == IntentType.SQL_QUERY
        assert result.confidence > 0.7

    def test_sql_query_by_keyword_统计(self, router: IntentRouter) -> None:
        """测试"统计"关键词识别为 SQL_QUERY。"""
        result = router.classify("统计各地区的订单量")
        assert result.intent_type == IntentType.SQL_QUERY

    def test_sql_query_by_keyword_排名(self, router: IntentRouter) -> None:
        """测试"排名"关键词识别为 SQL_QUERY。"""
        result = router.classify("销售额排名前10的城市")
        assert result.intent_type == IntentType.SQL_QUERY

    def test_sql_query_by_keyword_趋势(self, router: IntentRouter) -> None:
        """测试"趋势"关键词识别为 SQL_QUERY。"""
        result = router.classify("最近7天GMV趋势")
        assert result.intent_type == IntentType.SQL_QUERY

    def test_sql_query_by_keyword_对比(self, router: IntentRouter) -> None:
        """测试"对比"关键词识别为 SQL_QUERY。"""
        result = router.classify("本月和上月销售额对比")
        assert result.intent_type == IntentType.SQL_QUERY

    def test_sql_query_by_keyword_环比(self, router: IntentRouter) -> None:
        """测试"环比"关键词识别为 SQL_QUERY。"""
        result = router.classify("订单量环比增长率")
        assert result.intent_type == IntentType.SQL_QUERY

    def test_sql_query_by_keyword_合计(self, router: IntentRouter) -> None:
        """测试"合计"关键词识别为 SQL_QUERY。"""
        result = router.classify("合计所有订单的总金额")
        assert result.intent_type == IntentType.SQL_QUERY

    def test_sql_query_by_keyword_分布(self, router: IntentRouter) -> None:
        """测试"分布"关键词识别为 SQL_QUERY。"""
        result = router.classify("各地区GMV分布情况")
        assert result.intent_type == IntentType.SQL_QUERY

    def test_sql_query_by_keyword_明细(self, router: IntentRouter) -> None:
        """测试"明细"关键词识别为 SQL_QUERY。"""
        result = router.classify("查看今天的订单明细")
        assert result.intent_type == IntentType.SQL_QUERY

    def test_sql_query_by_keyword_GMV(self, router: IntentRouter) -> None:
        """测试 GMV 关键词识别为 SQL_QUERY。"""
        result = router.classify("今年的GMV是多少")
        assert result.intent_type == IntentType.SQL_QUERY

    # ---- 闲聊分类 ----

    def test_chitchat_你好(self, router: IntentRouter) -> None:
        """测试"你好"识别为 CHITCHAT。"""
        result = router.classify("你好")
        assert result.intent_type == IntentType.CHITCHAT

    def test_chitchat_谢谢(self, router: IntentRouter) -> None:
        """测试"谢谢"识别为 CHITCHAT。"""
        result = router.classify("谢谢")
        assert result.intent_type == IntentType.CHITCHAT

    def test_chitchat_早上好(self, router: IntentRouter) -> None:
        """测试"早上好"识别为 CHITCHAT。"""
        result = router.classify("早上好")
        assert result.intent_type == IntentType.CHITCHAT

    def test_chitchat_short_greeting(self, router: IntentRouter) -> None:
        """测试短问候语识别为 CHITCHAT。"""
        result = router.classify("您好")
        assert result.intent_type == IntentType.CHITCHAT

    def test_chitchat_not_triggered_by_long_input(self, router: IntentRouter) -> None:
        """测试长输入中的问候语不触发闲聊分类。"""
        # "你好"出现在长查询中，不应被判定为闲聊
        result = router.classify("你好，我想查一下上个月的销售额")
        # 应该被判定为 SQL_QUERY（包含"查询"和"销售额"）
        assert result.intent_type == IntentType.SQL_QUERY

    # ---- 超出范围分类 ----

    def test_out_of_scope_天气(self, router: IntentRouter) -> None:
        """测试"天气"识别为 OUT_OF_SCOPE。"""
        result = router.classify("今天天气怎么样？")
        assert result.intent_type == IntentType.OUT_OF_SCOPE

    def test_out_of_scope_新闻(self, router: IntentRouter) -> None:
        """测试"新闻"识别为 OUT_OF_SCOPE。"""
        result = router.classify("最近有什么新闻？")
        assert result.intent_type == IntentType.OUT_OF_SCOPE

    def test_out_of_scope_not_triggered_when_query_keyword(self, router: IntentRouter) -> None:
        """测试包含查询关键词时不判定为超出范围。"""
        # "趋势"既是查询关键词也是范围外潜在词，但应优先判定为 SQL_QUERY
        result = router.classify("销售额增长趋势")
        assert result.intent_type == IntentType.SQL_QUERY

    # ---- 转人工分类 ----

    def test_escalate_转人工(self, router: IntentRouter) -> None:
        """测试"转人工"识别为 ESCALATE_TO_HUMAN。"""
        result = router.classify("我要转人工")
        assert result.intent_type == IntentType.ESCALATE_TO_HUMAN
        assert result.confidence >= 0.9

    def test_escalate_投诉(self, router: IntentRouter) -> None:
        """测试"投诉"识别为 ESCALATE_TO_HUMAN。"""
        result = router.classify("我要投诉你们的服务")
        assert result.intent_type == IntentType.ESCALATE_TO_HUMAN

    def test_escalate_priority_over_other(self, router: IntentRouter) -> None:
        """测试转人工优先级高于其他分类。"""
        result = router.classify("我要投诉，统计一下最近的问题")
        assert result.intent_type == IntentType.ESCALATE_TO_HUMAN

    # ---- 空输入 ----

    def test_empty_input(self, router: IntentRouter) -> None:
        """测试空输入。"""
        result = router.classify("")
        assert result.intent_type == IntentType.CHITCHAT

    def test_whitespace_input(self, router: IntentRouter) -> None:
        """测试纯空格输入。"""
        result = router.classify("   ")
        assert result.intent_type == IntentType.CHITCHAT

    def test_none_like_input(self, router: IntentRouter) -> None:
        """测试空字符串。"""
        result = router.classify("")
        assert result.intent_type == IntentType.CHITCHAT
        assert result.confidence == 1.0

    # ---- 不确定输入（规则无法判定，无 LLM 时兜底） ----

    def test_uncertain_input_fallback(self, router: IntentRouter) -> None:
        """测试规则无法判定且无 LLM 时的兜底行为。"""
        result = router.classify("帮我看看数据")
        # "看看"是查询关键词，应命中 SQL_QUERY
        assert result.intent_type == IntentType.SQL_QUERY

    def test_uncertain_greeting_query_mix(self, router: IntentRouter) -> None:
        """测试混合输入的处理。"""
        result = router.classify("你好，查一下华东区的订单量")
        # 包含"查"和"订单量"关键词
        assert result.intent_type == IntentType.SQL_QUERY

    # ---- 缓存测试 ----

    def test_cache_hit(self) -> None:
        """测试缓存命中。"""
        router = IntentRouter(enable_llm=False, enable_cache=True)
        result = router.classify("你好")
        assert result.intent_type == IntentType.CHITCHAT
        assert result.confidence == 1.0
        assert result.reason == "常见问候语"

    def test_cache_miss(self) -> None:
        """测试缓存未命中。"""
        router = IntentRouter(enable_llm=False, enable_cache=True)
        result = router.classify("一条不常见的查询请求")
        # 不会命中缓存，走规则匹配
        assert result.intent_type == IntentType.SQL_QUERY  # 包含"查询"关键词

    # ---- 多关键词累加置信度 ----

    def test_multiple_keywords_increase_confidence(self, router: IntentRouter) -> None:
        """测试多个关键词命中时置信度更高。"""
        r1 = router.classify("销售额统计")
        r2 = router.classify("各地区的销售额统计排名趋势对比")
        assert r2.confidence >= r1.confidence
