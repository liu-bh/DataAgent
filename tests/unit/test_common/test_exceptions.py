"""datapilot_common.exceptions 单元测试。"""

from __future__ import annotations

import pytest

from datapilot_common.exceptions import (
    AppError,
    AuthError,
    ForbiddenError,
    LicenseError,
    NotFoundError,
    QuotaError,
    ValidationError,
)


class TestAppError:
    """AppError 基类测试。"""

    def test_default_values(self) -> None:
        err = AppError()
        assert err.error_code == "INTERNAL_ERROR"
        assert err.message == "服务内部错误"
        assert err.status_code == 500
        assert err.details == {}

    def test_custom_values(self) -> None:
        err = AppError(
            error_code="CUSTOM_ERROR",
            message="自定义错误",
            status_code=400,
            details={"field": "name"},
        )
        assert err.error_code == "CUSTOM_ERROR"
        assert err.message == "自定义错误"
        assert err.status_code == 400
        assert err.details == {"field": "name"}

    def test_str_representation(self) -> None:
        err = AppError(message="发生错误")
        assert str(err) == "发生错误"

    def test_details_defaults_to_empty_dict(self) -> None:
        err = AppError(details=None)
        assert err.details == {}


class TestNotFoundError:
    """NotFoundError 测试。"""

    def test_without_id(self) -> None:
        err = NotFoundError(resource="指标")
        assert err.error_code == "RESOURCE_NOT_FOUND"
        assert err.message == "指标不存在"
        assert err.status_code == 404

    def test_with_id(self) -> None:
        err = NotFoundError(resource="指标", resource_id="abc-123")
        assert err.message == "指标 abc-123 不存在"

    def test_with_details(self) -> None:
        err = NotFoundError(resource="数据源", resource_id="ds-1", details={"hint": "检查ID"})
        assert err.details == {"hint": "检查ID"}

    def test_default_resource(self) -> None:
        err = NotFoundError()
        assert err.message == "资源不存在"


class TestAuthError:
    """AuthError 测试。"""

    def test_default(self) -> None:
        err = AuthError()
        assert err.error_code == "UNAUTHORIZED"
        assert err.message == "未认证"
        assert err.status_code == 401

    def test_custom_code(self) -> None:
        err = AuthError(message="Token已过期", error_code="AUTH_TOKEN_EXPIRED")
        assert err.error_code == "AUTH_TOKEN_EXPIRED"
        assert err.message == "Token已过期"
        assert err.status_code == 401


class TestForbiddenError:
    """ForbiddenError 测试。"""

    def test_default(self) -> None:
        err = ForbiddenError()
        assert err.error_code == "PERMISSION_DENIED"
        assert err.message == "权限不足"
        assert err.status_code == 403

    def test_custom_message(self) -> None:
        err = ForbiddenError(message="无权访问该资源")
        assert err.message == "无权访问该资源"


class TestLicenseError:
    """LicenseError 测试。"""

    def test_default(self) -> None:
        err = LicenseError()
        assert err.error_code == "LICENSE_INVALID"
        assert err.message == "产品授权无效"
        assert err.status_code == 403

    def test_custom_code_with_prefix(self) -> None:
        err = LicenseError(error_code="LICENSE_EXPIRED", message="授权已过期")
        assert err.error_code == "LICENSE_EXPIRED"
        assert err.message == "授权已过期"

    def test_auto_add_prefix(self) -> None:
        """error_code 不以 LICENSE_ 开头时自动添加。"""
        err = LicenseError(error_code="IP_DENIED", message="IP不在白名单")
        assert err.error_code == "LICENSE_IP_DENIED"

    def test_is_forbidden_error(self) -> None:
        """LicenseError 继承自 ForbiddenError。"""
        err = LicenseError()
        assert isinstance(err, ForbiddenError)
        assert isinstance(err, AppError)

    def test_with_details(self) -> None:
        err = LicenseError(
            error_code="LICENSE_IP_DENIED",
            message="请求IP不在授权白名单内",
            details={"client_ip": "10.0.0.1", "allowed": ["192.168.1.0/24"]},
        )
        assert err.details == {"client_ip": "10.0.0.1", "allowed": ["192.168.1.0/24"]}


class TestQuotaError:
    """QuotaError 测试。"""

    def test_default(self) -> None:
        err = QuotaError()
        assert err.error_code == "RATE_LIMITED"
        assert err.message == "请求频率超限"
        assert err.status_code == 429

    def test_quota_exceeded(self) -> None:
        err = QuotaError(message="用户配额已用尽", error_code="QUOTA_EXCEEDED")
        assert err.error_code == "QUOTA_EXCEEDED"
        assert err.message == "用户配额已用尽"
        assert err.status_code == 429


class TestValidationError:
    """ValidationError 测试。"""

    def test_default(self) -> None:
        err = ValidationError()
        assert err.error_code == "VALIDATION_ERROR"
        assert err.message == "请求参数校验失败"
        assert err.status_code == 400

    def test_with_field_details(self) -> None:
        details = [{"field": "name", "message": "不能为空"}]
        err = ValidationError(message="参数错误", details=details)
        assert err.details == details

    def test_with_dict_details(self) -> None:
        details = {"field": "email", "message": "格式不正确"}
        err = ValidationError(details=details)
        assert err.details == details

    def test_details_defaults_to_empty_dict(self) -> None:
        err = ValidationError(details=None)
        assert err.details == {}
