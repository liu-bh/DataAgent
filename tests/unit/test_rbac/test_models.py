"""RBAC 数据模型单元测试。

覆盖 PermissionRule、MaskRule、RBACCheckResult 和 OperationType 的验证。
"""

from __future__ import annotations

import pytest

from datapilot_queryexec.rbac.models import (
    MaskRule,
    OperationType,
    PermissionRule,
    RBACCheckResult,
)


class TestOperationType:
    """OperationType 枚举测试。"""

    def test_values(self) -> None:
        """枚举值正确。"""
        assert OperationType.READ == "read"
        assert OperationType.EXPORT == "export"
        assert OperationType.DDL == "ddl"
        assert OperationType.WRITE == "write"

    def test_is_str_enum(self) -> None:
        """可以作为字符串使用。"""
        assert OperationType.READ in ["read", "write"]
        # StrEnum 的 str() 返回小写值
        assert str(OperationType.DDL) == "ddl"


class TestPermissionRule:
    """PermissionRule 模型测试。"""

    def test_minimal_fields(self) -> None:
        """仅必填字段。"""
        rule = PermissionRule(user_id="u1", tenant_id="t1")
        assert rule.user_id == "u1"
        assert rule.tenant_id == "t1"
        assert rule.role == "viewer"
        assert rule.allowed_operations == [OperationType.READ]
        assert rule.allowed_datasources == []
        assert rule.row_filter_expression == ""
        assert rule.hidden_columns == []
        assert rule.max_rows == 10000

    def test_full_fields(self) -> None:
        """所有字段赋值。"""
        rule = PermissionRule(
            user_id="u2",
            tenant_id="t2",
            role="admin",
            allowed_operations=[OperationType.READ, OperationType.EXPORT, OperationType.DDL],
            allowed_datasources=["ds1", "ds2"],
            row_filter_expression="department_id = 100",
            hidden_columns=["phone", "id_card"],
            max_rows=5000,
        )
        assert rule.role == "admin"
        assert len(rule.allowed_operations) == 3
        assert rule.allowed_datasources == ["ds1", "ds2"]
        assert rule.row_filter_expression == "department_id = 100"
        assert rule.hidden_columns == ["phone", "id_card"]
        assert rule.max_rows == 5000

    def test_default_operations_is_list_not_shared(self) -> None:
        """默认 allowed_operations 不被多个实例共享。"""
        r1 = PermissionRule(user_id="u1", tenant_id="t1")
        r2 = PermissionRule(user_id="u2", tenant_id="t2")
        r1.allowed_operations.append(OperationType.EXPORT)
        assert OperationType.EXPORT not in r2.allowed_operations

    def test_from_attributes(self) -> None:
        """支持 from_attributes 配置。"""
        # 验证 model_config 中包含 from_attributes=True
        assert PermissionRule.model_config.get("from_attributes") is True


class TestMaskRule:
    """MaskRule 模型测试。"""

    def test_minimal_fields(self) -> None:
        """仅必填字段。"""
        rule = MaskRule(column_name="*email*")
        assert rule.column_name == "*email*"
        assert rule.mask_type == "partial"
        assert rule.pattern == ""
        assert rule.replacement == "***"
        assert rule.examples == []

    def test_full_fields(self) -> None:
        """所有字段赋值。"""
        rule = MaskRule(
            column_name="*phone*",
            mask_type="partial",
            pattern=r"(\d{3})\d{4}(\d{4})",
            replacement=r"\1****\2",
            examples=["138****1234"],
        )
        assert rule.mask_type == "partial"
        assert rule.replacement == r"\1****\2"
        assert rule.examples == ["138****1234"]

    def test_all_mask_types(self) -> None:
        """各种脱敏类型。"""
        for mask_type in ("full", "partial", "hash", "replace"):
            rule = MaskRule(column_name="col", mask_type=mask_type)
            assert rule.mask_type == mask_type


class TestRBACCheckResult:
    """RBACCheckResult 数据类测试。"""

    def test_allowed_result(self) -> None:
        """通过的检查结果。"""
        result = RBACCheckResult(
            allowed=True,
            filtered_sql="SELECT id FROM users WHERE dept = 1",
            masked_columns=["email"],
            removed_columns=["phone"],
            injected_where="dept = 1",
            blocked_reason="",
            max_rows=10000,
        )
        assert result.allowed is True
        assert result.filtered_sql != ""
        assert result.blocked_reason == ""

    def test_blocked_result(self) -> None:
        """拒绝的检查结果。"""
        result = RBACCheckResult(
            allowed=False,
            blocked_reason="操作类型 'ddl' 不在允许范围内",
        )
        assert result.allowed is False
        assert result.filtered_sql == ""
        assert result.masked_columns == []
        assert result.blocked_reason != ""

    def test_defaults(self) -> None:
        """默认值。"""
        result = RBACCheckResult(allowed=True)
        assert result.filtered_sql == ""
        assert result.masked_columns == []
        assert result.removed_columns == []
        assert result.injected_where == ""
        assert result.blocked_reason == ""
        assert result.max_rows == 10000

    def test_not_shared_defaults(self) -> None:
        """列表默认值不被共享。"""
        r1 = RBACCheckResult(allowed=True)
        r2 = RBACCheckResult(allowed=True)
        r1.masked_columns.append("email")
        assert "email" not in r2.masked_columns
