"""SemanticResolver 时间/过滤/聚合解析单元测试。"""

from __future__ import annotations

from datetime import date

import pytest

from datapilot_sqlgen.intent.resolver import SemanticResolver
from datapilot_sqlgen.intent.types import (
    AggregationFunction,
    FilterCondition,
    JoinStep,
    LinkedDimension,
    LinkedMetric,
    ParsedIntent,
    QueryType,
    ResolvedAggregation,
    ResolvedFilter,
    ResolvedQuery,
    ResolvedSort,
    ResolvedTimeCondition,
    SemanticContext,
    SortDirection,
    SortSpec,
    TimeRange,
)


class TestSemanticResolverTimeParsing:
    """SemanticResolver 时间解析测试。"""

    @pytest.fixture
    def resolver(self) -> SemanticResolver:
        """创建 SemanticResolver 实例。"""
        return SemanticResolver()

    @pytest.fixture
    def context_with_time_dim(self) -> SemanticContext:
        """创建带时间维度的语义上下文。"""
        return SemanticContext(
            selected_tables=["orders"],
            selected_metrics=[
                LinkedMetric(
                    metric_id="m-001",
                    name="GMV",
                    calculation="SUM(orders.amount)",
                    unit="元",
                    table_id="t-001",
                    table_name="orders",
                )
            ],
            selected_dimensions=[
                LinkedDimension(
                    dimension_id="d-002",
                    name="时间",
                    column_name="created_at",
                    table_id="t-001",
                    table_name="orders",
                    synonyms=["日期", "创建时间"],
                )
            ],
        )

    def test_resolve_time_with_dates(
        self, resolver: SemanticResolver, context_with_time_dim: SemanticContext
    ) -> None:
        """测试时间范围转换为 WHERE 条件。"""
        intent = ParsedIntent(
            query_type=QueryType.AGGREGATION,
            target_metrics=["GMV"],
            time_range=TimeRange(
                start=date(2026, 4, 1),
                end=date(2026, 4, 30),
                raw_text="上月",
                granularity="month",
            ),
            raw_question="上月GMV",
        )
        result = resolver.resolve(intent, context_with_time_dim)
        assert result.time_condition is not None
        assert result.time_condition.column == "created_at"
        assert result.time_condition.start_expr == "'2026-04-01'"
        assert result.time_condition.end_expr == "'2026-04-30'"
        assert result.time_condition.raw_text == "上月"

    def test_resolve_time_no_time_range(
        self, resolver: SemanticResolver, context_with_time_dim: SemanticContext
    ) -> None:
        """测试无时间范围时不生成时间条件。"""
        intent = ParsedIntent(
            target_metrics=["GMV"],
            time_range=TimeRange(),
            raw_question="总GMV",
        )
        result = resolver.resolve(intent, context_with_time_dim)
        assert result.time_condition is None

    def test_resolve_time_only_start(
        self, resolver: SemanticResolver, context_with_time_dim: SemanticContext
    ) -> None:
        """测试仅有起始日期。"""
        intent = ParsedIntent(
            target_metrics=["GMV"],
            time_range=TimeRange(start=date(2026, 1, 1), raw_text="2026年起"),
            raw_question="2026年起GMV",
        )
        result = resolver.resolve(intent, context_with_time_dim)
        assert result.time_condition is not None
        assert result.time_condition.start_expr == "'2026-01-01'"
        assert result.time_condition.end_expr is None

    def test_resolve_time_no_time_dimension(
        self, resolver: SemanticResolver
    ) -> None:
        """测试无时间维度时使用默认列名。"""
        context = SemanticContext(
            selected_metrics=[
                LinkedMetric(
                    metric_id="m-001", name="GMV", calculation="SUM(orders.amount)"
                )
            ],
        )
        intent = ParsedIntent(
            target_metrics=["GMV"],
            time_range=TimeRange(
                start=date(2026, 1, 1),
                end=date(2026, 1, 31),
                raw_text="1月",
            ),
            raw_question="1月GMV",
        )
        result = resolver.resolve(intent, context)
        assert result.time_condition is not None
        # 无时间维度时使用默认列名
        assert result.time_condition.column == "created_at"
        # 无时间维度时应生成警告
        assert any("时间维度" in w for w in result.warnings)


class TestSemanticResolverFilterParsing:
    """SemanticResolver 过滤条件解析测试。"""

    @pytest.fixture
    def resolver(self) -> SemanticResolver:
        """创建 SemanticResolver 实例。"""
        return SemanticResolver()

    def test_resolve_string_filter(self, resolver: SemanticResolver) -> None:
        """测试字符串过滤条件解析。"""
        context = SemanticContext(
            filters=[
                FilterCondition(column="region", operator="=", value="华东", raw_text="华东")
            ],
        )
        intent = ParsedIntent(
            filters=[
                FilterCondition(column="地区", operator="=", value="华东", raw_text="华东")
            ],
            raw_question="华东区GMV",
        )
        result = resolver.resolve(intent, context)
        assert len(result.filters) == 1
        assert result.filters[0].column == "region"
        assert result.filters[0].sql_expression == "region = '华东'"

    def test_resolve_numeric_filter(self, resolver: SemanticResolver) -> None:
        """测试数值过滤条件解析。"""
        context = SemanticContext()
        intent = ParsedIntent(
            filters=[
                FilterCondition(column="amount", operator=">", value=1000, raw_text="金额>1000")
            ],
            raw_question="金额大于1000的订单",
        )
        result = resolver.resolve(intent, context)
        assert len(result.filters) == 1
        assert result.filters[0].column == "amount"
        assert result.filters[0].sql_expression == "amount > 1000"

    def test_resolve_in_filter(self, resolver: SemanticResolver) -> None:
        """测试 IN 过滤条件解析。"""
        context = SemanticContext()
        intent = ParsedIntent(
            filters=[
                FilterCondition(
                    column="status",
                    operator="IN",
                    value=["paid", "shipped"],
                    raw_text="已付款或已发货",
                )
            ],
            raw_question="已付款或已发货的订单",
        )
        result = resolver.resolve(intent, context)
        assert len(result.filters) == 1
        assert "IN" in result.filters[0].sql_expression
        assert "paid" in result.filters[0].sql_expression

    def test_resolve_like_filter(self, resolver: SemanticResolver) -> None:
        """测试 LIKE 过滤条件解析。"""
        context = SemanticContext()
        intent = ParsedIntent(
            filters=[
                FilterCondition(
                    column="name", operator="LIKE", value="iPhone", raw_text="包含iPhone"
                )
            ],
            raw_question="包含iPhone的商品",
        )
        result = resolver.resolve(intent, context)
        assert len(result.filters) == 1
        assert "LIKE" in result.filters[0].sql_expression

    def test_resolve_empty_filters(self, resolver: SemanticResolver) -> None:
        """测试无过滤条件。"""
        context = SemanticContext()
        intent = ParsedIntent(raw_question="总GMV")
        result = resolver.resolve(intent, context)
        assert len(result.filters) == 0


class TestSemanticResolverAggregation:
    """SemanticResolver 聚合解析测试。"""

    @pytest.fixture
    def resolver(self) -> SemanticResolver:
        """创建 SemanticResolver 实例。"""
        return SemanticResolver()

    def test_resolve_aggregation_from_calculation(self, resolver: SemanticResolver) -> None:
        """测试从指标计算表达式推断聚合函数。"""
        context = SemanticContext(
            selected_metrics=[
                LinkedMetric(
                    metric_id="m-001",
                    name="GMV",
                    calculation="SUM(orders.amount)",
                    table_name="orders",
                )
            ],
        )
        intent = ParsedIntent(
            query_type=QueryType.AGGREGATION,
            target_metrics=["GMV"],
            raw_question="总GMV",
        )
        result = resolver.resolve(intent, context)
        assert len(result.aggregations) == 1
        assert result.aggregations[0].function == AggregationFunction.SUM
        assert result.aggregations[0].column == "orders.amount"
        assert result.aggregations[0].alias == "GMV"

    def test_resolve_count_distinct(self, resolver: SemanticResolver) -> None:
        """测试 COUNT DISTINCT 聚合。"""
        context = SemanticContext(
            selected_metrics=[
                LinkedMetric(
                    metric_id="m-002",
                    name="订单量",
                    calculation="COUNT(DISTINCT orders.id)",
                    table_name="orders",
                )
            ],
        )
        intent = ParsedIntent(
            query_type=QueryType.AGGREGATION,
            target_metrics=["订单量"],
            raw_question="订单量统计",
        )
        result = resolver.resolve(intent, context)
        assert len(result.aggregations) == 1
        assert result.aggregations[0].function == AggregationFunction.COUNT_DISTINCT

    def test_no_aggregation_for_detail_query(self, resolver: SemanticResolver) -> None:
        """测试明细查询不产生聚合。"""
        context = SemanticContext(
            selected_metrics=[
                LinkedMetric(
                    metric_id="m-001", name="GMV", calculation="SUM(orders.amount)"
                )
            ],
        )
        intent = ParsedIntent(
            query_type=QueryType.DETAIL,
            target_metrics=["GMV"],
            raw_question="查看订单明细",
        )
        result = resolver.resolve(intent, context)
        assert len(result.aggregations) == 0

    def test_aggregation_keyword_mapping(self, resolver: SemanticResolver) -> None:
        """测试聚合关键词映射。"""
        context = SemanticContext()
        intent = ParsedIntent(
            query_type=QueryType.AGGREGATION,
            target_metrics=["销售额"],
            raw_question="平均销售额是多少",
        )
        result = resolver.resolve(intent, context)
        assert len(result.aggregations) >= 1
        # "平均" 应映射为 AVG
        avg_agg = [a for a in result.aggregations if a.function == AggregationFunction.AVG]
        assert len(avg_agg) > 0


class TestSemanticResolverSort:
    """SemanticResolver 排序解析测试。"""

    @pytest.fixture
    def resolver(self) -> SemanticResolver:
        """创建 SemanticResolver 实例。"""
        return SemanticResolver()

    def test_resolve_explicit_sort(self, resolver: SemanticResolver) -> None:
        """测试显式排序解析。"""
        context = SemanticContext(
            selected_metrics=[
                LinkedMetric(metric_id="m-001", name="GMV", calculation="SUM(orders.amount)")
            ],
        )
        intent = ParsedIntent(
            query_type=QueryType.RANKING,
            target_metrics=["GMV"],
            sort_by=[SortSpec(column="GMV", direction=SortDirection.DESC)],
            raw_question="GMV排名",
        )
        result = resolver.resolve(intent, context)
        assert len(result.sort_by) == 1
        assert result.sort_by[0].column == "GMV"
        assert result.sort_by[0].direction == SortDirection.DESC

    def test_ranking_default_desc_sort(self, resolver: SemanticResolver) -> None:
        """测试排名查询默认降序排序。"""
        context = SemanticContext(
            selected_metrics=[
                LinkedMetric(metric_id="m-001", name="GMV", calculation="SUM(orders.amount)")
            ],
        )
        intent = ParsedIntent(
            query_type=QueryType.RANKING,
            target_metrics=["GMV"],
            raw_question="GMV排名",
        )
        result = resolver.resolve(intent, context)
        assert len(result.sort_by) >= 1
        assert result.sort_by[0].direction == SortDirection.DESC


class TestSemanticResolverGroupBy:
    """SemanticResolver GROUP BY 测试。"""

    @pytest.fixture
    def resolver(self) -> SemanticResolver:
        """创建 SemanticResolver 实例。"""
        return SemanticResolver()

    def test_group_by_with_aggregation(self, resolver: SemanticResolver) -> None:
        """测试有聚合时生成 GROUP BY。"""
        context = SemanticContext(
            selected_metrics=[
                LinkedMetric(
                    metric_id="m-001", name="GMV", calculation="SUM(orders.amount)"
                )
            ],
            selected_dimensions=[
                LinkedDimension(
                    dimension_id="d-001",
                    name="地区",
                    column_name="region",
                    table_name="users",
                )
            ],
        )
        intent = ParsedIntent(
            query_type=QueryType.AGGREGATION,
            target_metrics=["GMV"],
            raw_question="各地区GMV",
        )
        result = resolver.resolve(intent, context)
        assert len(result.group_by) > 0
        assert "region" in result.group_by

    def test_no_group_by_without_aggregation(self, resolver: SemanticResolver) -> None:
        """测试无聚合时不生成 GROUP BY。"""
        context = SemanticContext()
        intent = ParsedIntent(query_type=QueryType.DETAIL, raw_question="订单明细")
        result = resolver.resolve(intent, context)
        assert len(result.group_by) == 0


class TestSemanticResolverSelectColumns:
    """SemanticResolver SELECT 列测试。"""

    @pytest.fixture
    def resolver(self) -> SemanticResolver:
        """创建 SemanticResolver 实例。"""
        return SemanticResolver()

    def test_aggregation_select_columns(self, resolver: SemanticResolver) -> None:
        """测试聚合查询的 SELECT 列。"""
        context = SemanticContext(
            selected_metrics=[
                LinkedMetric(
                    metric_id="m-001", name="GMV", calculation="SUM(orders.amount)"
                )
            ],
            selected_dimensions=[
                LinkedDimension(
                    dimension_id="d-001", name="地区", column_name="region"
                )
            ],
        )
        intent = ParsedIntent(
            query_type=QueryType.AGGREGATION,
            target_metrics=["GMV"],
            raw_question="各地区GMV",
        )
        result = resolver.resolve(intent, context)
        assert len(result.select_columns) > 0
        # 应包含聚合表达式
        select_str = " ".join(result.select_columns)
        assert "SUM" in select_str

    def test_detail_select_columns(self, resolver: SemanticResolver) -> None:
        """测试明细查询的 SELECT 列。"""
        context = SemanticContext(
            selected_metrics=[
                LinkedMetric(
                    metric_id="m-001", name="GMV", calculation="SUM(orders.amount)"
                )
            ],
            selected_dimensions=[
                LinkedDimension(
                    dimension_id="d-001", name="地区", column_name="region"
                )
            ],
        )
        intent = ParsedIntent(
            query_type=QueryType.DETAIL,
            raw_question="订单明细",
        )
        result = resolver.resolve(intent, context)
        # 应包含维度列和指标计算列
        assert len(result.select_columns) >= 1

    def test_no_columns_select_star(self, resolver: SemanticResolver) -> None:
        """测试无列时默认 SELECT *。"""
        context = SemanticContext()
        intent = ParsedIntent(query_type=QueryType.DETAIL, raw_question="查看数据")
        result = resolver.resolve(intent, context)
        assert result.select_columns == ["*"]


class TestResolvedQueryModel:
    """ResolvedQuery 模型测试。"""

    def test_model_creation(self) -> None:
        """测试模型创建。"""
        query = ResolvedQuery(
            select_columns=["region", "SUM(amount) AS total"],
            aggregations=[
                ResolvedAggregation(
                    metric_name="total",
                    function=AggregationFunction.SUM,
                    column="amount",
                    alias="total",
                )
            ],
            group_by=["region"],
            limit=10,
            query_type=QueryType.AGGREGATION,
        )
        assert query.limit == 10
        assert query.query_type == QueryType.AGGREGATION
        assert len(query.aggregations) == 1

    def test_model_defaults(self) -> None:
        """测试模型默认值。"""
        query = ResolvedQuery()
        assert query.select_columns == []
        assert query.aggregations == []
        assert query.filters == []
        assert query.sort_by == []
        assert query.group_by == []
        assert query.limit == 100
        assert query.query_type == QueryType.DETAIL
        assert query.warnings == []
        assert query.time_condition is None

    def test_model_from_attributes(self) -> None:
        """测试 from_attributes 配置。"""
        query = ResolvedQuery()
        assert query.model_config.get("from_attributes") is True

    def test_warnings_carried_over(self) -> None:
        """测试警告信息从 SemanticContext 传递。"""
        query = ResolvedQuery(
            warnings=["指标未匹配: X"],
        )
        assert len(query.warnings) == 1
        assert "指标未匹配" in query.warnings[0]
