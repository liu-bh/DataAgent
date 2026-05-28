"""RBAC 检查器（编排层）单元测试。

覆盖 RBACChecker 的完整流程和多步骤组合：
- 操作权限拦截
- 行级 + 列级权限组合
- 操作权限通过后的完整流程
- 各种权限规则组合
"""

from __future__ import annotations

import pytest

from datapilot_queryexec.rbac.checker import RBACChecker
from datapilot_queryexec.rbac.models import (
    OperationType,
    PermissionRule,
    RBACCheckResult,
)


def _viewer_permission(
    user_id: str = "u1",
    tenant_id: str = "t1",
    **kwargs,
) -> PermissionRule:
    """创建 viewer 权限规则（默认只有 READ 权限）。"""
    return PermissionRule(
        user_id=user_id,
        tenant_id=tenant_id,
        role="viewer",
        allowed_operations=[OperationType.READ],
        **kwargs,
    )


def _admin_permission(
    user_id: str = "a1",
    tenant_id: str = "t1",
    **kwargs,
) -> PermissionRule:
    """创建 admin 权限规则（允许所有操作）。"""
    return PermissionRule(
        user_id=user_id,
        tenant_id=tenant_id,
        role="admin",
        allowed_operations=[
            OperationType.READ,
            OperationType.WRITE,
            OperationType.DDL,
            OperationType.EXPORT,
        ],
        **kwargs,
    )


class TestOperationBlocked:
    """操作权限拦截测试。"""

    @pytest.fixture()
    def checker(self) -> RBACChecker:
        """创建 RBAC 检查器。"""
        return RBACChecker()

    def test_select_allowed_for_viewer(self, checker: RBACChecker) -> None:
        """viewer 可以执行 SELECT。"""
        permission = _viewer_permission()
        result = checker.check("SELECT id FROM users", permission)
        assert result.allowed is True
        assert result.blocked_reason == ""

    def test_ddl_blocked_for_viewer(self, checker: RBACChecker) -> None:
        """viewer 不能执行 DDL。"""
        permission = _viewer_permission()
        result = checker.check("DROP TABLE users", permission)
        assert result.allowed is False
        assert "ddl" in result.blocked_reason.lower()

    def test_write_blocked_for_viewer(self, checker: RBACChecker) -> None:
        """viewer 不能执行写操作。"""
        permission = _viewer_permission()
        result = checker.check("DELETE FROM users", permission)
        assert result.allowed is False
        assert "write" in result.blocked_reason.lower()

    def test_ddl_allowed_for_admin(self, checker: RBACChecker) -> None:
        """admin 可以执行 DDL。"""
        permission = _admin_permission()
        result = checker.check("CREATE TABLE test (id INT)", permission)
        assert result.allowed is True


class TestRowFilterInjection:
    """行级权限注入测试。"""

    @pytest.fixture()
    def checker(self) -> RBACChecker:
        """创建 RBAC 检查器。"""
        return RBACChecker()

    def test_row_filter_injected(self, checker: RBACChecker) -> None:
        """行级过滤条件被注入到 SQL 中。"""
        permission = _viewer_permission(
            row_filter_expression="department_id = 100"
        )
        result = checker.check("SELECT id, name FROM users", permission)
        assert result.allowed is True
        assert "department_id" in result.filtered_sql or "DEPARTMENT_ID" in result.filtered_sql.upper()
        assert result.injected_where == "department_id = 100"

    def test_row_filter_appended_to_existing_where(self, checker: RBACChecker) -> None:
        """行级过滤追加到已有 WHERE。"""
        permission = _viewer_permission(
            row_filter_expression="department_id = 100"
        )
        result = checker.check(
            "SELECT id FROM users WHERE age > 18", permission
        )
        assert result.allowed is True
        # 两个条件都应存在
        upper_sql = result.filtered_sql.upper()
        assert "DEPARTMENT_ID" in upper_sql or "department_id" in result.filtered_sql
        assert "AGE" in upper_sql or "age" in result.filtered_sql

    def test_no_row_filter_when_empty(self, checker: RBACChecker) -> None:
        """没有行级过滤时不修改 SQL（除可能的列过滤）。"""
        permission = _viewer_permission(row_filter_expression="")
        result = checker.check("SELECT id FROM users", permission)
        assert result.allowed is True
        assert result.injected_where == ""


class TestColumnFilterRemoval:
    """列级权限过滤测试。"""

    @pytest.fixture()
    def checker(self) -> RBACChecker:
        """创建 RBAC 检查器。"""
        return RBACChecker()

    def test_hidden_columns_removed(self, checker: RBACChecker) -> None:
        """隐藏列从 SQL 中移除。"""
        permission = _viewer_permission(hidden_columns=["phone", "email"])
        result = checker.check("SELECT id, name, phone, email FROM users", permission)
        assert result.allowed is True
        assert "phone" in result.removed_columns
        assert "email" in result.removed_columns
        # SQL 中不应包含被移除的列
        assert "phone" not in result.filtered_sql.lower() or "PHONE" not in result.filtered_sql.upper()

    def test_no_hidden_columns(self, checker: RBACChecker) -> None:
        """没有隐藏列时不修改 SQL。"""
        permission = _viewer_permission(hidden_columns=[])
        sql = "SELECT id, name FROM users"
        result = checker.check(sql, permission)
        assert result.allowed is True
        assert result.removed_columns == []


class TestFullPipeline:
    """完整 RBAC 检查流程测试。"""

    @pytest.fixture()
    def checker(self) -> RBACChecker:
        """创建 RBAC 检查器。"""
        return RBACChecker()

    def test_row_and_column_combined(self, checker: RBACChecker) -> None:
        """行级 + 列级权限组合。"""
        permission = _viewer_permission(
            row_filter_expression="department_id = 100",
            hidden_columns=["phone"],
        )
        result = checker.check(
            "SELECT id, name, phone FROM users", permission
        )
        assert result.allowed is True
        # 行级过滤
        assert "department_id" in result.filtered_sql or "DEPARTMENT_ID" in result.filtered_sql.upper()
        assert result.injected_where == "department_id = 100"
        # 列级过滤
        assert "phone" in result.removed_columns

    def test_operation_blocked_skips_row_filter(self, checker: RBACChecker) -> None:
        """操作权限拒绝时跳过行级过滤。"""
        permission = _viewer_permission(
            row_filter_expression="department_id = 100",
        )
        result = checker.check("DROP TABLE users", permission)
        assert result.allowed is False
        assert result.filtered_sql == ""

    def test_max_rows_preserved(self, checker: RBACChecker) -> None:
        """max_rows 在结果中保留。"""
        permission = _viewer_permission(max_rows=500)
        result = checker.check("SELECT id FROM users", permission)
        assert result.allowed is True
        assert result.max_rows == 500

    def test_full_permission_rule(self, checker: RBACChecker) -> None:
        """完整权限规则的端到端测试。"""
        permission = PermissionRule(
            user_id="u1",
            tenant_id="t1",
            role="analyst",
            allowed_operations=[OperationType.READ, OperationType.EXPORT],
            allowed_datasources=["mysql_prod"],
            row_filter_expression="region = '华东'",
            hidden_columns=["phone", "id_card"],
            max_rows=1000,
        )
        sql = (
            "SELECT id, name, phone, id_card, amount "
            "FROM orders "
            "WHERE amount > 100"
        )
        result = checker.check(sql, permission)
        assert result.allowed is True
        # 行级过滤注入
        assert "region" in result.filtered_sql or "REGION" in result.filtered_sql.upper()
        # 列级过滤移除
        assert set(result.removed_columns) == {"phone", "id_card"}
        # max_rows
        assert result.max_rows == 1000


class TestCustomComponents:
    """自定义组件注入测试。"""

    def test_custom_checker_components(self) -> None:
        """可以注入自定义组件。"""
        from datapilot_queryexec.rbac.row_filter import RowFilter
        from datapilot_queryexec.rbac.column_filter import ColumnFilter
        from datapilot_queryexec.rbac.operation_guard import OperationGuard
        from datapilot_queryexec.rbac.masking import DataMasker

        checker = RBACChecker(
            row_filter=RowFilter(),
            column_filter=ColumnFilter(),
            operation_guard=OperationGuard(),
            data_masker=DataMasker(),
        )
        permission = _viewer_permission()
        result = checker.check("SELECT id FROM users", permission)
        assert result.allowed is True


class TestRBACCheckResultStructure:
    """RBACCheckResult 结构验证测试。"""

    @pytest.fixture()
    def checker(self) -> RBACChecker:
        """创建 RBAC 检查器。"""
        return RBACChecker()

    def test_allowed_result_fields(self, checker: RBACChecker) -> None:
        """通过结果的字段完整性。"""
        permission = _viewer_permission()
        result = checker.check("SELECT id FROM users", permission)
        assert isinstance(result, RBACCheckResult)
        assert result.allowed is True
        assert isinstance(result.filtered_sql, str)
        assert isinstance(result.masked_columns, list)
        assert isinstance(result.removed_columns, list)
        assert isinstance(result.injected_where, str)
        assert isinstance(result.blocked_reason, str)
        assert isinstance(result.max_rows, int)

    def test_blocked_result_fields(self, checker: RBACChecker) -> None:
        """拒绝结果的字段完整性。"""
        permission = _viewer_permission()
        result = checker.check("DROP TABLE users", permission)
        assert isinstance(result, RBACCheckResult)
        assert result.allowed is False
        assert result.filtered_sql == ""
        assert result.blocked_reason != ""
