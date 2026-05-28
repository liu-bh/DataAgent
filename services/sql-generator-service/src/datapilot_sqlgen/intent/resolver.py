"""Semantic Resolver 模块。

将 ParsedIntent 和 SemanticContext 转换为完整的结构化查询信息 (ResolvedQuery)，
包括时间条件转换、过滤条件解析、聚合映射、排序映射等。
ResolvedQuery 是 SQL 生成阶段的直接输入。
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from datapilot_sqlgen.intent.types import (
    AggregationFunction,
    FilterCondition,
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
    TimeRange,
)

logger = structlog.get_logger(__name__)


# ============================================================
# 聚合函数关键词映射
# ============================================================

_AGGREGATION_KEYWORDS: dict[str, AggregationFunction] = {
    "总计": AggregationFunction.SUM,
    "合计": AggregationFunction.SUM,
    "总和": AggregationFunction.SUM,
    "累计": AggregationFunction.SUM,
    "平均": AggregationFunction.AVG,
    "均值": AggregationFunction.AVG,
    "数量": AggregationFunction.COUNT,
    "个数": AggregationFunction.COUNT,
    "去重数": AggregationFunction.COUNT_DISTINCT,
    "唯一数": AggregationFunction.COUNT_DISTINCT,
    "最大": AggregationFunction.MAX,
    "最高": AggregationFunction.MAX,
    "最小": AggregationFunction.MIN,
    "最低": AggregationFunction.MIN,
}

# 排序方向关键词映射
_SORT_KEYWORDS: dict[str, SortDirection] = {
    "从高到低": SortDirection.DESC,
    "从大到小": SortDirection.DESC,
    "降序": SortDirection.DESC,
    "从低到高": SortDirection.ASC,
    "从小到大": SortDirection.ASC,
    "升序": SortDirection.ASC,
}


class SemanticResolver:
    """语义解析器。

    将 IntentParser 的输出和 SchemaLinker 的输出合并，
    转换为 SQL 生成所需的结构化查询信息。

    主要职责：
    - 时间范围 → WHERE date >= ... AND date < ...
    - 过滤条件 → WHERE 条件
    - 聚合语义 → SUM/AVG/COUNT 等
    - 排序需求 → ORDER BY

    Usage::

        resolver = SemanticResolver()
        resolved = resolver.resolve(parsed_intent, semantic_context)
    """

    def __init__(self) -> None:
        """初始化语义解析器。"""
        logger.info("SemanticResolver 初始化")

    # ---- 公开接口 ----

    def resolve(
        self,
        parsed_intent: ParsedIntent,
        semantic_context: SemanticContext,
    ) -> ResolvedQuery:
        """将解析意图和语义上下文合并为完整的结构化查询。

        Args:
            parsed_intent: IntentParser 的输出。
            semantic_context: SchemaLinker 的输出。

        Returns:
            ResolvedQuery 供 SQL 生成使用。
        """
        warnings: list[str] = list(semantic_context.warnings)

        # 1. 解析时间条件
        time_condition = self._resolve_time_condition(parsed_intent.time_range, semantic_context)
        if time_condition and self._is_using_default_time_column(semantic_context):
            warnings.append("未在语义上下文中找到时间维度，使用默认列 created_at")

        # 2. 解析过滤条件
        resolved_filters = self._resolve_filters(parsed_intent.filters, semantic_context)

        # 3. 解析聚合
        aggregations = self._resolve_aggregations(parsed_intent, semantic_context)

        # 4. 解析排序
        resolved_sort = self._resolve_sort(parsed_intent, semantic_context)

        # 5. 确定 SELECT 列
        select_columns = self._resolve_select_columns(parsed_intent, semantic_context, aggregations)

        # 6. 确定 GROUP BY
        group_by = self._resolve_group_by(parsed_intent, semantic_context, aggregations)

        # 7. 确定查询类型
        query_type = self._resolve_query_type(parsed_intent)

        logger.info(
            "语义解析完成",
            query_type=query_type.value,
            select_cols=len(select_columns),
            aggregations=len(aggregations),
            filters=len(resolved_filters),
            sort_cols=len(resolved_sort),
            group_by_cols=len(group_by),
            has_time_cond=time_condition is not None,
            warnings_count=len(warnings),
        )

        return ResolvedQuery(
            select_columns=select_columns,
            aggregations=aggregations,
            time_condition=time_condition,
            filters=resolved_filters,
            sort_by=resolved_sort,
            group_by=group_by,
            limit=parsed_intent.limit,
            join_path=semantic_context.join_path,
            query_type=query_type,
            raw_question=parsed_intent.raw_question,
            warnings=warnings,
        )

    # ---- 时间条件解析 ----

    def _resolve_time_condition(
        self,
        time_range: TimeRange,
        semantic_context: SemanticContext,
    ) -> ResolvedTimeCondition | None:
        """将时间范围转换为 WHERE 条件表达式。"""
        if not time_range.raw_text and time_range.start is None and time_range.end is None:
            return None

        # 查找时间维度
        time_column = self._find_time_column(semantic_context)

        # 构建 SQL 表达式
        start_expr: str | None = None
        end_expr: str | None = None

        if time_range.start is not None:
            start_expr = f"'{time_range.start.isoformat()}'"

        if time_range.end is not None:
            end_expr = f"'{time_range.end.isoformat()}'"

        return ResolvedTimeCondition(
            column=time_column,
            start_expr=start_expr,
            end_expr=end_expr,
            raw_text=time_range.raw_text,
        )

    def _find_time_column(self, semantic_context: SemanticContext) -> str:
        """从语义上下文中查找时间字段。"""
        # 优先从关联维度中查找时间类型维度
        for dim in semantic_context.selected_dimensions:
            # 按名称和同义词判断是否为时间维度
            time_names = ["时间", "日期", "创建时间", "下单时间", "time", "date", "created_at"]
            if dim.name.lower() in [n.lower() for n in time_names]:
                return dim.column_name or dim.name
            for syn in dim.synonyms:
                if syn.lower() in [n.lower() for n in time_names]:
                    return dim.column_name or dim.name

        # 默认使用常见时间列名
        return "created_at"

    def _is_using_default_time_column(self, semantic_context: SemanticContext) -> bool:
        """检查是否使用了默认时间列（语义上下文中没有时间维度）。"""
        time_names = ["时间", "日期", "创建时间", "下单时间", "time", "date", "created_at"]
        for dim in semantic_context.selected_dimensions:
            if dim.name.lower() in [n.lower() for n in time_names]:
                return False
            for syn in dim.synonyms:
                if syn.lower() in [n.lower() for n in time_names]:
                    return False
        return True

    # ---- 过滤条件解析 ----

    def _resolve_filters(
        self,
        filters: list[FilterCondition],
        semantic_context: SemanticContext,
    ) -> list[ResolvedFilter]:
        """将过滤条件映射到物理列并构建 SQL 表达式。"""
        if not filters:
            return []

        # 合并 SchemaLinker 已解析的过滤条件和原始过滤条件
        # 优先使用 semantic_context 中已映射的列名
        ctx_filter_map: dict[str, FilterCondition] = {}
        for f in semantic_context.filters:
            ctx_filter_map[f.raw_text] = f

        resolved: list[ResolvedFilter] = []
        for f in filters:
            # 尝试从语义上下文获取映射后的列名
            mapped = ctx_filter_map.get(f.raw_text, f)
            column = mapped.column

            # 构建 SQL 表达式
            sql_expr = self._build_filter_sql(column, mapped.operator, mapped.value)

            resolved.append(
                ResolvedFilter(
                    column=column,
                    operator=mapped.operator,
                    value=mapped.value,
                    sql_expression=sql_expr,
                    raw_text=f.raw_text,
                )
            )

        return resolved

    def _build_filter_sql(self, column: str, operator: str, value: Any) -> str:
        """构建单个过滤条件的 SQL 表达式。"""
        if value is None:
            return ""

        op = operator.upper()

        if op == "IN":
            if isinstance(value, (list, tuple)):
                values_str = ", ".join(f"'{v}'" for v in value)
                return f"{column} IN ({values_str})"
            return f"{column} IN ('{value}')"

        if op == "BETWEEN":
            if isinstance(value, (list, tuple)) and len(value) == 2:
                return f"{column} BETWEEN '{value[0]}' AND '{value[1]}'"
            return ""

        if op == "LIKE":
            return f"{column} LIKE '%{value}%'"

        # 基本操作符
        if isinstance(value, str):
            return f"{column} {op} '{value}'"
        return f"{column} {op} {value}"

    # ---- 聚合解析 ----

    def _resolve_aggregations(
        self,
        parsed_intent: ParsedIntent,
        semantic_context: SemanticContext,
    ) -> list[ResolvedAggregation]:
        """将查询意图中的聚合语义映射为具体聚合函数。"""
        # 明细查询不需要聚合
        if parsed_intent.query_type == QueryType.DETAIL:
            return []

        aggregations: list[ResolvedAggregation] = []

        # 从关联的指标中构建聚合
        for metric in semantic_context.selected_metrics:
            agg = self._metric_to_aggregation(metric, parsed_intent)
            if agg:
                aggregations.append(agg)

        # 如果没有通过语义层找到指标，从问题中的关键词推断
        if not aggregations and parsed_intent.target_metrics:
            for metric_name in parsed_intent.target_metrics:
                agg = self._infer_aggregation(metric_name, parsed_intent)
                if agg and not any(a.metric_name == agg.metric_name for a in aggregations):
                    aggregations.append(agg)

        return aggregations

    def _metric_to_aggregation(
        self,
        metric: LinkedMetric,
        parsed_intent: ParsedIntent,
    ) -> ResolvedAggregation | None:
        """将关联指标转换为聚合信息。"""
        if not metric.calculation:
            return None

        # 从计算表达式中推断聚合函数
        calc_upper = metric.calculation.upper().strip()
        agg_func = self._detect_aggregation_function(calc_upper)

        # 提取列名
        column = self._extract_column_from_calculation(metric.calculation)

        # 生成别名
        alias = metric.name

        return ResolvedAggregation(
            metric_name=metric.name,
            function=agg_func,
            column=column,
            alias=alias,
        )

    def _detect_aggregation_function(self, calc_expr: str) -> AggregationFunction:
        """从计算表达式中检测聚合函数。"""
        # COUNT DISTINCT 需要先于 COUNT 检查
        if "COUNT(DISTINCT" in calc_expr or "COUNT_DISTINCT" in calc_expr:
            return AggregationFunction.COUNT_DISTINCT
        for func in AggregationFunction:
            func_name = func.value
            if func_name in calc_expr:
                return func
        return AggregationFunction.SUM

    @staticmethod
    def _extract_column_from_calculation(calc_expr: str) -> str:
        """从计算表达式中提取列名。

        例如: "SUM(orders.amount)" → "orders.amount"
        """
        # 匹配括号内的内容
        match = re.search(r"\(([^)]+)\)", calc_expr)
        if match:
            return match.group(1).strip()
        return ""

    def _infer_aggregation(
        self, metric_name: str, parsed_intent: ParsedIntent
    ) -> ResolvedAggregation | None:
        """从问题关键词推断聚合函数。"""
        question = parsed_intent.raw_question.lower()

        # 检查问题中的聚合关键词
        for kw, func in _AGGREGATION_KEYWORDS.items():
            if kw in question:
                return ResolvedAggregation(
                    metric_name=metric_name,
                    function=func,
                    column=metric_name,
                    alias=metric_name,
                )

        # 默认 SUM
        return ResolvedAggregation(
            metric_name=metric_name,
            function=AggregationFunction.SUM,
            column=metric_name,
            alias=metric_name,
        )

    # ---- 排序解析 ----

    def _resolve_sort(
        self,
        parsed_intent: ParsedIntent,
        semantic_context: SemanticContext,
    ) -> list[ResolvedSort]:
        """解析排序需求。"""
        resolved: list[ResolvedSort] = []

        if parsed_intent.sort_by:
            for sort_spec in parsed_intent.sort_by:
                # 如果列名未指定，使用第一个指标
                column = sort_spec.column
                if not column and semantic_context.selected_metrics:
                    column = semantic_context.selected_metrics[0].name
                if not column:
                    continue

                resolved.append(
                    ResolvedSort(
                        column=column,
                        direction=sort_spec.direction,
                    )
                )
        else:
            # 根据查询类型推断默认排序
            if parsed_intent.query_type == QueryType.RANKING and semantic_context.selected_metrics:
                # 排名查询默认按指标降序
                resolved.append(
                    ResolvedSort(
                        column=semantic_context.selected_metrics[0].name,
                        direction=SortDirection.DESC,
                    )
                )

        return resolved

    # ---- SELECT 列 ----

    def _resolve_select_columns(
        self,
        parsed_intent: ParsedIntent,
        semantic_context: SemanticContext,
        aggregations: list[ResolvedAggregation],
    ) -> list[str]:
        """确定 SELECT 列列表。"""
        columns: list[str] = []

        if aggregations:
            # 聚合查询：SELECT 聚合列 + 维度列
            for agg in aggregations:
                columns.append(f"{agg.function.value}({agg.column}) AS {agg.alias}")
        elif parsed_intent.query_type == QueryType.DETAIL:
            # 明细查询：SELECT 维度列 + 指标列
            for dim in semantic_context.selected_dimensions:
                columns.append(dim.column_name or dim.name)
            for metric in semantic_context.selected_metrics:
                columns.append(metric.calculation if metric.calculation else metric.name)

        # 确保至少有 SELECT 列
        if not columns:
            columns.append("*")

        return columns

    # ---- GROUP BY ----

    def _resolve_group_by(
        self,
        parsed_intent: ParsedIntent,
        semantic_context: SemanticContext,
        aggregations: list[ResolvedAggregation],
    ) -> list[str]:
        """确定 GROUP BY 列列表。"""
        if not aggregations:
            return []

        # 有聚合时，所有非聚合维度都应加入 GROUP BY
        group_cols: list[str] = []
        for dim in semantic_context.selected_dimensions:
            col = dim.column_name or dim.name
            if col not in group_cols:
                group_cols.append(col)

        return group_cols

    # ---- 查询类型解析 ----

    @staticmethod
    def _resolve_query_type(parsed_intent: ParsedIntent) -> QueryType:
        """确定最终查询类型。"""
        # 如果有聚合，且查询类型为 DETAIL，调整为 AGGREGATION
        if parsed_intent.query_type == QueryType.DETAIL and parsed_intent.target_metrics:
            # 检查问题中是否有聚合关键词
            question = parsed_intent.raw_question.lower()
            agg_kw = ["总计", "合计", "汇总", "平均", "总量", "总共"]
            if any(kw in question for kw in agg_kw):
                return QueryType.AGGREGATION

        return parsed_intent.query_type
