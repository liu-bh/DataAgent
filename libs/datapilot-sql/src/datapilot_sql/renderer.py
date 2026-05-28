"""SQL 渲染器模块。

提供 SQL AST 到字符串的渲染能力，支持多种方言和格式化输出。

用法::

    from datapilot_sql.renderer import SQLRenderer
    from datapilot_sql.dialect import Dialect

    renderer = SQLRenderer()

    # 渲染为指定方言的 SQL
    sql = renderer.render(ast, dialect=Dialect.POSTGRESQL)

    # 格式化渲染（美化 SQL）
    sql = renderer.render_pretty(ast, dialect=Dialect.MYSQL)

    # 从 SQL 字符串解析为 AST
    ast = renderer.string_to_ast("SELECT * FROM users WHERE id = 1")
"""

from __future__ import annotations

import sqlglot
from sqlglot.expressions import Expression

from datapilot_sql.dialect import Dialect


class SQLRenderer:
    """SQL 渲染器。

    负责将 sqlglot AST 渲染为 SQL 字符串，以及将 SQL 字符串解析为 AST。
    """

    def render(
        self,
        ast: Expression,
        dialect: Dialect = Dialect.POSTGRESQL,
    ) -> str:
        """将 AST 渲染为指定方言的 SQL 字符串（单行）。

        Args:
            ast: sqlglot AST 表达式。
            dialect: 目标方言。

        Returns:
            SQL 字符串。
        """
        return ast.sql(dialect=dialect.value)

    def render_pretty(
        self,
        ast: Expression,
        dialect: Dialect = Dialect.POSTGRESQL,
    ) -> str:
        """将 AST 渲染为格式化的 SQL 字符串（多行美化输出）。

        Args:
            ast: sqlglot AST 表达式。
            dialect: 目标方言。

        Returns:
            格式化的 SQL 字符串。
        """
        return ast.sql(dialect=dialect.value, pretty=True)

    def ast_to_string(
        self,
        ast: Expression,
    ) -> str:
        """使用默认方言将 AST 渲染为 SQL 字符串。

        默认使用 PostgreSQL 方言。

        Args:
            ast: sqlglot AST 表达式。

        Returns:
            SQL 字符串。
        """
        return self.render(ast, dialect=Dialect.POSTGRESQL)

    def string_to_ast(
        self,
        sql: str,
        dialect: Dialect = Dialect.POSTGRESQL,
    ) -> Expression:
        """将 SQL 字符串解析为 AST。

        Args:
            sql: SQL 字符串。
            dialect: SQL 方言。

        Returns:
            sqlglot AST 表达式。

        Raises:
            ValueError: SQL 解析失败时抛出。
        """
        try:
            result = sqlglot.parse_one(sql, read=dialect.value)
            if result is None:
                raise ValueError(f"SQL 解析失败: {sql}")
            return result
        except Exception as e:
            raise ValueError(f"SQL 解析失败: {sql}, 错误: {e}") from e
