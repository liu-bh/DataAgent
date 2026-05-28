"""DataPilot Session Service."""

__version__ = "0.1.0"

import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from datapilot_session.api.routes.sessions import router as sessions_router
from datapilot_session.exceptions import AppError

app = FastAPI(
    title="DataPilot Session Service",
    version=__version__,
    description="会话管理服务：会话 CRUD、消息历史",
)


# 注册路由
app.include_router(sessions_router)


# 全局异常处理
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """统一捕获 AppError，返回标准错误格式。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
            },
        },
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "session"}


# Prometheus 指标导出
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


if __name__ == "__main__":
    port = int(os.getenv("SESSION_PORT", "8006"))
    uvicorn.run(app, host="0.0.0.0", port=port)
