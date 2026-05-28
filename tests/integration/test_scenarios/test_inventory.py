"""业务场景：库存统计。

验证 NL2SQL Pipeline 在库存管理场景下的端到端能力，
包括低库存预警、库存汇总和库存趋势查询。
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from datapilot_sqlgen.generator.models import NL2SQLResult, SemanticContext


# ---------------------------------------------------------------------------
# 库存场景语义上下文
# ---------------------------------------------------------------------------


@pytest.fixture
def inventory_semantic_context() -> SemanticContext:
    """构建库存统计场景的语义上下文。"""
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
                table_name="warehouse_inventory",
                description="仓库库存表",
                columns=[
                    ColumnInfo(name="id", col_type="BIGINT", description="库存记录 ID", is_primary_key=True),
                    ColumnInfo(name="product_id", col_type="BIGINT", description="商品 ID"),
                    ColumnInfo(name="product_name", col_type="VARCHAR(200)", description="商品名称"),
                    ColumnInfo(name="warehouse", col_type="VARCHAR(50)", description="仓库名称"),
                    ColumnInfo(name="stock_qty", col_type="INT", description="当前库存数量"),
                    ColumnInfo(name="safety_stock", col_type="INT", description="安全库存数量"),
                    ColumnInfo(name="avg_daily_sales", col_type="DECIMAL(10,2)", description="日均销售量"),
                    ColumnInfo(name="last_replenish_date", col_type="DATE", description="最近补货日期"),
                    ColumnInfo(name="updated_at", col_type="DATETIME", description="更新时间"),
                ],
            ),
            TableInfo(
                table_name="products",
                description="商品主表",
                columns=[
                    ColumnInfo(name="id", col_type="BIGINT", description="商品 ID", is_primary_key=True),
                    ColumnInfo(name="name", col_type="VARCHAR(200)", description="商品名称"),
                    ColumnInfo(name="category", col_type="VARCHAR(50)", description="类目"),
                    ColumnInfo(name="status", col_type="VARCHAR(20)", description="商品状态（active/discontinued）"),
                ],
            ),
        ],
        relationships=[
            TableRelationship(
                left_table="warehouse_inventory",
                right_table="products",
                join_condition="warehouse_inventory.product_id = products.id",
                join_type="left",
            ),
        ],
        metrics=[
            MetricInfo(name="总库存量", calculation="SUM(stock_qty)", unit="件"),
            MetricInfo(name="低库存商品数", calculation="COUNT(CASE WHEN stock_qty < safety_stock THEN 1 END)", unit="个"),
            MetricInfo(name="可用库存天数", calculation="stock_qty / NULLIF(avg_daily_sales, 0)", unit="天"),
        ],
        dimensions=[
            DimensionInfo(name="仓库", column_name="warehouse", table_name="warehouse_inventory"),
            DimensionInfo(name="类目", column_name="category", table_name="products"),
            DimensionInfo(name="商品名称", column_name="product_name", table_name="warehouse_inventory"),
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
# 库存统计场景测试
# ---------------------------------------------------------------------------


class TestInventoryScenario:
    """业务场景：库存统计。"""

    @pytest.mark.asyncio
    async def test_low_stock_alert(
        self,
        inventory_semantic_context: SemanticContext,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
    ) -> None:
        """场景：低库存预警商品查询。

        用户问题：「哪些商品库存低于安全库存？」
        预期 SQL：筛选库存量低于安全库存的商品。
        """
        mock_llm = _make_mock_llm(
            sql=(
                "SELECT product_name, warehouse, stock_qty, safety_stock, "
                "safety_stock - stock_qty AS shortage "
                "FROM warehouse_inventory "
                "WHERE stock_qty < safety_stock "
                "ORDER BY shortage DESC "
                "LIMIT 100"
            ),
            explanation="查询库存低于安全库存的商品，按缺口降序排列",
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
            question="哪些商品库存低于安全库存？",
            session_id="inv-session-001",
            tenant_id="tenant-001",
            context=inventory_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "sql_query"
        assert result.sql != ""
        assert "stock_qty" in result.sql.lower()
        assert "safety_stock" in result.sql.lower()
        assert "WHERE" in result.sql.upper()
        assert result.confidence > 0.8

    @pytest.mark.asyncio
    async def test_inventory_summary(
        self,
        inventory_semantic_context: SemanticContext,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
    ) -> None:
        """场景：各仓库库存汇总。

        用户问题：「各仓库的库存总量分别是多少？」
        预期 SQL：按仓库分组聚合库存。
        """
        mock_llm = _make_mock_llm(
            sql=(
                "SELECT warehouse, "
                "  SUM(stock_qty) AS total_stock, "
                "  COUNT(DISTINCT product_id) AS product_count "
                "FROM warehouse_inventory "
                "GROUP BY warehouse "
                "ORDER BY total_stock DESC "
                "LIMIT 50"
            ),
            explanation="按仓库统计库存总量和商品种类数",
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
            question="各仓库的库存总量分别是多少？",
            session_id="inv-session-002",
            tenant_id="tenant-001",
            context=inventory_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "sql_query"
        assert result.sql != ""
        assert "warehouse" in result.sql.lower()
        assert "SUM" in result.sql.upper()
        assert "GROUP BY" in result.sql.upper()
        assert result.confidence > 0.8

    @pytest.mark.asyncio
    async def test_stock_trend(
        self,
        inventory_semantic_context: SemanticContext,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
    ) -> None:
        """场景：库存变化趋势。

        用户问题：「最近 7 天每天的库存入库量变化趋势如何？」
        预期 SQL：按日期分组统计。
        """
        mock_llm = _make_mock_llm(
            sql=(
                "SELECT DATE(last_replenish_date) AS replenish_date, "
                "  COUNT(*) AS replenish_count, "
                "  SUM(stock_qty) AS total_replenished "
                "FROM warehouse_inventory "
                "WHERE last_replenish_date >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY) "
                "GROUP BY DATE(last_replenish_date) "
                "ORDER BY replenish_date ASC "
                "LIMIT 50"
            ),
            explanation="查询最近 7 天的库存入库趋势",
            confidence=0.88,
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
            question="最近 7 天每天的库存入库量变化趋势如何？",
            session_id="inv-session-003",
            tenant_id="tenant-001",
            context=inventory_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "sql_query"
        assert result.sql != ""
        assert "DATE" in result.sql.upper()
        assert "GROUP BY" in result.sql.upper()
        assert "ORDER BY" in result.sql.upper()
        assert result.confidence > 0.7

        # Guardrail 验证：生成的 SQL 应通过安全检查
        from datapilot_guardrail.checker import GuardrailChecker
        checker = GuardrailChecker(redis_url="redis://nonexistent:6379/0")
        guardrail_result = await checker.check(
            sql=result.sql,
            tenant_id="tenant-001",
        )
        assert guardrail_result.passed is True

    @pytest.mark.asyncio
    async def test_category_inventory_distribution(
        self,
        inventory_semantic_context: SemanticContext,
        mock_budget_manager: MagicMock,
        mock_intent_router: MagicMock,
        mock_intent_parser: MagicMock,
        mock_schema_linker: MagicMock,
        mock_fewshot_matcher: MagicMock,
    ) -> None:
        """场景：按类目统计库存分布。

        用户问题：「各商品类目的库存数量分布如何？」

        这是一个需要跨表 JOIN 的分析查询。
        """
        mock_llm = _make_mock_llm(
            sql=(
                "SELECT p.category, "
                "  SUM(wi.stock_qty) AS total_stock, "
                "  COUNT(DISTINCT wi.product_id) AS sku_count "
                "FROM warehouse_inventory wi "
                "LEFT JOIN products p ON wi.product_id = p.id "
                "GROUP BY p.category "
                "ORDER BY total_stock DESC "
                "LIMIT 50"
            ),
            explanation="按商品类目统计库存总量和 SKU 数量",
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
            question="各商品类目的库存数量分布如何？",
            session_id="inv-session-004",
            tenant_id="tenant-001",
            context=inventory_semantic_context,
        )

        assert isinstance(result, NL2SQLResult)
        assert result.intent == "sql_query"
        assert result.sql != ""
        assert "category" in result.sql.lower()
        assert "JOIN" in result.sql.upper()
        assert result.confidence > 0.8
