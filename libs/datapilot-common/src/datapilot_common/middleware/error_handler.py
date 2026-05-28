"""FastAPI 全局异常处理器。

捕获 AppError / RequestValidationError / Exception，
返回统一的 JSON 错误响应格式::

    {
        "error": {
            "code": "RESOURCE_NOT_FOUND",
            "message": "...",
            "details": {}
        },
        "trace_id": "abc123"
    }
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from datapilot_common.exceptions import AppError

if TYPE_CHECKING:
    from fastapi import FastAPI, Request


def _build_error_body(
    code: str,
    message: str,
    details: Any = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """构建统一错误响应体。"""
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }
    if trace_id:
        body["trace_id"] = trace_id
    return body


def _get_trace_id(request: Request) -> str | None:
    """从请求上下文中获取 trace_id。"""
    return getattr(request.state, "trace_id", None) or request.headers.get("X-Trace-ID")


# ---------------------------------------------------------------------------
# 异常处理函数
# ---------------------------------------------------------------------------


async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """捕获业务异常 AppError。"""
    trace_id = _get_trace_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_body(
            code=exc.error_code,
            message=exc.message,
            details=exc.details if exc.details else None,
            trace_id=trace_id,
        ),
    )


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """捕获 FastAPI 请求体验证错误。"""
    trace_id = _get_trace_id(request)
    # 将 Pydantic 错误转换为 field + message 结构
    details: list[dict[str, str]] = []
    for error in exc.errors():
        loc = error.get("loc", ())
        # 跳过 'body' / 'query' 等前缀
        field_parts = [str(p) for p in loc if p not in ("body", "query", "path", "header")]
        field = ".".join(field_parts) if field_parts else "unknown"
        details.append({"field": field, "message": error.get("msg", "校验失败")})

    return JSONResponse(
        status_code=422,
        content=_build_error_body(
            code="VALIDATION_ERROR",
            message="请求参数校验失败",
            details=details,
            trace_id=trace_id,
        ),
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底：捕获未处理的异常。"""
    trace_id = _get_trace_id(request)
    # 生产环境不暴露内部错误细节
    message = "服务内部错误" if not _is_debug(request) else str(exc)
    return JSONResponse(
        status_code=500,
        content=_build_error_body(
            code="INTERNAL_ERROR",
            message=message,
            details=None,
            trace_id=trace_id,
        ),
    )


def _is_debug(request: Request) -> bool:
    """判断当前请求是否处于 debug 模式。"""
    app = request.app
    return getattr(app.state, "debug", False)


# ---------------------------------------------------------------------------
# 注册函数
# ---------------------------------------------------------------------------


def register_error_handlers(app: FastAPI) -> None:
    """将异常处理器注册到 FastAPI 应用。

    用法::

        from fastapi import FastAPI
        from datapilot_common.middleware.error_handler import register_error_handlers

        app = FastAPI()
        register_error_handlers(app)
    """
    app.add_exception_handler(AppError, _app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
