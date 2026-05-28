"""业务场景：销售数据查询。

验证 NL2SQL Pipeline 在电商销售场景下的端到端能力，
包括按城市查询销售额、月度趋势分析、商品排名等。
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from datapilot_sqlgen.generator.models import NL2SQLResult, SemanticContext


# ---------------------------------------------------------------------------
# 销售场景语义上下文
# ---------------------------------------------------------------------------


@pytest.fixture
def sales_semantic_context() -> SemanticContext:
    """构建销售数据查询场景的语义上下文。"""
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
                table_name="sales_orders",
                description="销售订单表",
                columns=[
                    ColumnInfo(name="id", col_type="BIGINT", description="订单 ID", is_primary_key=True),
                    ColumnInfo(name="city", col_type="VARCHAR(50)", description="下单城市"),
                    ColumnInfo(name="product_name", col_type="VARCHAR(200)", description="商品名称"),
                    ColumnInfo(name="category", col_type="VARCHAR(50)", description="商品类目"),
                    ColumnInfo(name="amount", col_type="DECIMAL(12,2)", description="销售金额（元）"),
                    ColumnInfo(name="quantity", col_type="INT", description="购买数量"),
                    ColumnInfo(name="order_date", col_type="DATE", description="下单日期"),
                    ColumnInfo(name="status", col_type="VARCHAR(20)", description="订单状态"),
                ],
            ),
            TableInfo(
                table_name="products",
                description="商品维度表",
                columns=[
                    ColumnInfo(name="id", col_type="BIGINT", description="商品 ID", is_primary_key=True),
                    ColumnInfo(name="name", col_type="VARCHAR(200)", description="商品名称"),
                    ColumnInfo(name="category", col_type="VARCHAR(50)", description="类目"),
                    ColumnInfo(name="brand", col_type="VARCHAR(100)", description="品牌"),
                    ColumnInfo(name="unit_price", col_type="DECIMAL(10,2)", description="单价"),
                ],
            ),
        ],
        relationships=[
            TableRelationship(
                left_table="sales_orders",
                right_table="products",
                join_condition="sales_orders.product_name = products.name",
                join_type="left",
            ),
        ],
        metrics=[
            MetricInfo(name="销售额", calculation="SUM(sales_orders.amount)", unit="元"),
            MetricInfo(name="订单量", calculation="COUNT(DISTINCT sales_orders.id)", unit="单"),
            MetricInfo(name="客单价", calculation="AVG(sales_orders.amount)", unit="元"),
        ],
        dimensions=[
            DimensionInfo(name="城市", column_name="city", table_name="sales_orders"),
            DimensionInfo(name="日期", column_name="order_date", table_name="sales_orders"),
            DimensionInfo(name="类目", column_name="category", table_name="sales_orders"),
            DimensionInfo(name="品牌", column_name="brand", table_name="products"),
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
# 销售数据查询场景测试
# ---------------------------------------------------------------------------


class TestSalesScenario:
    """业务场景：销售数据查询。"""

    @pytest.mark.asyncio
    async def test_city_sales_amount(
        self,
        sales_semantic_context: SemanticContext,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
    ) -> None:
        """场景：按城市查询销售总额。

        用户问题：「各城市的销售额是多少？」
        预期 SQL：按城市分组聚合金额。
        """
        mock_llm = _make_mock_llm(
            sql="SELECT city, SUM(amount) AS total_sales FROM sales_orders GROUP BY city ORDER BY total_sales DESC LIMIT 50",
            explanation="按城市分组计算销售总额并降序排列",
            confidence=0.93,
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
            question="各城市的销售额是多少？",
            session_id="sales-session-001",
            tenant_id="tenant-001",
            context=sales_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "sql_query"
        assert result.sql != ""
        assert "city" in result.sql.lower()
        assert "SUM" in result.sql.upper()
        assert "GROUP BY" in result.sql.upper()
        assert result.confidence > 0.8

    @pytest.mark.asyncio
    async def test_monthly_trend(
        self,
        sales_semantic_context: SemanticContext,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
    ) -> None:
        """场景：月度销售趋势分析。

        用户问题：「今年每个月的销售额趋势如何？」
        预期 SQL：按月份分组聚合，包含时间范围过滤。
        """
        mock_llm = _make_mock_llm(
            sql=(
                "SELECT DATE_FORMAT(order_date, '%Y-%m') AS month, "
                "SUM(amount) AS monthly_sales "
                "FROM sales_orders "
                "WHERE order_date >= '2024-01-01' "
                "GROUP BY DATE_FORMAT(order_date, '%Y-%m') "
                "ORDER BY month ASC "
                "LIMIT 100"
            ),
            explanation="按月份统计 2024 年每月销售总额并按时间排序",
            confidence=0.90,
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
            question="今年每个月的销售额趋势如何？",
            session_id="sales-session-002",
            tenant_id="tenant-001",
            context=sales_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "sql_query"
        assert result.sql != ""
        assert "DATE_FORMAT" in result.sql or "month" in result.sql.lower()
        assert "SUM" in result.sql.upper()
        assert "GROUP BY" in result.sql.upper()
        assert result.confidence > 0.8

    @pytest.mark.asyncio
    async def test_top_products(
        self,
        sales_semantic_context: SemanticContext,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
    ) -> None:
        """场景：查询销售排名前 N 的商品。

        用户问题：「销售额最高的前 10 个商品是什么？」
        预期 SQL：按商品聚合并排序，含 LIMIT。
        """
        mock_llm = _make_mock_llm(
            sql=(
                "SELECT product_name, SUM(amount) AS total_sales, COUNT(DISTINCT id) AS order_count "
                "FROM sales_orders "
                "GROUP BY product_name "
                "ORDER BY total_sales DESC "
                "LIMIT 10"
            ),
            explanation="按商品名称聚合销售总额，取前 10 名",
            confidence=0.94,
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
            question="销售额最高的前 10 个商品是什么？",
            session_id="sales-session-003",
            tenant_id="tenant-001",
            context=sales_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "sql_query"
        assert result.sql != ""
        assert "product_name" in result.sql.lower()
        assert "SUM" in result.sql.upper()
        assert "ORDER BY" in result.sql.upper()
        assert "LIMIT" in result.sql.upper()
        assert result.confidence > 0.8

    @pytest.mark.asyncio
    async def test_category_sales_comparison(
        self,
        sales_semantic_context: SemanticContext,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
    ) -> None:
        """场景：各类目销售对比。

        用户问题：「不同商品类目的销售额对比情况？」

        这里也顺便验证在 guardrail 中，合理的安全 SELECT 通过检查。
        """
        mock_llm = _make_mock_llm(
            sql=(
                "SELECT category, SUM(amount) AS total_sales, COUNT(DISTINCT id) AS order_count "
                "FROM sales_orders "
                "GROUP BY category "
                "ORDER BY total_sales DESC "
                "LIMIT 50"
            ),
            explanation="按商品类目分组统计销售额和订单数",
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
            question="不同商品类目的销售额对比情况？",
            session_id="sales-session-004",
            tenant_id="tenant-001",
            context=sales_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "sql_query"
        assert result.sql != ""

        # Guardrail 验证：生成的 SQL 应通过安全检查
        from datapilot_guardrail.checker import GuardrailChecker
        checker = GuardrailChecker(redis_url="redis://nonexistent:6379/0")
        guardrail_result = await checker.check(
            sql=result.sql,
            tenant_id="tenant-001",
        )
        assert guardrail_result.passed is True
