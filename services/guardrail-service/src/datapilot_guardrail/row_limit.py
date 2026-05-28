"""行数限制检查器。

通过 sqlglot AST 提取 SQL 中的 LIMIT 值，并在必要时施加默认限制。
"""

from __future__ import annotations

import sqlglot
import structlog

logger = structlog.get_logger(__name__)


class RowLimitEnforcer:
    """行数限制检查器。

    检查 SQL 是否包含 LIMIT 子句，如果未指定或超过允许的最大值，
    则返回建议的实际限制值。
    """

    def __init__(self, default_limit: int = 10000) -> None:
        """初始化行数限制检查器。

        Args:
            default_limit: 默认最大行数限制。
        """
        self.default_limit = default_limit

    def check(self, sql: str, max_rows: int | None = None) -> tuple[bool, int]:
        """检查 SQL 的行数限制。

        如果 SQL 中已有 LIMIT 且不超过 max_rows，直接放行。
        如果 SQL 没有 LIMIT 或 LIMIT 超过 max_rows，返回需要施加的限制值。

        Args:
            sql: 待检查的 SQL 语句。
            max_rows: 允许的最大行数，None 时使用 default_limit。

        Returns:
            (需要施加限制, 实际 limit 值)。
            如果需要施加限制为 True，调用方应在 SQL 上追加/修改 LIMIT。
        """
        effective_limit = max_rows if max_rows is not None else self.default_limit

        try:
            tree = sqlglot.parse_one(sql, error_level=sqlglot.ErrorLevel.WARN)
        except sqlglot.errors.ParseError as exc:
            logger.warning("SQL 解析失败，使用默认限制", sql=sql[:200], error=str(exc))
            return True, effective_limit

        if tree is None:
            return True, effective_limit

        # 提取 LIMIT 值
        limit_node = tree.find(sqlglot.exp.Limit)
        if limit_node is None:
            logger.info("SQL 未包含 LIMIT 子句，将施加限制", limit=effective_limit)
            return True, effective_limit

        # 获取 LIMIT 的值
        limit_value = self._extract_limit_value(limit_node)
        if limit_value is None:
            # 无法提取 LIMIT 值（例如表达式），使用默认限制
            logger.warning("LIMIT 值无法提取为整数，使用默认限制")
            return True, effective_limit

        if limit_value > effective_limit:
            logger.info(
                "SQL LIMIT 超过最大限制，将截断",
                original_limit=limit_value,
                effective_limit=effective_limit,
            )
            return True, effective_limit

        # LIMIT 在允许范围内
        return False, limit_value

    @staticmethod
    def _extract_limit_value(limit_node: sqlglot.exp.Limit) -> int | None:
        """从 LIMIT AST 节点提取整数值。

        Args:
            limit_node: sqlglot LIMIT 表达式节点。

        Returns:
            LIMIT 整数值，如果无法提取则返回 None。
        """
        # LIMIT 表达式通常包含一个 Literal 或 Number 子节点
        for child in limit_node.iter_expressions():
            if isinstance(child, sqlglot.exp.Literal) and child.is_int:
                return int(child.this)
            if isinstance(child, sqlglot.exp.Number):
                return int(child.this)
            # 尝试直接获取字符串形式的数字
            if hasattr(child, "this") and isinstance(child.this, str):
                try:
                    return int(child.this)
                except (ValueError, TypeError):
                    pass

        return None
