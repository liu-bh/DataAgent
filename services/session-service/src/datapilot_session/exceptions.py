"""自定义异常类。

TODO: 迁移到 datapilot-common
"""


class AppError(Exception):
    """应用基础异常。"""

    def __init__(self, message: str, status_code: int = 400, error_code: str | None = None) -> None:
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "INTERNAL_ERROR"
        super().__init__(self.message)


class AuthenticationError(AppError):
    """认证失败。"""

    def __init__(self, message: str = "认证失败") -> None:
        super().__init__(message, status_code=401, error_code="AUTHENTICATION_FAILED")


class TokenExpiredError(AppError):
    """Token 已过期。"""

    def __init__(self, message: str = "Token 已过期") -> None:
        super().__init__(message, status_code=401, error_code="TOKEN_EXPIRED")


class ForbiddenError(AppError):
    """权限不足。"""

    def __init__(self, message: str = "权限不足") -> None:
        super().__init__(message, status_code=403, error_code="FORBIDDEN")


class NotFoundError(AppError):
    """资源不存在。"""

    def __init__(self, resource: str = "资源") -> None:
        super().__init__(f"{resource}不存在", status_code=404, error_code="NOT_FOUND")


class ConflictError(AppError):
    """资源冲突。"""

    def __init__(self, message: str = "资源冲突") -> None:
        super().__init__(message, status_code=409, error_code="CONFLICT")


class ValidationError(AppError):
    """请求参数校验失败。"""

    def __init__(self, message: str = "参数校验失败") -> None:
        super().__init__(message, status_code=422, error_code="VALIDATION_ERROR")
