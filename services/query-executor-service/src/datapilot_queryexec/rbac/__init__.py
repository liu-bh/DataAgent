"""RBAC 权限与数据脱敏模块。

提供基于 sqlglot AST 的行级/列级权限控制、操作级权限守卫和查询结果脱敏能力。

主要组件：
- PermissionRule / MaskRule: 权限和脱敏规则数据模型
- RowFilter: 行级权限（AST WHERE 注入）
- ColumnFilter: 列级权限（AST 移除 SELECT 列）
- DataMasker: 数据脱敏器
- OperationGuard: 操作级权限守卫
- RBACChecker: RBAC 检查器（编排层）
"""

from datapilot_queryexec.rbac.checker import RBACChecker
from datapilot_queryexec.rbac.column_filter import ColumnFilter
from datapilot_queryexec.rbac.masking import DataMasker
from datapilot_queryexec.rbac.models import MaskRule, OperationType, PermissionRule, RBACCheckResult
from datapilot_queryexec.rbac.operation_guard import OperationGuard
from datapilot_queryexec.rbac.row_filter import RowFilter

__all__ = [
    "MaskRule",
    "OperationType",
    "PermissionRule",
    "RBACCheckResult",
    "RBACChecker",
    "RowFilter",
    "ColumnFilter",
    "DataMasker",
    "OperationGuard",
]
