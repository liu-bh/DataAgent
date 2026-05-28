"""业务场景：用户行为分析。

验证 NL2SQL Pipeline 在用户行为分析场景下的端到端能力，
包括 DAU 查询、留存分析、用户分层等。
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from datapilot_sqlgen.generator.models import NL2SQLResult, SemanticContext


# ---------------------------------------------------------------------------
# 用户行为场景语义上下文
# ---------------------------------------------------------------------------


@pytest.fixture
def user_behavior_context() -> SemanticContext:
    """构建用户行为分析场景的语义上下文。"""
    from datapilot_sqlgen.generator.models import (
        ColumnInfo,
        DimensionInfo,
        MetricInfo,
        SemanticContext,
        TableInfo,
        TableRelationship,
    )

    return SemanticContext(
        tables=[
            TableInfo(
                table_name="user_events",
                description="用户行为事件表",
                columns=[
                    ColumnInfo(name="id", col_type="BIGINT", description="事件 ID", is_primary_key=True),
                    ColumnInfo(name="user_id", col_type="BIGINT", description="用户 ID"),
                    ColumnInfo(name="event_type", col_type="VARCHAR(50)", description="事件类型（login/view/order/share）"),
                    ColumnInfo(name="event_date", col_type="DATE", description="事件日期"),
                    ColumnInfo(name="event_time", col_type="DATETIME", description="事件时间"),
                    ColumnInfo(name="page_url", col_type="VARCHAR(500)", description="页面 URL"),
                    ColumnInfo(name="device_type", col_type="VARCHAR(20)", description="设备类型"),
                    ColumnInfo(name="duration_seconds", col_type="INT", description="停留时长（秒）"),
                ],
            ),
            TableInfo(
                table_name="user_profiles",
                description="用户画像表",
                columns=[
                    ColumnInfo(name="id", col_type="BIGINT", description="用户 ID", is_primary_key=True),
                    ColumnInfo(name="name", col_type="VARCHAR(100)", description="用户名"),
                    ColumnInfo(name="segment", col_type="VARCHAR(30)", description="用户分层（new/active/churned/vip）"),
                    ColumnInfo(name="register_date", col_type="DATE", description="注册日期"),
                    ColumnInfo(name="total_orders", col_type="INT", description="累计订单数"),
                    ColumnInfo(name="total_spent", col_type="DECIMAL(12,2)", description="累计消费金额"),
                    ColumnInfo(name="last_active_date", col_type="DATE", description="最后活跃日期"),
                ],
            ),
        ],
        relationships=[
            TableRelationship(
                left_table="user_events",
                right_table="user_profiles",
                join_condition="user_events.user_id = user_profiles.id",
                join_type="left",
            ),
        ],
        metrics=[
            MetricInfo(name="DAU", calculation="COUNT(DISTINCT user_id)", unit="人"),
            MetricInfo(name="MAU", calculation="COUNT(DISTINCT user_id)", unit="人"),
            MetricInfo(name="人均访问时长", calculation="AVG(duration_seconds)", unit="秒"),
            MetricInfo(name="事件总数", calculation="COUNT(*)", unit="次"),
        ],
        dimensions=[
            DimensionInfo(name="事件类型", column_name="event_type", table_name="user_events"),
            DimensionInfo(name="日期", column_name="event_date", table_name="user_events"),
            DimensionInfo(name="用户分层", column_name="segment", table_name="user_profiles"),
            DimensionInfo(name="设备类型", column_name="device_type", table_name="user_events"),
        ],
        dialect="mysql",
    )


# ---------------------------------------------------------------------------
# Mock LLM 构建
# ---------------------------------------------------------------------------


def _make_mock_llm(sql: str, explanation: str, confidence: float = 0.9) -> AsyncMock:
    """构建返回指定 SQL 的 mock LLM generate 方法。"""
    return AsyncMock(return_value={
        "content": json.dumps({"sql": sql, "explanation": explanation, "confidence": confidence}, ensure_ascii=False),
        "explanation": explanation,
        "confidence": confidence,
    })


def _build_pipeline(
    mock_budget_manager: MagicMock,
    mock_intent_router: MagicMock,
    mock_intent_parser: MagicMock,
    mock_schema_linker: MagicMock,
    mock_fewshot_matcher: MagicMock,
    mock_llm: AsyncMock,
) -> Any:
    """构建 NL2SQLPipeline 实例。"""
    from datapilot_sqlgen.generator.pipeline import NL2SQLPipeline
    from datapilot_sqlgen.generator.postprocess import SQLPostProcessor
    from datapilot_sqlgen.generator.prompt_builder import PromptBuilder

    prompt_builder = PromptBuilder(budget_manager=mock_budget_manager)
    postprocessor = SQLPostProcessor()
    llm_router = MagicMock()
    llm_router.generate = mock_llm

    return NL2SQLPipeline(
        prompt_builder=prompt_builder,
        postprocessor=postprocessor,
        fewshot_matcher=mock_fewshot_matcher,
        intent_router=mock_intent_router,
        intent_parser=mock_intent_parser,
        schema_linker=mock_schema_linker,
        llm_router=llm_router,
    )


# ---------------------------------------------------------------------------
# 用户行为分析场景测试
# ---------------------------------------------------------------------------


class TestUserBehaviorScenario:
    """业务场景：用户行为分析。"""

    @pytest.mark.asyncio
    async def test_dau_query(
        self,
        user_behavior_context: SemanticContext,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
    ) -> None:
        """场景：查询日活跃用户数（DAU）。

        用户问题：「今天的 DAU 是多少？」
        预期 SQL：去重统计当日活跃用户数。
        """
        mock_llm = _make_mock_llm(
            sql=(
                "SELECT COUNT(DISTINCT user_id) AS dau "
                "FROM user_events "
                "WHERE event_date = CURRENT_DATE"
            ),
            explanation="统计今天的日活跃用户数",
            confidence=0.95,
        )

        pipeline = _build_pipeline(
            mock_budget_manager=mock_budget_manager,
            mock_intent_router=mock_intent_router,
            mock_intent_parser=mock_intent_parser,
            mock_schema_linker=mock_schema_linker,
            mock_fewshot_matcher=mock_fewshot_matcher,
            mock_llm=mock_llm,
        )

        result = await pipeline.generate(
            question="今天的 DAU 是多少？",
            session_id="ub-session-001",
            tenant_id="tenant-001",
            context=user_behavior_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "sql_query"
        assert result.sql != ""
        assert "COUNT" in result.sql.upper()
        assert "DISTINCT" in result.sql.upper()
        assert "user_id" in result.sql.lower()
        assert result.confidence > 0.8

    @pytest.mark.asyncio
    async def test_retention_analysis(
        self,
        user_behavior_context: SemanticContext,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
    ) -> None:
        """场景：用户留存分析。

        用户问题：「上个月新注册用户的次日留存率是多少？」
        预期 SQL：统计上个月注册用户中在第二天有活跃记录的比例。
        """
        mock_llm = _make_mock_llm(
            sql=(
                "SELECT "
                "  COUNT(DISTINCT CASE WHEN e2.user_id IS NOT NULL THEN p.id END) * 100.0 "
                "  / NULLIF(COUNT(DISTINCT p.id), 0) AS retention_rate "
                "FROM user_profiles p "
                "LEFT JOIN user_events e2 "
                "  ON p.id = e2.user_id "
                "  AND e2.event_date = DATE_ADD(p.register_date, INTERVAL 1 DAY) "
                "WHERE p.register_date >= '2024-04-01' "
                "  AND p.register_date < '2024-05-01' "
                "LIMIT 1"
            ),
            explanation="计算上个月新注册用户的次日留存率",
            confidence=0.87,
        )

        pipeline = _build_pipeline(
            mock_budget_manager=mock_budget_manager,
            mock_intent_router=mock_intent_router,
            mock_intent_parser=mock_intent_parser,
            mock_schema_linker=mock_schema_linker,
            mock_fewshot_matcher=mock_fewshot_matcher,
            mock_llm=mock_llm,
        )

        result = await pipeline.generate(
            question="上个月新注册用户的次日留存率是多少？",
            session_id="ub-session-002",
            tenant_id="tenant-001",
            context=user_behavior_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "sql_query"
        assert result.sql != ""
        # 留存分析 SQL 应包含 JOIN 和时间条件
        assert "JOIN" in result.sql.upper()
        assert result.confidence > 0.7

    @pytest.mark.asyncio
    async def test_user_segment(
        self,
        user_behavior_context: SemanticContext,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
    ) -> None:
        """场景：用户分层统计。

        用户问题：「各用户分层的活跃人数和平均消费金额分别是多少？」
        预期 SQL：按用户分层分组统计。
        """
        mock_llm = _make_mock_llm(
            sql=(
                "SELECT "
                "  p.segment, "
                "  COUNT(DISTINCT p.id) AS active_users, "
                "  AVG(p.total_spent) AS avg_spent "
                "FROM user_profiles p "
                "INNER JOIN user_events e ON p.id = e.user_id "
                "WHERE e.event_date >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY) "
                "GROUP BY p.segment "
                "ORDER BY active_users DESC "
                "LIMIT 50"
            ),
            explanation="按用户分层统计近 30 天活跃人数和平均消费金额",
            confidence=0.91,
        )

        pipeline = _build_pipeline(
            mock_budget_manager=mock_budget_manager,
            mock_intent_router=mock_intent_router,
            mock_intent_parser=mock_intent_parser,
            mock_schema_linker=mock_schema_linker,
            mock_fewshot_matcher=mock_fewshot_matcher,
            mock_llm=mock_llm,
        )

        result = await pipeline.generate(
            question="各用户分层的活跃人数和平均消费金额分别是多少？",
            session_id="ub-session-003",
            tenant_id="tenant-001",
            context=user_behavior_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "sql_query"
        assert result.sql != ""
        assert "segment" in result.sql.lower()
        assert "GROUP BY" in result.sql.upper()
        assert result.confidence > 0.8

        # Guardrail 验证：生成的 SQL 应通过安全检查
        from datapilot_guardrail.checker import GuardrailChecker
        checker = GuardrailChecker(redis_url="redis://nonexistent:6379/0")
        guardrail_result = await checker.check(
            sql=result.sql,
            tenant_id="tenant-001",
        )
        assert guardrail_result.passed is True
