"""DataPilot Auth Service."""
__version__ = "0.1.0"

import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from datapilot_auth.api.routes.auth import router as auth_router
from datapilot_auth.exceptions import AppError

app = FastAPI(
    title="DataPilot Auth Service",
    version=__version__,
    description="认证服务：JWT、RBAC、用户管理",
)


# 注册路由
app.include_router(auth_router)


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
    return {"status": "ok", "service": "auth"}


if __name__ == "__main__":
    port = int(os.getenv("AUTH_PORT", "8004"))
    uvicorn.run(app, host="0.0.0.0", port=port)
