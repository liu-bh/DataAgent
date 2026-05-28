"""意图识别类型定义。

定义 NL2SQL 流程中意图路由、解析、Schema Linking、语义解析所需的数据结构。
包括意图类型枚举、解析结果、语义上下文等核心类型。
"""

from __future__ import annotations

from datetime import date  # noqa: TC003
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ============================================================
# 枚举类型
# ============================================================


class IntentType(StrEnum):
    """用户查询意图类型。

    用于意图路由阶段对用户输入进行分类。
    """

    SQL_QUERY = "sql_query"
    CHITCHAT = "chitchat"
    OUT_OF_SCOPE = "out_of_scope"
    ESCALATE_TO_HUMAN = "escalate_to_human"


class QueryType(StrEnum):
    """SQL 查询子类型。

    用于 Intent Parser 识别用户查询的具体数据需求。
    """

    AGGREGATION = "aggregation"  # 聚合查询（总计/平均/汇总）
    DETAIL = "detail"  # 明细查询（逐行展示）
    RANKING = "ranking"  # 排名查询（Top N / Bottom N）
    COMPARISON = "comparison"  # 对比查询（同比/环比/分组对比）
    TREND = "trend"  # 趋势查询（时序变化）


class AggregationFunction(StrEnum):
    """聚合函数类型。"""

    SUM = "SUM"
    AVG = "AVG"
    COUNT = "COUNT"
    COUNT_DISTINCT = "COUNT_DISTINCT"
    MAX = "MAX"
    MIN = "MIN"


class SortDirection(StrEnum):
    """排序方向。"""

    ASC = "ASC"
    DESC = "DESC"


# ============================================================
# 意图路由结果
# ============================================================


class IntentResult(BaseModel):
    """意图路由分类结果。

    由 IntentRouter 产生，包含意图类型、置信度和分类原因。

    Attributes:
        intent_type: 意图类型。
        confidence: 分类置信度 [0, 1]。
        reason: 分类原因说明。
        extracted_entities: 从用户输入中提取的实体信息（如指标名、维度名）。
    """

    model_config = ConfigDict(from_attributes=True)

    intent_type: IntentType
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="分类置信度")
    reason: str = Field(default="", description="分类原因说明")
    extracted_entities: list[str] = Field(default_factory=list, description="提取的实体信息")


# ============================================================
# Intent Parser 输出
# ============================================================


class TimeRange(BaseModel):
    """时间范围。

    Attributes:
        start: 起始日期，None 表示不限。
        end: 结束日期，None 表示不限。
        raw_text: 原始时间描述文本（如"上月"、"今年Q1"）。
        granularity: 时间粒度：day/week/month/quarter/year。
    """

    model_config = ConfigDict(from_attributes=True)

    start: date | None = Field(default=None, description="起始日期")
    end: date | None = Field(default=None, description="结束日期")
    raw_text: str = Field(default="", description="原始时间描述文本")
    granularity: str = Field(default="day", description="时间粒度")


class FilterCondition(BaseModel):
    """过滤条件。

    Attributes:
        column: 字段/维度名称。
        operator: 操作符（=, !=, >, <, >=, <=, IN, LIKE, BETWEEN）。
        value: 过滤值（单个值或列表）。
        raw_text: 原始过滤条件文本。
    """

    model_config = ConfigDict(from_attributes=True)

    column: str = Field(description="字段/维度名称")
    operator: str = Field(default="=", description="操作符")
    value: Any = Field(default=None, description="过滤值")
    raw_text: str = Field(default="", description="原始过滤条件文本")


class SortSpec(BaseModel):
    """排序规格。

    Attributes:
        column: 排序字段。
        direction: 排序方向。
    """

    model_config = ConfigDict(from_attributes=True)

    column: str = Field(description="排序字段")
    direction: SortDirection = Field(default=SortDirection.ASC, description="排序方向")


class ParsedIntent(BaseModel):
    """结构化意图解析结果。

    由 IntentParser 产生，包含从用户自然语言中提取的所有结构化查询信息。

    Attributes:
        query_type: 查询子类型（聚合/明细/排名/对比/趋势）。
        target_metrics: 用户目标指标列表。
        target_dimensions: 用户目标维度列表。
        time_range: 时间范围。
        filters: 过滤条件列表。
        sort_by: 排序规格列表。
        limit: 返回行数限制。
        raw_question: 原始用户问题。
    """

    model_config = ConfigDict(from_attributes=True)

    query_type: QueryType = Field(default=QueryType.DETAIL, description="查询子类型")
    target_metrics: list[str] = Field(default_factory=list, description="目标指标列表")
    target_dimensions: list[str] = Field(default_factory=list, description="目标维度列表")
    time_range: TimeRange = Field(default_factory=TimeRange, description="时间范围")
    filters: list[FilterCondition] = Field(default_factory=list, description="过滤条件列表")
    sort_by: list[SortSpec] = Field(default_factory=list, description="排序规格列表")
    limit: int = Field(default=100, ge=1, le=10000, description="返回行数限制")
    raw_question: str = Field(default="", description="原始用户问题")


# ============================================================
# Schema Linking 输出
# ============================================================


class LinkedMetric(BaseModel):
    """关联指标。

    Attributes:
        metric_id: 指标 ID。
        name: 指标名称。
        calculation: 计算表达式。
        unit: 单位。
        table_id: 所属源表 ID。
        table_name: 所属源表名。
        match_score: 匹配分数 [0, 1]。
        matched_by: 匹配方式（exact/synonym/fuzzy/vector）。
    """

    model_config = ConfigDict(from_attributes=True)

    metric_id: str
    name: str
    calculation: str = ""
    unit: str | None = None
    table_id: str | None = None
    table_name: str | None = None
    match_score: float = Field(default=1.0, ge=0.0, le=1.0)
    matched_by: str = Field(default="exact", description="匹配方式")


class LinkedDimension(BaseModel):
    """关联维度。

    Attributes:
        dimension_id: 维度 ID。
        name: 维度名称。
        column_name: 对应物理列名。
        table_id: 所属源表 ID。
        table_name: 所属源表名。
        synonyms: 同义词列表。
        is_virtual: 是否为虚拟维度。
        match_score: 匹配分数 [0, 1]。
        matched_by: 匹配方式（exact/synonym/fuzzy/vector）。
    """

    model_config = ConfigDict(from_attributes=True)

    dimension_id: str
    name: str
    column_name: str = ""
    table_id: str | None = None
    table_name: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    is_virtual: bool = False
    match_score: float = Field(default=1.0, ge=0.0, le=1.0)
    matched_by: str = Field(default="exact", description="匹配方式")


class JoinStep(BaseModel):
    """JOIN 路径中的一步。

    Attributes:
        left_table: 左表名。
        right_table: 右表名。
        join_type: JOIN 类型。
        join_condition: JOIN 条件。
    """

    model_config = ConfigDict(from_attributes=True)

    left_table: str
    right_table: str
    join_type: str = "inner"
    join_condition: str = ""


class SemanticContext(BaseModel):
    """语义上下文。

    由 SchemaLinker 产生，包含 Schema Linking 后完整的表、指标、维度、JOIN 路径信息。

    Attributes:
        selected_tables: 选中的源表名列表。
        selected_metrics: 关联指标列表。
        selected_dimensions: 关联维度列表。
        join_path: JOIN 路径列表。
        semantic_model_id: 选中的语义模型 ID。
        semantic_model_name: 语义模型名称。
        filters: 过滤条件列表（Schema Linking 后可能已补充字段映射）。
        warnings: 匹配过程中的警告信息。
    """

    model_config = ConfigDict(from_attributes=True)

    selected_tables: list[str] = Field(default_factory=list, description="选中的源表名")
    selected_metrics: list[LinkedMetric] = Field(default_factory=list, description="关联指标")
    selected_dimensions: list[LinkedDimension] = Field(
        default_factory=list, description="关联维度"
    )
    join_path: list[JoinStep] = Field(default_factory=list, description="JOIN 路径")
    semantic_model_id: str | None = Field(default=None, description="语义模型 ID")
    semantic_model_name: str | None = Field(default=None, description="语义模型名称")
    filters: list[FilterCondition] = Field(default_factory=list, description="过滤条件")
    warnings: list[str] = Field(default_factory=list, description="匹配警告")


# ============================================================
# Semantic Resolver 输出
# ============================================================


class ResolvedTimeCondition(BaseModel):
    """解析后的时间条件。

    Attributes:
        column: 时间字段名。
        start_expr: 起始时间表达式（SQL 表达式或具体值）。
        end_expr: 结束时间表达式。
        raw_text: 原始时间描述。
    """

    model_config = ConfigDict(from_attributes=True)

    column: str = ""
    start_expr: str | None = None
    end_expr: str | None = None
    raw_text: str = ""


class ResolvedFilter(BaseModel):
    """解析后的过滤条件。

    Attributes:
        column: 物理列名（已映射）。
        operator: 操作符。
        value: 过滤值。
        sql_expression: 可选的 SQL 表达式。
        raw_text: 原始条件文本。
    """

    model_config = ConfigDict(from_attributes=True)

    column: str
    operator: str = "="
    value: Any = None
    sql_expression: str | None = None
    raw_text: str = ""


class ResolvedAggregation(BaseModel):
    """解析后的聚合信息。

    Attributes:
        metric_name: 指标名称。
        function: 聚合函数。
        column: 聚合列。
        alias: 别名。
    """

    model_config = ConfigDict(from_attributes=True)

    metric_name: str = ""
    function: AggregationFunction = AggregationFunction.SUM
    column: str = ""
    alias: str = ""


class ResolvedSort(BaseModel):
    """解析后的排序信息。

    Attributes:
        column: 排序列。
        direction: 排序方向。
        alias: 别名（如果有）。
    """

    model_config = ConfigDict(from_attributes=True)

    column: str
    direction: SortDirection = SortDirection.ASC
    alias: str | None = None


class ResolvedQuery(BaseModel):
    """完整结构化查询信息。

    由 SemanticResolver 产生，将 ParsedIntent 和 SemanticContext 转换为
    SQL 生成所需的完整结构化信息。

    Attributes:
        select_columns: SELECT 列列表。
        aggregations: 聚合信息列表。
        time_condition: 时间范围条件。
        filters: 解析后的过滤条件列表。
        sort_by: 排序信息列表。
        group_by: GROUP BY 列列表。
        limit: LIMIT 值。
        join_path: JOIN 路径。
        query_type: 查询类型。
        raw_question: 原始用户问题。
        warnings: 解析过程中的警告。
    """

    model_config = ConfigDict(from_attributes=True)

    select_columns: list[str] = Field(default_factory=list, description="SELECT 列")
    aggregations: list[ResolvedAggregation] = Field(
        default_factory=list, description="聚合信息"
    )
    time_condition: ResolvedTimeCondition | None = Field(
        default=None, description="时间条件"
    )
    filters: list[ResolvedFilter] = Field(default_factory=list, description="过滤条件")
    sort_by: list[ResolvedSort] = Field(default_factory=list, description="排序信息")
    group_by: list[str] = Field(default_factory=list, description="GROUP BY 列")
    limit: int = Field(default=100, ge=1, le=10000, description="LIMIT 值")
    join_path: list[JoinStep] = Field(default_factory=list, description="JOIN 路径")
    query_type: QueryType = Field(default=QueryType.DETAIL, description="查询类型")
    raw_question: str = Field(default="", description="原始用户问题")
    warnings: list[str] = Field(default_factory=list, description="解析警告")
