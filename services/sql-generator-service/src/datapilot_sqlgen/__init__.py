"""DataPilot SQL Generator Service.

NL2SQL 核心：自然语言转 SQL 的完整流程编排。
"""

__version__ = "0.1.0"

import os

import uvicorn
from fastapi import FastAPI

from .api.routes.sqlgen import router as sqlgen_router
from .generator import NL2SQLPipeline

__all__ = ["app", "NL2SQLPipeline"]

app = FastAPI(title="DataPilot SQL Generator Service", version=__version__)

# 注册路由
app.include_router(sqlgen_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查端点。"""
    return {"status": "ok", "service": "sqlgen"}


if __name__ == "__main__":
    port = int(os.getenv("SQLGEN_PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
