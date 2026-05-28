"""SQL AST 转换器模块。

提供 AST 级别的 SQL 转换能力，包括：
- RBAC WHERE 条件注入（行级权限）
- 列移除（列级权限）
- 方言转换
- 自动添加 LIMIT

用法::

    from datapilot_sql.transformer import SQLTransformer
    from datapilot_sql.dialect import Dialect

    transformer = SQLTransformer()

    # 注入 RBAC 条件
    ast = transformer.inject_where(ast, "region IN ('华东', '华南')")

    # 移除无权限列
    ast = transformer.remove_columns(ast, ["phone", "id_card"])

    # 方言转换
    ast = transformer.convert_dialect(ast, Dialect.POSTGRESQL, Dialect.MYSQL)

    # 添加 LIMIT
    ast = transformer.add_limit_if_missing(ast, default=1000)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlglot
from sqlglot.expressions import (
    Alias,
    And,
    Column,
    Expression,
    Limit,
    Literal,
    Where,
)

if TYPE_CHECKING:
    from datapilot_sql.dialect import Dialect


class SQLTransformer:
    """SQL AST 转换器。

    在 AST 级别对 SQL 进行安全转换，保证不通过字符串拼接修改 SQL。
    """

    def inject_where(
        self,
        ast: Expression,
        condition: str | Expression,
    ) -> Expression:
        """注入 RBAC WHERE 条件（行级权限）。

        如果已有 WHERE 条件，则以 AND 方式追加；否则新增 WHERE 子句。

        Args:
            ast: 原始 AST。
            condition: 要注入的条件，支持 SQL 字符串或 sqlglot 表达式。

        Returns:
            注入条件后的新 AST（不修改原始 AST）。
        """
        ast = ast.copy()

        # 解析条件
        if isinstance(condition, str):
            condition_expr = sqlglot.parse_one(condition)
        else:
            condition_expr = condition.copy()

        existing_where = ast.find(Where)
        if existing_where is not None:
            # 已有 WHERE，合并条件
            combined = And(
                this=existing_where.this.copy(),
                expression=condition_expr,
            )
            existing_where.set("this", combined)
        else:
            # 新增 WHERE
            ast.set("where", Where(this=condition_expr))

        return ast

    def remove_columns(
        self,
        ast: Expression,
        columns: list[str],
    ) -> Expression:
        """移除指定列（列级权限）。

        从 SELECT 子句中移除指定的列名。支持移除带别名的列。

        Args:
            ast: 原始 AST。
            columns: 要移除的列名列表。

        Returns:
            移除列后的新 AST（不修改原始 AST）。
        """
        ast = ast.copy()
        columns_to_remove = set(columns)

        select_exprs = ast.args.get("expressions", [])
        new_exprs: list[Expression] = []

        for expr in select_exprs:
            if self._should_remove_column(expr, columns_to_remove):
                continue
            new_exprs.append(expr)

        ast.set("expressions", new_exprs)
        return ast

    def convert_dialect(
        self,
        ast: Expression,
        source_dialect: Dialect,
        target_dialect: Dialect,
    ) -> Expression:
        """转换 SQL 方言。

        将源方言的 AST 转换为目标方言的 AST。

        Args:
            ast: 原始 AST。
            source_dialect: 源方言。
            target_dialect: 目标方言。

        Returns:
            转换方言后的新 AST。
        """
        try:
            # 使用 sqlglot 内置方言转换：先转为目标方言的 SQL 字符串，再解析回 AST
            sql_str = ast.sql(dialect=target_dialect.value)
            result = sqlglot.parse_one(sql_str, read=target_dialect.value)
            return result
        except Exception:
            # 降级：直接返回 AST 副本
            return ast.copy()

    def add_limit_if_missing(
        self,
        ast: Expression,
        default: int = 1000,
    ) -> Expression:
        """如果 AST 没有 LIMIT 子句，自动添加。

        用于防止全表扫描，保障查询安全。

        Args:
            ast: 原始 AST。
            default: 默认 LIMIT 值。

        Returns:
            添加 LIMIT 后的 AST（如果已有 LIMIT 则返回原 AST 的副本）。
        """
        ast = ast.copy()

        existing_limit = ast.find(Limit)
        if existing_limit is None:
            limit_expr = Limit(expression=Literal.number(default))
            ast.set("limit", limit_expr)

        return ast

    @staticmethod
    def _should_remove_column(expr: Expression, columns_to_remove: set[str]) -> bool:
        """判断是否应该移除该列表达式。

        Args:
            expr: SELECT 子句中的表达式。
            columns_to_remove: 要移除的列名集合。

        Returns:
            True 表示应该移除。
        """
        # 直接列引用
        if isinstance(expr, Column):
            return expr.name in columns_to_remove

        # 带别名的列
        if isinstance(expr, Alias):
            inner = expr.this
            if isinstance(inner, Column):
                return inner.name in columns_to_remove
            # 也检查别名本身
            alias_name = expr.alias
            if alias_name and alias_name in columns_to_remove:
                return True

        return False
