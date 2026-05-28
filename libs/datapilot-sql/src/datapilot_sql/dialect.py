"""SQL 方言管理模块。

提供 DataPilot 支持的 SQL 方言枚举，以及方言工厂方法。
同时包含方言兼容性检查能力，用于在 AST 阶段发现不兼容的语法。

用法::

    from datapilot_sql.dialect import Dialect, get_dialect

    dialect = get_dialect(Dialect.POSTGRESQL)
    result = check_compatibility(ast, Dialect.CLICKHOUSE)
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlglot.dialects import (
    ClickHouse,
    MySQL,
    Postgres,
)
from sqlglot.dialects.doris import Doris
from sqlglot.dialects.starrocks import StarRocks
from sqlglot.expressions import Expression, Join, With

if TYPE_CHECKING:
    from sqlglot import Dialect as SqlglotDialect


class Dialect(enum.Enum):
    """DataPilot 支持的 SQL 方言枚举。"""

    MYSQL = "mysql"
    POSTGRESQL = "postgres"
    DORIS = "doris"
    STARROCKS = "starrocks"
    CLICKHOUSE = "clickhouse"


# 方言枚举值 → sqlglot Dialect 类的映射
_DIALECT_CLASS_MAP: dict[Dialect, type[SqlglotDialect]] = {
    Dialect.MYSQL: MySQL,
    Dialect.POSTGRESQL: Postgres,
    Dialect.DORIS: Doris,
    Dialect.STARROCKS: StarRocks,
    Dialect.CLICKHOUSE: ClickHouse,
}


def get_dialect(dialect: Dialect) -> SqlglotDialect:
    """获取 sqlglot 方言实例。

    Args:
        dialect: DataPilot 方言枚举。

    Returns:
        sqlglot Dialect 实例。
    """
    cls = _DIALECT_CLASS_MAP[dialect]
    return cls()


# 方言兼容性限制定义
# key: 方言
# value: 不支持的特性列表，每项为 (特性名称, 说明)
_DIALECT_LIMITATIONS: dict[Dialect, list[tuple[str, str]]] = {
    Dialect.CLICKHOUSE: [
        ("multi_table_join", "ClickHouse 不支持多表 JOIN，需要使用子查询替代"),
        ("with_recursive", "ClickHouse 不支持 WITH RECURSIVE"),
        ("update_join", "ClickHouse 不支持 UPDATE ... JOIN 语法"),
        ("nested_subquery_in_join", "ClickHouse JOIN 条件中不支持嵌套子查询"),
    ],
    Dialect.DORIS: [
        ("with_recursive", "Doris 不支持 WITH RECURSIVE"),
        ("full_outer_join", "Doris 对 FULL OUTER JOIN 的支持有限"),
        ("lateral_view", "Doris 不支持 LATERAL VIEW 语法"),
    ],
    Dialect.STARROCKS: [
        ("with_recursive", "StarRocks 不支持 WITH RECURSIVE"),
        ("full_outer_join", "StarRocks 对 FULL OUTER JOIN 的支持有限"),
    ],
}


class CompatibilityIssue:
    """方言兼容性问题。"""

    __slots__ = ("feature", "description", "severity")

    def __init__(self, feature: str, description: str, severity: str = "error") -> None:
        """初始化兼容性问题。

        Args:
            feature: 不支持的特性名称。
            description: 问题描述。
            severity: 严重程度，取值 "error" 或 "warning"。
        """
        self.feature = feature
        self.description = description
        self.severity = severity

    def __repr__(self) -> str:
        return (
            f"CompatibilityIssue(feature={self.feature!r}, "
            f"description={self.description!r}, severity={self.severity!r})"
        )


def check_compatibility(
    ast: Expression,
    target_dialect: Dialect,
) -> list[CompatibilityIssue]:
    """检查 AST 在目标方言下的兼容性。

    遍历 AST 节点，对照方言限制列表检测不兼容的语法。

    Args:
        ast: sqlglot AST 表达式。
        target_dialect: 目标方言。

    Returns:
        兼容性问题列表，为空表示完全兼容。
    """
    issues: list[CompatibilityIssue] = []

    # 如果目标方言没有已知限制，直接返回
    limitations = _DIALECT_LIMITATIONS.get(target_dialect, [])
    if not limitations:
        return issues

    # 将限制转为查找集合
    unsupported_features = {item[0]: item[1] for item in limitations}

    # 遍历 AST 检测特定模式
    _walk_ast_for_compatibility(ast, unsupported_features, issues)

    return issues


def _walk_ast_for_compatibility(
    node: Expression,
    unsupported: dict[str, str],
    issues: list[CompatibilityIssue],
) -> None:
    """递归遍历 AST 节点检查兼容性。

    Args:
        node: 当前 AST 节点。
        unsupported: 不支持的特性映射 {特性名: 描述}。
        issues: 收集兼容性问题的列表。
    """
    # 检查 WITH RECURSIVE（sqlglot v30 中 With 节点有 recursive 参数）
    if isinstance(node, With) and node.args.get("recursive"):
        feature_key = "with_recursive"
        if feature_key in unsupported:
            issues.append(
                CompatibilityIssue(
                    feature=feature_key,
                    description=unsupported[feature_key],
                    severity="error",
                )
            )

    # 检查隐式多表 JOIN（逗号连接，如 FROM a, b）
    # sqlglot v30 中逗号连接解析为 Join 节点（kind=None, side=None）
    if isinstance(node, Join):
        side = node.args.get("side")
        kind = node.args.get("kind")
        # 逗号连接：side 和 kind 均为 None
        if side is None and kind is None:
            feature_key = "multi_table_join"
            if feature_key in unsupported:
                issues.append(
                    CompatibilityIssue(
                        feature=feature_key,
                        description=unsupported[feature_key],
                        severity="error",
                    )
                )
        # FULL OUTER JOIN：side="FULL", kind="OUTER"
        elif side is not None and "FULL" in str(side).upper():
            feature_key = "full_outer_join"
            if feature_key in unsupported:
                issues.append(
                    CompatibilityIssue(
                        feature=feature_key,
                        description=unsupported[feature_key],
                        severity="warning",
                    )
                )

    # 递归检查子节点
    for child in node.iter_expressions():
        _walk_ast_for_compatibility(child, unsupported, issues)
