"""SQL 风险检测器。

通过 sqlglot AST 解析 SQL，识别危险操作并返回对应风险等级。
"""

from __future__ import annotations

import sqlglot
import structlog
from sqlglot import exp

from datapilot_guardrail.models import RiskLevel

logger = structlog.get_logger(__name__)

# 危险 DDL 语句类型
_DDL_TYPES: set[type[exp.Expression]] = {
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
}

# 危险 DML 写操作类型（非 SELECT）
_DML_WRITE_TYPES: set[type[exp.Expression]] = {
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
}

# 系统表前缀模式
_SYSTEM_TABLE_PREFIXES: list[str] = [
    "information_schema",
    "mysql",
    "pg_catalog",
    "sys",
]


class SQLRiskDetector:
    """SQL 风险检测器。

    基于 sqlglot AST 分析 SQL 语句，检测 DDL、DML 写操作、系统表访问、
    过深子查询等风险，并返回对应的风险等级和原因描述。
    """

    def check(self, sql: str, dialect: str = "mysql") -> tuple[RiskLevel, str]:
        """检测 SQL 风险等级。

        Args:
            sql: 待检测的 SQL 语句。
            dialect: SQL 方言，默认 "mysql"。

        Returns:
            (风险等级, 原因描述) 元组。SAFE 时原因为空字符串。
        """
        # 解析 SQL 为 AST
        try:
            tree = sqlglot.parse_one(sql, dialect=dialect, error_level=sqlglot.ErrorLevel.WARN)
        except sqlglot.errors.ParseError as exc:
            logger.warning("SQL 解析失败，视为 BLOCKED", sql=sql[:200], error=str(exc))
            return RiskLevel.BLOCKED, f"SQL 语法错误: {exc}"

        if tree is None:
            return RiskLevel.BLOCKED, "无法解析 SQL 语句"

        # 1. 检测 DDL 操作 → BLOCKED
        risk, reason = self._check_ddl(tree)
        if risk == RiskLevel.BLOCKED:
            return risk, reason

        # 2. 检测 DML 写操作 → BLOCKED
        risk, reason = self._check_dml_write(tree)
        if risk == RiskLevel.BLOCKED:
            return risk, reason

        # 3. 检测系统表访问 → HIGH
        risk, reason = self._check_system_tables(tree)
        if risk == RiskLevel.HIGH:
            return risk, reason

        # 4. 检测子查询深度 → MEDIUM
        risk, reason = self._check_subquery_depth(tree, max_depth=3)
        if risk == RiskLevel.MEDIUM:
            return risk, reason

        # 5. 正常 SELECT → 根据复杂度返回 SAFE 或 LOW
        return self._assess_select_complexity(tree)

    def _check_ddl(self, tree: exp.Expression) -> tuple[RiskLevel, str]:
        """检测 DDL 语句（CREATE/DROP/ALTER/TRUNCATE）。

        Args:
            tree: SQL AST 根节点。

        Returns:
            如果检测到 DDL，返回 (BLOCKED, 原因)；否则返回 (SAFE, "")。
        """
        # tree 本身可能就是顶层节点
        if isinstance(tree, tuple(_DDL_TYPES)):
            stmt_kind = tree.__class__.__name__.upper()
            return RiskLevel.BLOCKED, f"不允许执行 DDL 操作: {stmt_kind}"

        # 遍历子树查找 DDL
        for ddl_type in _DDL_TYPES:
            if tree.find(ddl_type):
                return RiskLevel.BLOCKED, f"不允许执行 DDL 操作: {ddl_type.__name__.upper()}"

        return RiskLevel.SAFE, ""

    def _check_dml_write(self, tree: exp.Expression) -> tuple[RiskLevel, str]:
        """检测 DML 写操作（INSERT/UPDATE/DELETE）。

        Args:
            tree: SQL AST 根节点。

        Returns:
            如果检测到写操作，返回 (BLOCKED, 原因)；否则返回 (SAFE, "")。
        """
        for write_type in _DML_WRITE_TYPES:
            if isinstance(tree, write_type):
                return RiskLevel.BLOCKED, f"不允许执行写操作: {write_type.__name__.upper()}"

        # 也检查子树（例如 CTE 中的写操作）
        for write_type in _DML_WRITE_TYPES:
            if tree.find(write_type):
                return RiskLevel.BLOCKED, f"检测到写操作: {write_type.__name__.upper()}"

        return RiskLevel.SAFE, ""

    def _check_system_tables(self, tree: exp.Expression) -> tuple[RiskLevel, str]:
        """检测系统表访问。

        Args:
            tree: SQL AST 根节点。

        Returns:
            如果访问系统表，返回 (HIGH, 原因)；否则返回 (SAFE, "")。
        """
        # 遍历所有表引用
        for table_node in tree.find_all(exp.Table):
            table_name = table_node.name.lower() if table_node.name else ""
            # 带有 db/schema 限定的情况
            db_name = table_node.db if table_node.db else ""
            catalog = (
                table_node.catalog if hasattr(table_node, "catalog") and table_node.catalog else ""
            )

            full_name_parts = [p for p in [catalog, db_name, table_name] if p]
            full_name = ".".join(full_name_parts)

            for prefix in _SYSTEM_TABLE_PREFIXES:
                if full_name.startswith(prefix.lower()):
                    return RiskLevel.HIGH, f"禁止访问系统表: {full_name}"
                # 也检查表名本身是否是系统表前缀
                if table_name and table_name.startswith(prefix.lower()):
                    return RiskLevel.HIGH, f"禁止访问系统表: {table_name}"

        return RiskLevel.SAFE, ""

    def _check_subquery_depth(
        self, tree: exp.Expression, max_depth: int = 3
    ) -> tuple[RiskLevel, str]:
        """检测子查询嵌套深度。

        Args:
            tree: SQL AST 根节点。
            max_depth: 允许的最大子查询嵌套层数。

        Returns:
            如果超过深度限制，返回 (MEDIUM, 原因)；否则返回 (SAFE, "")。
        """
        max_found = self._max_subquery_depth(tree)
        if max_found > max_depth:
            return (
                RiskLevel.MEDIUM,
                f"子查询嵌套深度 {max_found} 超过限制 {max_depth}，可能影响性能",
            )
        return RiskLevel.SAFE, ""

    def _max_subquery_depth(self, node: exp.Expression) -> int:
        """递归计算 AST 节点的最大子查询嵌套深度。

        Args:
            node: 当前 AST 节点。

        Returns:
            最大子查询嵌套深度。
        """
        max_depth = 0
        for child in node.iter_expressions():
            if isinstance(child, (exp.Subquery, exp.Select)):
                child_depth = 1 + self._max_subquery_depth(child)
                max_depth = max(max_depth, child_depth)
            else:
                child_depth = self._max_subquery_depth(child)
                max_depth = max(max_depth, child_depth)
        return max_depth

    def _assess_select_complexity(self, tree: exp.Expression) -> tuple[RiskLevel, str]:
        """评估 SELECT 语句复杂度。

        根据是否包含 JOIN、GROUP BY、HAVING 等复杂子句，
        返回 SAFE 或 LOW。

        Args:
            tree: SQL AST 根节点。

        Returns:
            (SAFE/LOW, 原因)。
        """
        complexity_indicators = 0
        if tree.find(exp.Join):
            complexity_indicators += 1
        if tree.find(exp.Group):
            complexity_indicators += 1
        if tree.find(exp.Having):
            complexity_indicators += 1
        if tree.find(exp.Window):
            complexity_indicators += 1
        if tree.find(exp.Order):
            complexity_indicators += 1

        if complexity_indicators >= 3:
            return RiskLevel.LOW, "查询复杂度较高，建议拆分为多个简单查询"
        if complexity_indicators >= 1:
            return RiskLevel.LOW, "查询包含复杂子句"

        return RiskLevel.SAFE, ""
