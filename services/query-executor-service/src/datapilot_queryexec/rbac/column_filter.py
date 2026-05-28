"""列级权限过滤器。

通过 sqlglot AST 移除 SELECT 列实现列权限控制。
不修改原始 SQL 字符串，所有操作在 AST 层面完成。
"""

from __future__ import annotations

import structlog

import sqlglot
from sqlglot.expressions import Alias, Column, Count, Expression, Star

logger = structlog.get_logger(__name__)


class ColumnFilter:
    """通过 sqlglot AST 移除 SELECT 列实现列权限控制。"""

    @staticmethod
    def apply(
        sql: str, hidden_columns: list[str], dialect: str = "mysql"
    ) -> tuple[str, list[str]]:
        """移除 SQL 中指定的列。

        Args:
            sql: 原始 SQL。
            hidden_columns: 需要隐藏的列名列表。
            dialect: SQL 方言。

        Returns:
            (filtered_sql, removed_columns): 过滤后的 SQL 和实际移除的列。

        Raises:
            ValueError: 当 SQL 无法解析时抛出。
        """
        if not hidden_columns:
            logger.debug("列级权限: 隐藏列列表为空，跳过过滤")
            return sql, []

        # 解析 SQL 为 AST
        try:
            ast = sqlglot.parse_one(sql, dialect=dialect)
        except Exception as e:
            logger.error("列级权限: SQL 解析失败", error=str(e), sql=sql)
            raise ValueError(f"SQL 解析失败: {e}") from e

        ast = ast.copy()
        columns_to_remove = set(hidden_columns)
        removed: list[str] = []

        select_exprs = ast.args.get("expressions", [])
        new_exprs: list[Expression] = []

        for expr in select_exprs:
            if ColumnFilter._should_remove(expr, columns_to_remove, removed):
                continue
            new_exprs.append(expr)

        # 如果所有列都被移除，保留 COUNT(*) 占位，防止 SQL 语法错误
        if not new_exprs:
            logger.warning(
                "列级权限: 所有列都被移除，使用 COUNT(*) 占位",
                removed=removed,
            )
            count_star = Count(this=Star())
            new_exprs = [count_star]

        ast.set("expressions", new_exprs)

        result = ast.sql(dialect=dialect)
        logger.debug(
            "列级权限: 列过滤完成",
            removed=removed,
            remaining=len(new_exprs),
            result=result,
        )
        return result, sorted(removed)

    @staticmethod
    def _should_remove(
        expr: Expression,
        columns_to_remove: set[str],
        removed: list[str],
    ) -> bool:
        """判断是否应该移除该列表达式。

        支持以下列形式：
        - 直接列引用: column_name
        - 带表名: table.column_name
        - 带别名: table.column_name AS alias

        Args:
            expr: SELECT 子句中的表达式。
            columns_to_remove: 要移除的列名集合。
            removed: 已移除列名列表（用于记录）。

        Returns:
            True 表示应该移除。
        """
        column_name = ColumnFilter._extract_column_name(expr)

        if column_name and column_name in columns_to_remove:
            removed.append(column_name)
            return True

        # 对于带别名的列，也检查别名本身
        alias_name = ColumnFilter._extract_alias_name(expr)
        if alias_name and alias_name in columns_to_remove and alias_name != column_name:
            removed.append(alias_name)
            return True

        return False

    @staticmethod
    def _extract_column_name(expr: Expression) -> str | None:
        """从表达式中提取列名。

        支持 Column 和 Alias 两种形式。
        对于 Alias，提取内部列名（非别名）。

        Args:
            expr: SELECT 子句中的表达式。

        Returns:
            列名，如果无法提取则返回 None。
        """
        # 直接列引用
        if isinstance(expr, Column):
            return expr.name

        # 带别名的列：提取原始列名
        if isinstance(expr, Alias):
            inner = expr.this
            if isinstance(inner, Column):
                return inner.name

        return None

    @staticmethod
    def _extract_alias_name(expr: Expression) -> str | None:
        """从表达式中提取别名。

        Args:
            expr: SELECT 子句中的表达式。

        Returns:
            别名，如果没有别名则返回 None。
        """
        if isinstance(expr, Alias):
            alias_name = expr.alias
            if alias_name:
                return alias_name
        return None
