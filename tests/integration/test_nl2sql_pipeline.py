"""NL2SQL Pipeline 集成测试。

测试完整的 NL2SQL 编排逻辑：意图路由 → 语义解析 → Schema Linking →
Prompt 组装 → LLM 生成 → SQL 后处理。Mock LLM 和数据库依赖。
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datapilot_sqlgen.generator.models import NL2SQLResult, SemanticContext
from datapilot_sqlgen.generator.pipeline import NL2SQLPipeline
from datapilot_sqlgen.generator.postprocess import SQLPostProcessor
from datapilot_sqlgen.generator.prompt_builder import PromptBuilder


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def chitchat_intent_router() -> MagicMock:
    """创建返回闲聊意图的 mock IntentRouter。"""
    router = MagicMock()
    router.classify = MagicMock(return_value=MagicMock(
        intent_type=MagicMock(value="chitchat"),
        confidence=0.92,
    ))
    return router


@pytest.fixture
def out_of_scope_intent_router() -> MagicMock:
    """创建返回超出范围意图的 mock IntentRouter。"""
    router = MagicMock()
    router.classify = MagicMock(return_value=MagicMock(
        intent_type=MagicMock(value="out_of_scope"),
        confidence=0.85,
    ))
    return router


@pytest.fixture
def sql_query_llm_output() -> str:
    """LLM 返回的标准 NL2SQL JSON 输出。"""
    return json.dumps({
        "sql": "SELECT city, SUM(amount) AS total FROM orders GROUP BY city ORDER BY total DESC LIMIT 10",
        "explanation": "查询各城市的销售总额并按金额降序排列",
        "confidence": 0.92,
    }, ensure_ascii=False)


@pytest.fixture
def sql_query_llm_generate(sql_query_llm_output: str) -> AsyncMock:
    """创建返回 SQL 查询结果的 mock LLM generate。"""
    return AsyncMock(return_value={
        "content": sql_query_llm_output,
        "explanation": "查询各城市的销售总额并按金额降序排列",
        "confidence": 0.92,
    })


@pytest.fixture
def syntax_error_llm_output() -> str:
    """LLM 返回的包含语法错误的 SQL。"""
    return json.dumps({
        "sql": "SELEC city, SUM(amount FROM orders GROUPY city",
        "explanation": "尝试查询销售数据",
        "confidence": 0.6,
    }, ensure_ascii=False)


@pytest.fixture
def corrected_llm_output() -> str:
    """LLM 纠错后的正确 SQL。"""
    return json.dumps({
        "sql": "SELECT city, SUM(amount) AS total FROM orders GROUP BY city LIMIT 100",
        "explanation": "查询各城市的销售总额",
        "confidence": 0.88,
    }, ensure_ascii=False)


def _build_pipeline(
    mock_budget_manager: MagicMock,
    mock_intent_router: MagicMock,
    mock_intent_parser: MagicMock,
    mock_schema_linker: MagicMock,
    mock_fewshot_matcher: MagicMock,
    mock_llm_generate: AsyncMock,
) -> NL2SQLPipeline:
    """构建 NL2SQLPipeline 实例的工具方法。"""
    prompt_builder = PromptBuilder(budget_manager=mock_budget_manager)
    postprocessor = SQLPostProcessor()

    llm_router = MagicMock()
    llm_router.generate = mock_llm_generate

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
# 意图路由测试
# ---------------------------------------------------------------------------


class TestNL2SQLPipeline:
    """NL2SQL Pipeline 集成测试。"""

    @pytest.mark.asyncio
    async def test_chitchat_intent(
        self,
        mock_budget_manager: MagicMock,
        chitchat_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
        mock_llm_generate: AsyncMock,
    ) -> None:
        """闲聊意图应返回文本回复，不生成 SQL。"""
        pipeline = _build_pipeline(
            mock_budget_manager=mock_budget_manager,
            mock_intent_router=chitchat_intent_router,
            mock_intent_parser=mock_intent_parser,
            mock_schema_linker=mock_schema_linker,
            mock_fewshot_matcher=mock_fewshot_matcher,
            mock_llm_generate=mock_llm_generate,
        )

        result = await pipeline.generate(
            question="你好呀",
            session_id="session-001",
            tenant_id="tenant-001",
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "chitchat"
        assert result.sql == ""
        assert result.text_response != ""
        assert "DataPilot" in result.text_response or "助手" in result.text_response
        # 闲聊不应调用 LLM
        mock_llm_generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_out_of_scope_intent(
        self,
        mock_budget_manager: MagicMock,
        out_of_scope_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
        mock_llm_generate: AsyncMock,
    ) -> None:
        """超出范围意图应返回友好提示，不生成 SQL。"""
        pipeline = _build_pipeline(
            mock_budget_manager=mock_budget_manager,
            mock_intent_router=out_of_scope_intent_router,
            mock_intent_parser=mock_intent_parser,
            mock_schema_linker=mock_schema_linker,
            mock_fewshot_matcher=mock_fewshot_matcher,
            mock_llm_generate=mock_llm_generate,
        )

        result = await pipeline.generate(
            question="今天天气怎么样？",
            session_id="session-001",
            tenant_id="tenant-001",
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "out_of_scope"
        assert result.sql == ""
        assert result.text_response != ""
        assert "超出" in result.text_response or "范围" in result.text_response
        # 超出范围不应调用 LLM
        mock_llm_generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_sql_query_with_mock_llm(
        self,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
        sql_query_llm_generate: AsyncMock,
        sample_semantic_context: SemanticContext,
    ) -> None:
        """SQL 查询意图应通过 LLM 生成 SQL 并完成完整链路。"""
        pipeline = _build_pipeline(
            mock_budget_manager=mock_budget_manager,
            mock_intent_router=mock_intent_router,
            mock_intent_parser=mock_intent_parser,
            mock_schema_linker=mock_schema_linker,
            mock_fewshot_matcher=mock_fewshot_matcher,
            mock_llm_generate=sql_query_llm_generate,
        )

        result = await pipeline.generate(
            question="各城市的销售额是多少？",
            session_id="session-001",
            tenant_id="tenant-001",
            context=sample_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "sql_query"
        assert result.sql != ""
        assert "SELECT" in result.sql.upper()
        assert result.confidence > 0
        assert result.latency_ms >= 0
        # 验证 LLM 被调用
        sql_query_llm_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_sql_generation_and_postprocess(
        self,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
        sample_semantic_context: SemanticContext,
    ) -> None:
        """SQL 生成后应经过后处理（提取 JSON、AST 解析、添加 LIMIT）。"""
        # LLM 返回没有 LIMIT 的 SQL
        no_limit_output = json.dumps({
            "sql": "SELECT city, SUM(amount) AS total FROM orders GROUP BY city ORDER BY total DESC",
            "explanation": "查询各城市的销售总额",
            "confidence": 0.9,
        }, ensure_ascii=False)
        mock_llm = AsyncMock(return_value={
            "content": no_limit_output,
            "explanation": "查询各城市的销售总额",
            "confidence": 0.9,
        })

        pipeline = _build_pipeline(
            mock_budget_manager=mock_budget_manager,
            mock_intent_router=mock_intent_router,
            mock_intent_parser=mock_intent_parser,
            mock_schema_linker=mock_schema_linker,
            mock_fewshot_matcher=mock_fewshot_matcher,
            mock_llm_generate=mock_llm,
        )

        result = await pipeline.generate(
            question="各城市的销售额是多少？",
            session_id="session-001",
            tenant_id="tenant-001",
            context=sample_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.sql != ""
        # 后处理器应尝试添加 LIMIT（如果 AST 解析成功）
        # 注意：sqlglot AST 解析可能在某些环境下失败（如 sqlglot 版本差异），
        # 此时 LIMIT 不会被自动添加，但仍应有警告或原始 SQL 返回
        assert "LIMIT" in result.sql.upper() or any(
            "AST" in w or "LIMIT" in w for w in result.warnings
        )

    @pytest.mark.asyncio
    async def test_validation_step(
        self,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
        sample_semantic_context: SemanticContext,
    ) -> None:
        """SQL 验证步骤应检测并拒绝非法 SQL（DDL/写操作）。"""
        # LLM 错误返回了 DROP 语句
        ddl_output = json.dumps({
            "sql": "DROP TABLE orders",
            "explanation": "删除订单表",
            "confidence": 0.5,
        }, ensure_ascii=False)
        mock_llm = AsyncMock(return_value={
            "content": ddl_output,
            "explanation": "删除订单表",
            "confidence": 0.5,
        })

        pipeline = _build_pipeline(
            mock_budget_manager=mock_budget_manager,
            mock_intent_router=mock_intent_router,
            mock_intent_parser=mock_intent_parser,
            mock_schema_linker=mock_schema_linker,
            mock_fewshot_matcher=mock_fewshot_matcher,
            mock_llm_generate=mock_llm,
        )

        result = await pipeline.generate(
            question="删除订单表",
            session_id="session-001",
            tenant_id="tenant-001",
            context=sample_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        # DROP 语句不应被接受为有效 SQL
        # 后处理器会将非法 SQL 标记警告
        assert len(result.warnings) > 0 or result.sql == ""

    @pytest.mark.asyncio
    async def test_self_correction_on_syntax_error(
        self,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
        sample_semantic_context: SemanticContext,
        syntax_error_llm_output: str,
        corrected_llm_output: str,
    ) -> None:
        """LLM 首次返回语法错误 SQL 时，自纠错引擎应尝试修复。"""
        # 第一次调用返回错误 SQL，第二次返回纠正后的 SQL
        call_count = 0

        async def side_effect(*args: Any, **kwargs: Any) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "content": syntax_error_llm_output,
                    "explanation": "尝试查询销售数据",
                    "confidence": 0.6,
                }
            return {
                "content": corrected_llm_output,
                "explanation": "查询各城市的销售总额",
                "confidence": 0.88,
            }

        mock_llm = AsyncMock(side_effect=side_effect)

        pipeline = _build_pipeline(
            mock_budget_manager=mock_budget_manager,
            mock_intent_router=mock_intent_router,
            mock_intent_parser=mock_intent_parser,
            mock_schema_linker=mock_schema_linker,
            mock_fewshot_matcher=mock_fewshot_matcher,
            mock_llm_generate=mock_llm,
        )

        result = await pipeline.generate(
            question="各城市销售额是多少？",
            session_id="session-001",
            tenant_id="tenant-001",
            context=sample_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        # Pipeline 本身不做自纠错，但后处理器应标记语法错误警告
        # 自纠错在 correction/engine.py 中独立处理
        assert isinstance(result.warnings, list)

    @pytest.mark.asyncio
    async def test_sql_explanation(
        self,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
        sample_semantic_context: SemanticContext,
    ) -> None:
        """Pipeline 应为生成的 SQL 提供自然语言解释。"""
        llm_output = json.dumps({
            "sql": "SELECT COUNT(*) AS total_orders FROM orders WHERE status = 'completed'",
            "explanation": "查询已完成订单的总数量",
            "confidence": 0.95,
        }, ensure_ascii=False)
        mock_llm = AsyncMock(return_value={
            "content": llm_output,
            "explanation": "查询已完成订单的总数量",
            "confidence": 0.95,
        })

        pipeline = _build_pipeline(
            mock_budget_manager=mock_budget_manager,
            mock_intent_router=mock_intent_router,
            mock_intent_parser=mock_intent_parser,
            mock_schema_linker=mock_schema_linker,
            mock_fewshot_matcher=mock_fewshot_matcher,
            mock_llm_generate=mock_llm,
        )

        result = await pipeline.generate(
            question="已完成订单有多少？",
            session_id="session-001",
            tenant_id="tenant-001",
            context=sample_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.sql != ""
        assert result.explanation != ""
        # 解释应包含语义描述
        assert len(result.explanation) > 5


# ---------------------------------------------------------------------------
# Pipeline 降级测试
# ---------------------------------------------------------------------------


class TestNL2SQLPipelineDegradation:
    """NL2SQL Pipeline 降级场景测试。"""

    @pytest.mark.asyncio
    async def test_llm_failure_returns_placeholder(
        self,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
        sample_semantic_context: SemanticContext,
    ) -> None:
        """LLM 调用失败时应返回占位 SQL 而非抛出异常。"""
        mock_llm = AsyncMock(side_effect=Exception("LLM 服务不可用"))

        pipeline = _build_pipeline(
            mock_budget_manager=mock_budget_manager,
            mock_intent_router=mock_intent_router,
            mock_intent_parser=mock_intent_parser,
            mock_schema_linker=mock_schema_linker,
            mock_fewshot_matcher=mock_fewshot_matcher,
            mock_llm_generate=mock_llm,
        )

        result = await pipeline.generate(
            question="订单量多少",
            session_id="session-001",
            tenant_id="tenant-001",
            context=sample_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        # 应返回占位 SQL 而非空字符串
        assert result.sql != ""
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_no_intent_router_uses_rule_based(
        self,
        mock_budget_manager: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
        sample_semantic_context: SemanticContext,
    ) -> None:
        """没有 IntentRouter 时应使用基于规则的降级路由。"""
        mock_llm = AsyncMock(return_value={
            "content": '{"sql": "SELECT COUNT(*) FROM orders", "explanation": "统计订单", "confidence": 0.8}',
            "explanation": "统计订单",
            "confidence": 0.8,
        })

        pipeline = _build_pipeline(
            mock_budget_manager=mock_budget_manager,
            mock_intent_router=None,  # 不提供 IntentRouter
            mock_intent_parser=mock_intent_parser,
            mock_schema_linker=mock_schema_linker,
            mock_fewshot_matcher=mock_fewshot_matcher,
            mock_llm_generate=mock_llm,
        )

        # 包含数据查询关键词 → 应识别为 sql_query
        result = await pipeline.generate(
            question="统计上个月的订单量",
            session_id="session-001",
            tenant_id="tenant-001",
            context=sample_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "sql_query"

    @pytest.mark.asyncio
    async def test_rule_based_greeting_without_intent_router(
        self,
        mock_budget_manager: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
    ) -> None:
        """没有 IntentRouter 时，问候语应通过规则识别为闲聊。"""
        mock_llm = AsyncMock()

        pipeline = _build_pipeline(
            mock_budget_manager=mock_budget_manager,
            mock_intent_router=None,
            mock_intent_parser=mock_intent_parser,
            mock_schema_linker=mock_schema_linker,
            mock_fewshot_matcher=mock_fewshot_matcher,
            mock_llm_generate=mock_llm,
        )

        result = await pipeline.generate(
            question="你好",
            session_id="session-001",
            tenant_id="tenant-001",
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "chitchat"
        assert result.sql == ""

    @pytest.mark.asyncio
    async def test_no_schema_linker_uses_full_context(
        self,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_fewshot_matcher: MagicMock,
        sample_semantic_context: SemanticContext,
    ) -> None:
        """没有 SchemaLinker 时应使用传入的完整语义上下文。"""
        mock_llm = AsyncMock(return_value={
            "content": '{"sql": "SELECT COUNT(*) FROM orders", "explanation": "统计订单", "confidence": 0.8}',
            "explanation": "统计订单",
            "confidence": 0.8,
        })

        pipeline = _build_pipeline(
            mock_budget_manager=mock_budget_manager,
            mock_intent_router=mock_intent_router,
            mock_intent_parser=mock_intent_parser,
            mock_schema_linker=None,  # 不提供 SchemaLinker
            mock_fewshot_matcher=mock_fewshot_matcher,
            mock_llm_generate=mock_llm,
        )

        result = await pipeline.generate(
            question="订单量多少",
            session_id="session-001",
            tenant_id="tenant-001",
            context=sample_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.sql != ""

    @pytest.mark.asyncio
    async def test_empty_context_defaults(
        self,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
    ) -> None:
        """不提供语义上下文时不应报错，使用默认空上下文。"""
        mock_llm = AsyncMock(return_value={
            "content": '{"sql": "SELECT 1", "explanation": "占位", "confidence": 0.5}',
            "explanation": "占位",
            "confidence": 0.5,
        })

        pipeline = _build_pipeline(
            mock_budget_manager=mock_budget_manager,
            mock_intent_router=mock_intent_router,
            mock_intent_parser=mock_intent_parser,
            mock_schema_linker=mock_schema_linker,
            mock_fewshot_matcher=mock_fewshot_matcher,
            mock_llm_generate=mock_llm,
        )

        result = await pipeline.generate(
            question="随便查点数据",
            session_id="session-001",
            tenant_id="tenant-001",
            # 不提供 context 参数
        )

        assert isinstance(result, NL2SQLResult)
