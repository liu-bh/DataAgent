"""NL2SQL Pipeline 编排器单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datapilot_sqlgen.generator.models import (
    FewShotExample,
    NL2SQLResult,
    SemanticContext,
)
from datapilot_sqlgen.generator.pipeline import NL2SQLPipeline
from datapilot_sqlgen.generator.prompt_builder import PromptBuilder
from datapilot_sqlgen.generator.postprocess import SQLPostProcessor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def prompt_builder(mock_budget_manager: MagicMock) -> PromptBuilder:
    """创建 PromptBuilder 实例。"""
    return PromptBuilder(budget_manager=mock_budget_manager)


@pytest.fixture
def postprocessor() -> SQLPostProcessor:
    """创建 SQLPostProcessor 实例。"""
    return SQLPostProcessor()


@pytest.fixture
def pipeline(
    prompt_builder: PromptBuilder,
    postprocessor: SQLPostProcessor,
    mock_llm_router: MagicMock,
    mock_intent_router: MagicMock,
    mock_intent_parser: MagicMock,
    mock_schema_linker: MagicMock,
    mock_fewshot_matcher: MagicMock,
) -> NL2SQLPipeline:
    """创建 NL2SQLPipeline 实例（所有依赖已 mock）。"""
    return NL2SQLPipeline(
        prompt_builder=prompt_builder,
        postprocessor=postprocessor,
        fewshot_matcher=mock_fewshot_matcher,
        intent_router=mock_intent_router,
        intent_parser=mock_intent_parser,
        schema_linker=mock_schema_linker,
        llm_router=mock_llm_router,
    )


# ---------------------------------------------------------------------------
# 完整流程测试
# ---------------------------------------------------------------------------


class TestPipelineFullFlow:
    """Pipeline 完整流程测试。"""

    @pytest.mark.asyncio
    async def test_sql_query_flow(
        self,
        pipeline: NL2SQLPipeline,
        sample_semantic_context: SemanticContext,
        session_id: str,
        tenant_id: str,
    ) -> None:
        """SQL 查询意图的完整流程。"""
        result = await pipeline.generate(
            question="上个月销售额是多少？",
            session_id=session_id,
            tenant_id=tenant_id,
            context=sample_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "sql_query"
        assert result.sql != ""
        assert result.sql_dialect == "mysql"
        assert result.confidence > 0
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_chitchat_flow(
        self,
        pipeline: NL2SQLPipeline,
        session_id: str,
        tenant_id: str,
    ) -> None:
        """闲聊意图应返回文本回复而非 SQL。"""
        # 修改 intent router 返回闲聊
        pipeline._intent_router.route = MagicMock(return_value={
            "intent": "chitchat",
            "confidence": 0.9,
        })

        result = await pipeline.generate(
            question="你好",
            session_id=session_id,
            tenant_id=tenant_id,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "chitchat"
        assert result.sql == ""
        assert result.text_response != ""

    @pytest.mark.asyncio
    async def test_out_of_scope_flow(
        self,
        pipeline: NL2SQLPipeline,
        session_id: str,
        tenant_id: str,
    ) -> None:
        """超出范围应返回友好提示。"""
        pipeline._intent_router.route = MagicMock(return_value={
            "intent": "out_of_scope",
            "confidence": 0.85,
        })

        result = await pipeline.generate(
            question="今天天气怎么样？",
            session_id=session_id,
            tenant_id=tenant_id,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "out_of_scope"
        assert result.sql == ""
        assert result.text_response != ""
        assert "超出" in result.text_response or "范围" in result.text_response


# ---------------------------------------------------------------------------
# 意图路由测试
# ---------------------------------------------------------------------------


class TestIntentRouting:
    """意图路由逻辑测试。"""

    @pytest.mark.asyncio
    async def test_rule_based_greeting(
        self,
        pipeline: NL2SQLPipeline,
    ) -> None:
        """规则引擎应识别问候语为闲聊。"""
        # 不使用 intent router，测试降级逻辑
        pipeline._intent_router = None

        intent, confidence = pipeline._rule_based_intent_route("你好")
        assert intent == "chitchat"
        assert confidence > 0

    @pytest.mark.asyncio
    async def test_rule_based_sql_keywords(
        self,
        pipeline: NL2SQLPipeline,
    ) -> None:
        """包含数据查询关键词应识别为 SQL 查询。"""
        pipeline._intent_router = None

        intent, confidence = pipeline._rule_based_intent_route("上个月销售额是多少")
        assert intent == "sql_query"

    @pytest.mark.asyncio
    async def test_rule_based_default(
        self,
        pipeline: NL2SQLPipeline,
    ) -> None:
        """默认应识别为 SQL 查询。"""
        pipeline._intent_router = None

        intent, confidence = pipeline._rule_based_intent_route("一些不明确的问题")
        assert intent == "sql_query"

    @pytest.mark.asyncio
    async def test_intent_router_failure_fallback(
        self,
        pipeline: NL2SQLPipeline,
        session_id: str,
        tenant_id: str,
    ) -> None:
        """意图路由器失败时应降级为规则路由。"""
        pipeline._intent_router.route = MagicMock(side_effect=Exception("LLM 不可用"))

        result = await pipeline.generate(
            question="订单量多少",
            session_id=session_id,
            tenant_id=tenant_id,
        )

        assert result.intent == "sql_query"


# ---------------------------------------------------------------------------
# 无依赖降级测试
# ---------------------------------------------------------------------------


class TestPipelineDegradation:
    """Pipeline 依赖缺失时的降级行为测试。"""

    @pytest.mark.asyncio
    async def test_no_llm_router_returns_placeholder(
        self,
        pipeline: NL2SQLPipeline,
        sample_semantic_context: SemanticContext,
        session_id: str,
        tenant_id: str,
    ) -> None:
        """没有 LLM 路由器时应返回占位 SQL。"""
        pipeline._llm_router = None

        result = await pipeline.generate(
            question="订单量多少",
            session_id=session_id,
            tenant_id=tenant_id,
            context=sample_semantic_context,
        )

        assert result.sql != ""
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_no_fewshot_matcher_continues(
        self,
        pipeline: NL2SQLPipeline,
        sample_semantic_context: SemanticContext,
        session_id: str,
        tenant_id: str,
    ) -> None:
        """没有 Few-shot 匹配器时应继续执行流程。"""
        pipeline._fewshot_matcher = None

        result = await pipeline.generate(
            question="订单量多少",
            session_id=session_id,
            tenant_id=tenant_id,
            context=sample_semantic_context,
        )

        assert result.sql != ""
        assert result.used_few_shots == []

    @pytest.mark.asyncio
    async def test_no_schema_linker_uses_full_context(
        self,
        pipeline: NL2SQLPipeline,
        sample_semantic_context: SemanticContext,
        session_id: str,
        tenant_id: str,
    ) -> None:
        """没有 Schema Linker 时应使用完整上下文。"""
        pipeline._schema_linker = None

        result = await pipeline.generate(
            question="订单量多少",
            session_id=session_id,
            tenant_id=tenant_id,
            context=sample_semantic_context,
        )

        assert result.sql != ""

    @pytest.mark.asyncio
    async def test_no_context_defaults(
        self,
        pipeline: NL2SQLPipeline,
        session_id: str,
        tenant_id: str,
    ) -> None:
        """不提供语义上下文时应使用默认空上下文。"""
        result = await pipeline.generate(
            question="订单量多少",
            session_id=session_id,
            tenant_id=tenant_id,
        )

        # 应该不报错，正常返回结果
        assert isinstance(result, NL2SQLResult)
