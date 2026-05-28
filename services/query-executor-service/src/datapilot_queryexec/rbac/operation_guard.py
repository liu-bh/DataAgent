"""操作级权限守卫。

通过 sqlglot AST 判断 SQL 的操作类型（SELECT/INSERT/UPDATE/DELETE/DDL），
并与用户允许的操作类型进行匹配。
"""

from __future__ import annotations

import structlog

import sqlglot
from sqlglot import exp

from datapilot_queryexec.rbac.models import OperationType

logger = structlog.get_logger(__name__)

# DDL 语句类型集合
_DDL_TYPES: set[type[exp.Expression]] = {
    exp.Create,
    exp.Alter,
    exp.Drop,
    exp.TruncateTable,
}

# DML 写操作类型集合
_WRITE_TYPES: set[type[exp.Expression]] = {
    exp.Insert,
    exp.Update,
    exp.Delete,
}


class OperationGuard:
    """操作级权限守卫。"""

    @staticmethod
    def check(
        sql: str, allowed_operations: list[OperationType]
    ) -> tuple[bool, str]:
        """检查 SQL 操作类型是否在允许范围内。

        使用 sqlglot AST 判断 SQL 的操作类型：
        - SELECT → OperationType.READ
        - INSERT/UPDATE/DELETE → OperationType.WRITE
        - CREATE/ALTER/DROP/TRUNCATE → OperationType.DDL

        Args:
            sql: 待检查的 SQL。
            allowed_operations: 允许的操作类型列表。

        Returns:
            (allowed, blocked_reason): 是否允许和拒绝原因（如果被拒绝）。
        """
        # 解析 SQL
        try:
            ast = sqlglot.parse_one(sql)
        except Exception as e:
            logger.error("操作权限: SQL 解析失败", error=str(e), sql=sql)
            return False, f"SQL 解析失败: {e}"

        # 判断操作类型
        operation_type = OperationGuard._detect_operation_type(ast)

        if operation_type is None:
            # 无法识别的操作类型，默认允许（如 EXPLAIN、SET 等）
            logger.debug("操作权限: 无法识别的操作类型，默认允许", sql=sql)
            return True, ""

        # 检查是否在允许范围内
        if operation_type in allowed_operations:
            logger.debug(
                "操作权限: 检查通过",
                operation=operation_type.value,
                allowed=[op.value for op in allowed_operations],
            )
            return True, ""

        reason = (
            f"操作类型 '{operation_type.value}' 不在允许范围内，"
            f"允许的操作: {[op.value for op in allowed_operations]}"
        )
        logger.info("操作权限: 检查未通过", reason=reason)
        return False, reason

    @staticmethod
    def _detect_operation_type(ast: exp.Expression) -> OperationType | None:
        """通过 AST 节点类型判断 SQL 操作类型。

        Args:
            ast: 解析后的 sqlglot AST。

        Returns:
            操作类型，无法识别时返回 None。
        """
        for ddl_type in _DDL_TYPES:
            if isinstance(ast, ddl_type):
                return OperationType.DDL

        for write_type in _WRITE_TYPES:
            if isinstance(ast, write_type):
                return OperationType.WRITE

        if isinstance(ast, exp.Select):
            return OperationType.READ

        return None
