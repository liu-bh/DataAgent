"""DataPilot 自定义异常体系。

所有业务异常继承 AppError，由 FastAPI 全局异常处理器统一捕获返回。
错误码格式: {DOMAIN}_{ERROR_TYPE}，大写蛇形命名。
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """业务异常基类。

    Attributes:
        error_code: 错误码，格式 {DOMAIN}_{ERROR_TYPE}。
        message: 人类可读的错误描述。
        status_code: HTTP 状态码。
        details: 附加错误详情。
    """

    def __init__(
        self,
        error_code: str = "INTERNAL_ERROR",
        message: str = "服务内部错误",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppError):
    """资源不存在 (404)。"""

    def __init__(
        self,
        resource: str = "资源",
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        message = f"{resource}不存在" if resource_id is None else f"{resource} {resource_id} 不存在"
        super().__init__(
            error_code="RESOURCE_NOT_FOUND",
            message=message,
            status_code=404,
            details=details,
        )


class AuthError(AppError):
    """认证失败 (401)。"""

    def __init__(
        self,
        message: str = "未认证",
        error_code: str = "UNAUTHORIZED",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            error_code=error_code,
            message=message,
            status_code=401,
            details=details,
        )


class ForbiddenError(AppError):
    """权限不足 (403)。"""

    def __init__(
        self,
        message: str = "权限不足",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            error_code="PERMISSION_DENIED",
            message=message,
            status_code=403,
            details=details,
        )


class LicenseError(ForbiddenError):
    """产品授权异常 (403)，error_code 以 LICENSE_ 开头。"""

    def __init__(
        self,
        error_code: str = "LICENSE_INVALID",
        message: str = "产品授权无效",
        details: dict[str, Any] | None = None,
    ) -> None:
        if not error_code.startswith("LICENSE_"):
            error_code = f"LICENSE_{error_code}"
        super().__init__(message=message, details=details)
        # 覆盖父类 error_code
        self.error_code = error_code


class QuotaError(AppError):
    """配额超限 (429)。"""

    def __init__(
        self,
        message: str = "请求频率超限",
        error_code: str = "RATE_LIMITED",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            error_code=error_code,
            message=message,
            status_code=429,
            details=details,
        )


class ValidationError(AppError):
    """业务参数校验失败 (400)，区别于 Pydantic RequestValidationError。"""

    def __init__(
        self,
        message: str = "请求参数校验失败",
        details: dict[str, Any] | list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(
            error_code="VALIDATION_ERROR",
            message=message,
            status_code=400,
            details=details or {},
        )
