"""SchemaLinker 匹配逻辑单元测试。"""

from __future__ import annotations

import pytest

from datapilot_sqlgen.intent.schema_linker import (
    _EXACT_THRESHOLD,
    _FUZZY_THRESHOLD,
    _SYNONYM_THRESHOLD,
    SchemaLinker,
)
from datapilot_sqlgen.intent.types import (
    FilterCondition,
    LinkedMetric,
    LinkedDimension,
    ParsedIntent,
    QueryType,
    SemanticContext,
    TimeRange,
)


class TestSchemaLinkerMetrics:
    """SchemaLinker 指标匹配测试。"""

    @pytest.fixture
    def linker(self) -> SchemaLinker:
        """创建 SchemaLinker 实例。"""
        return SchemaLinker(use_vector_search=False)

    def test_exact_metric_match(self, linker: SchemaLinker) -> None:
        """测试指标精确匹配。"""
        intent = ParsedIntent(
            query_type=QueryType.AGGREGATION,
            target_metrics=["GMV"],
            raw_question="GMV是多少",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        assert len(ctx.selected_metrics) == 1
        assert ctx.selected_metrics[0].name == "GMV"
        assert ctx.selected_metrics[0].matched_by == "exact"
        assert ctx.selected_metrics[0].match_score == _EXACT_THRESHOLD

    def test_synonym_metric_match(self, linker: SchemaLinker) -> None:
        """测试指标同义词匹配。"""
        intent = ParsedIntent(
            query_type=QueryType.AGGREGATION,
            target_metrics=["销售额"],
            raw_question="销售额统计",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        assert len(ctx.selected_metrics) == 1
        assert ctx.selected_metrics[0].name == "GMV"
        assert ctx.selected_metrics[0].matched_by == "synonym"
        assert ctx.selected_metrics[0].match_score >= _SYNONYM_THRESHOLD

    def test_no_metric_match(self, linker: SchemaLinker) -> None:
        """测试无匹配指标时返回警告。"""
        intent = ParsedIntent(
            target_metrics=["不存在指标"],
            raw_question="不存在指标统计",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        assert len(ctx.selected_metrics) == 0
        assert any("不存在指标" in w for w in ctx.warnings)

    def test_multiple_metrics(self, linker: SchemaLinker) -> None:
        """测试多指标匹配。"""
        intent = ParsedIntent(
            target_metrics=["GMV", "订单量"],
            raw_question="GMV和订单量",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        metric_names = [m.name for m in ctx.selected_metrics]
        assert "GMV" in metric_names
        assert "订单量" in metric_names

    def test_metric_table_info(self, linker: SchemaLinker) -> None:
        """测试匹配指标的表信息。"""
        intent = ParsedIntent(
            target_metrics=["订单量"],
            raw_question="订单量统计",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        assert len(ctx.selected_metrics) == 1
        assert ctx.selected_metrics[0].table_name == "orders"
        assert ctx.selected_metrics[0].calculation == "COUNT(DISTINCT orders.id)"


class TestSchemaLinkerDimensions:
    """SchemaLinker 维度匹配测试。"""

    @pytest.fixture
    def linker(self) -> SchemaLinker:
        """创建 SchemaLinker 实例。"""
        return SchemaLinker(use_vector_search=False)

    def test_exact_dimension_match(self, linker: SchemaLinker) -> None:
        """测试维度精确匹配。"""
        intent = ParsedIntent(
            target_dimensions=["地区"],
            raw_question="各地区销售额",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        assert len(ctx.selected_dimensions) == 1
        assert ctx.selected_dimensions[0].name == "地区"
        assert ctx.selected_dimensions[0].matched_by == "exact"

    def test_synonym_dimension_match(self, linker: SchemaLinker) -> None:
        """测试维度同义词匹配。"""
        intent = ParsedIntent(
            target_dimensions=["区域"],
            raw_question="各区域销售额",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        assert len(ctx.selected_dimensions) == 1
        assert ctx.selected_dimensions[0].name == "地区"
        assert ctx.selected_dimensions[0].matched_by == "synonym"

    def test_synonym_大区(self, linker: SchemaLinker) -> None:
        """测试维度同义词"大区"匹配。"""
        intent = ParsedIntent(
            target_dimensions=["大区"],
            raw_question="各大区GMV",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        assert len(ctx.selected_dimensions) == 1
        assert ctx.selected_dimensions[0].name == "地区"

    def test_no_dimension_match(self, linker: SchemaLinker) -> None:
        """测试无匹配维度时返回警告。"""
        intent = ParsedIntent(
            target_dimensions=["不存在维度"],
            raw_question="按不存在维度分组",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        assert len(ctx.selected_dimensions) == 0
        assert any("不存在维度" in w for w in ctx.warnings)

    def test_dimension_column_mapping(self, linker: SchemaLinker) -> None:
        """测试维度列名映射。"""
        intent = ParsedIntent(
            target_dimensions=["时间"],
            raw_question="按时间统计",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        assert len(ctx.selected_dimensions) == 1
        assert ctx.selected_dimensions[0].column_name == "created_at"

    def test_virtual_dimension(self, linker: SchemaLinker) -> None:
        """测试虚拟维度标记。"""
        # Mock 数据中的维度 is_virtual 均为 False
        intent = ParsedIntent(
            target_dimensions=["渠道"],
            raw_question="按渠道统计",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        assert len(ctx.selected_dimensions) == 1
        assert ctx.selected_dimensions[0].is_virtual is False


class TestSchemaLinkerJoinPath:
    """SchemaLinker JOIN 路径测试。"""

    @pytest.fixture
    def linker(self) -> SchemaLinker:
        """创建 SchemaLinker 实例。"""
        return SchemaLinker(use_vector_search=False)

    def test_single_table_no_join(self, linker: SchemaLinker) -> None:
        """测试单表查询无需 JOIN。"""
        intent = ParsedIntent(
            target_metrics=["GMV"],
            raw_question="总GMV",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        assert len(ctx.join_path) == 0

    def test_multi_table_join(self, linker: SchemaLinker) -> None:
        """测试多表 JOIN 路径推导。"""
        # GMV 在 orders 表，地区在 users 表 → 需要 JOIN
        intent = ParsedIntent(
            target_metrics=["GMV"],
            target_dimensions=["地区"],
            raw_question="各地区GMV",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        assert len(ctx.join_path) >= 1
        # 应包含 orders → users 的 JOIN
        join_strs = [
            f"{j.left_table} {j.join_type} JOIN {j.right_table}"
            for j in ctx.join_path
        ]
        assert any("orders" in s and "users" in s for s in join_strs)

    def test_selected_tables(self, linker: SchemaLinker) -> None:
        """测试选中的表列表。"""
        intent = ParsedIntent(
            target_metrics=["GMV"],
            target_dimensions=["地区"],
            raw_question="各地区GMV",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        assert "orders" in ctx.selected_tables
        assert "users" in ctx.selected_tables


class TestSchemaLinkerFilterDimensions:
    """SchemaLinker 过滤条件维度匹配测试。"""

    @pytest.fixture
    def linker(self) -> SchemaLinker:
        """创建 SchemaLinker 实例。"""
        return SchemaLinker(use_vector_search=False)

    def test_filter_column_mapping(self, linker: SchemaLinker) -> None:
        """测试过滤条件列名映射。"""
        intent = ParsedIntent(
            target_metrics=["GMV"],
            filters=[
                FilterCondition(column="地区", operator="=", value="华东", raw_text="华东")
            ],
            raw_question="华东区GMV",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        # 过滤条件中的"地区"应映射为 "region"
        assert any(f.column == "region" for f in ctx.filters)

    def test_filter_no_match_uses_original(self, linker: SchemaLinker) -> None:
        """测试过滤条件无匹配时使用原始列名。"""
        intent = ParsedIntent(
            target_metrics=["GMV"],
            filters=[
                FilterCondition(column="unknown_col", operator="=", value="val", raw_text="unknown")
            ],
            raw_question="查询数据",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        assert any(f.column == "unknown_col" for f in ctx.filters)


class TestSchemaLinkerSemanticModel:
    """SchemaLinker 语义模型选择测试。"""

    @pytest.fixture
    def linker(self) -> SchemaLinker:
        """创建 SchemaLinker 实例。"""
        return SchemaLinker(use_vector_search=False)

    def test_preferred_semantic_model(self, linker: SchemaLinker) -> None:
        """测试指定语义模型 ID。"""
        intent = ParsedIntent(
            target_metrics=["GMV"],
            raw_question="GMV统计",
        )
        ctx = linker.link(
            intent, tenant_id="t-001", semantic_model_id="sm-custom"
        )
        assert ctx.semantic_model_id == "sm-custom"

    def test_no_semantic_model_id(self, linker: SchemaLinker) -> None:
        """测试未指定语义模型 ID 时返回 None。"""
        intent = ParsedIntent(
            target_metrics=["GMV"],
            raw_question="GMV统计",
        )
        ctx = linker.link(intent, tenant_id="t-001")
        # Mock 实现返回 None
        assert ctx.semantic_model_id is None


class TestSemanticContextModel:
    """SemanticContext 模型测试。"""

    def test_empty_context(self) -> None:
        """测试空语义上下文。"""
        ctx = SemanticContext()
        assert ctx.selected_tables == []
        assert ctx.selected_metrics == []
        assert ctx.selected_dimensions == []
        assert ctx.join_path == []
        assert ctx.warnings == []

    def test_context_from_attributes(self) -> None:
        """测试 from_attributes 配置。"""
        ctx = SemanticContext()
        assert ctx.model_config.get("from_attributes") is True
