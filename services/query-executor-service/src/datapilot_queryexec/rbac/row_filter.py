"""行级权限过滤器。

通过 sqlglot AST 注入 WHERE 条件实现行级权限控制。
不修改原始 SQL 字符串，所有操作在 AST 层面完成。
"""

from __future__ import annotations

import sqlglot
import structlog
from sqlglot.expressions import And, Where

logger = structlog.get_logger(__name__)


class RowFilter:
    """通过 sqlglot AST 注入 WHERE 条件实现行级权限。"""

    @staticmethod
    def apply(sql: str, filter_expression: str, dialect: str = "mysql") -> str:
        """在 SQL 的 WHERE 子句中注入过滤条件。

        如果 SQL 已有 WHERE，使用 AND 连接。
        如果 SQL 没有 WHERE，添加 WHERE 子句。

        Args:
            sql: 原始 SQL。
            filter_expression: 过滤表达式（如 "department_id = 100"）。
            dialect: SQL 方言。

        Returns:
            注入过滤条件后的 SQL。

        Raises:
            ValueError: 当 SQL 或过滤表达式无法解析时抛出。
        """
        if not filter_expression:
            logger.debug("行级权限: 过滤表达式为空，跳过注入")
            return sql

        # 解析原始 SQL 为 AST
        try:
            ast = sqlglot.parse_one(sql, dialect=dialect)
        except Exception as e:
            logger.error("行级权限: SQL 解析失败", error=str(e), sql=sql)
            raise ValueError(f"SQL 解析失败: {e}") from e

        # 解析过滤条件为 AST 表达式
        try:
            condition_expr = sqlglot.parse_one(filter_expression, dialect=dialect)
        except Exception as e:
            logger.error("行级权限: 过滤表达式解析失败", error=str(e), expression=filter_expression)
            raise ValueError(f"过滤表达式解析失败: {e}") from e

        # 复制 AST，避免修改原始对象
        ast = ast.copy()

        # 查找现有 WHERE 条件
        existing_where = ast.find(Where)
        if existing_where is not None:
            # 已有 WHERE，使用 AND 追加条件
            combined = And(
                this=existing_where.this.copy(),
                expression=condition_expr,
            )
            existing_where.set("this", combined)
            logger.debug(
                "行级权限: 追加 AND 条件",
                original=sql,
                injected=filter_expression,
            )
        else:
            # 没有 WHERE，新增 WHERE 子句
            ast.set("where", Where(this=condition_expr))
            logger.debug(
                "行级权限: 新增 WHERE 子句",
                original=sql,
                injected=filter_expression,
            )

        # 渲染回 SQL 字符串
        result = ast.sql(dialect=dialect)
        logger.debug("行级权限: 注入完成", result=result)
        return result
