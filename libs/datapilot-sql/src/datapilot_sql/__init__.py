"""DataPilot SQL 库。

提供 sqlglot AST 封装、方言适配、SQL 构建与验证能力。

导出公共接口供各微服务使用。
"""

from datapilot_sql.builder import Aggregate, SQLBuilder, cond
from datapilot_sql.dialect import (
    CompatibilityIssue,
    Dialect,
    check_compatibility,
    get_dialect,
)
from datapilot_sql.renderer import SQLRenderer
from datapilot_sql.transformer import SQLTransformer
from datapilot_sql.validator import SQLValidator, ValidationResult

__all__ = [
    # 方言
    "Dialect",
    "get_dialect",
    "check_compatibility",
    "CompatibilityIssue",
    # 构建
    "SQLBuilder",
    "Aggregate",
    "cond",
    # 验证
    "SQLValidator",
    "ValidationResult",
    # 转换
    "SQLTransformer",
    # 渲染
    "SQLRenderer",
]
