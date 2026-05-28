"""RBAC 权限检查器（编排层）。

组合行级权限、列级权限、操作级权限和数据脱敏，
提供统一的权限检查入口。
"""

from __future__ import annotations

import structlog

from datapilot_queryexec.rbac.column_filter import ColumnFilter
from datapilot_queryexec.rbac.masking import DataMasker
from datapilot_queryexec.rbac.models import PermissionRule, RBACCheckResult
from datapilot_queryexec.rbac.operation_guard import OperationGuard
from datapilot_queryexec.rbac.row_filter import RowFilter

logger = structlog.get_logger(__name__)


class RBACChecker:
    """RBAC 权限检查器，组合行级+列级+操作级权限。

    检查流程：
    1. 操作权限检查（OperationGuard）→ 如果不允许，直接返回 blocked
    2. 行级权限注入（RowFilter）→ 修改 SQL
    3. 列级权限过滤（ColumnFilter）→ 修改 SQL
    4. 返回检查结果
    """

    def __init__(
        self,
        row_filter: RowFilter | None = None,
        column_filter: ColumnFilter | None = None,
        operation_guard: OperationGuard | None = None,
        data_masker: DataMasker | None = None,
    ) -> None:
        """初始化 RBAC 检查器。

        Args:
            row_filter: 行级权限过滤器，默认使用 RowFilter。
            column_filter: 列级权限过滤器，默认使用 ColumnFilter。
            operation_guard: 操作权限守卫，默认使用 OperationGuard。
            data_masker: 数据脱敏器，默认使用 DataMasker。
        """
        self._row_filter = row_filter or RowFilter()
        self._column_filter = column_filter or ColumnFilter()
        self._operation_guard = operation_guard or OperationGuard()
        self._data_masker = data_masker or DataMasker()

    def check(
        self,
        sql: str,
        permission: PermissionRule,
        dialect: str = "mysql",
    ) -> RBACCheckResult:
        """执行完整的 RBAC 检查。

        Args:
            sql: 待检查的 SQL。
            permission: 用户权限规则。
            dialect: SQL 方言。

        Returns:
            RBAC 检查结果，包含是否通过、过滤后的 SQL 等信息。
        """
        logger.info(
            "RBAC 检查: 开始",
            user_id=permission.user_id,
            tenant_id=permission.tenant_id,
            role=permission.role,
        )

        # 第一步：操作权限检查
        allowed, blocked_reason = self._operation_guard.check(sql, permission.allowed_operations)
        if not allowed:
            logger.info(
                "RBAC 检查: 操作权限拒绝",
                user_id=permission.user_id,
                reason=blocked_reason,
            )
            return RBACCheckResult(
                allowed=False,
                blocked_reason=blocked_reason,
                max_rows=permission.max_rows,
            )

        current_sql = sql

        # 第二步：行级权限注入
        if permission.row_filter_expression:
            try:
                current_sql = self._row_filter.apply(
                    current_sql, permission.row_filter_expression, dialect
                )
                logger.debug(
                    "RBAC 检查: 行级权限注入完成",
                    injected=permission.row_filter_expression,
                )
            except Exception as e:
                logger.error(
                    "RBAC 检查: 行级权限注入失败",
                    error=str(e),
                    expression=permission.row_filter_expression,
                )
                return RBACCheckResult(
                    allowed=False,
                    blocked_reason=f"行级权限注入失败: {e}",
                    max_rows=permission.max_rows,
                )

        # 第三步：列级权限过滤
        removed_columns: list[str] = []
        if permission.hidden_columns:
            try:
                current_sql, removed_columns = self._column_filter.apply(
                    current_sql, permission.hidden_columns, dialect
                )
                logger.debug(
                    "RBAC 检查: 列级权限过滤完成",
                    removed=removed_columns,
                )
            except Exception as e:
                logger.error(
                    "RBAC 检查: 列级权限过滤失败",
                    error=str(e),
                    hidden_columns=permission.hidden_columns,
                )
                return RBACCheckResult(
                    allowed=False,
                    blocked_reason=f"列级权限过滤失败: {e}",
                    max_rows=permission.max_rows,
                )

        # 返回检查结果
        # 脱敏在查询结果返回时由 DataMasker.mask_result() 执行，
        # 这里仅标记隐藏列以便后续处理
        masked_columns = [col for col in permission.hidden_columns if col not in removed_columns]

        result = RBACCheckResult(
            allowed=True,
            filtered_sql=current_sql,
            masked_columns=masked_columns,
            removed_columns=removed_columns,
            injected_where=permission.row_filter_expression,
            max_rows=permission.max_rows,
        )

        logger.info(
            "RBAC 检查: 通过",
            user_id=permission.user_id,
            removed_columns=removed_columns,
            max_rows=permission.max_rows,
        )
        return result
