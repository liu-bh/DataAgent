"""意图识别模块。

NL2SQL 流程前 4 步：意图路由 → Intent Parsing → Schema Linking → Semantic Resolution。

主要导出:
    - IntentType, QueryType: 意图/查询类型枚举
    - IntentResult, ParsedIntent, SemanticContext, ResolvedQuery: 核心数据结构
    - IntentRouter: 意图路由器（规则 + LLM）
    - IntentParser: 意图解析器（LLM 结构化输出）
    - SchemaLinker: Schema Linker（指标/维度映射 + JOIN 推导）
    - SemanticResolver: 语义解析器（时间/过滤/聚合映射）
"""

from datapilot_sqlgen.intent.parser import IntentParser
from datapilot_sqlgen.intent.resolver import SemanticResolver
from datapilot_sqlgen.intent.router import IntentRouter
from datapilot_sqlgen.intent.schema_linker import SchemaLinker
from datapilot_sqlgen.intent.types import (
    AggregationFunction,
    FilterCondition,
    IntentResult,
    IntentType,
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

__all__ = [
    # 枚举
    "AggregationFunction",
    "IntentType",
    "QueryType",
    "SortDirection",
    # 核心类
    "IntentRouter",
    "IntentParser",
    "SchemaLinker",
    "SemanticResolver",
    # 数据结构
    "IntentResult",
    "ParsedIntent",
    "SemanticContext",
    "ResolvedQuery",
    "FilterCondition",
    "JoinStep",
    "LinkedDimension",
    "LinkedMetric",
    "ResolvedAggregation",
    "ResolvedFilter",
    "ResolvedSort",
    "ResolvedTimeCondition",
    "SortSpec",
    "TimeRange",
]
