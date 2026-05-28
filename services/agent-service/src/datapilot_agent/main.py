"""DataPilot Agent Service — 应用入口。

定义 FastAPI 应用实例、CORS 中间件和路由挂载。
"""

from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from datapilot_agent.api.routes.chart import router as chart_router
from datapilot_agent.api.routes.chat import router as chat_router
from datapilot_agent.api.routes.dag import router as dag_router
from datapilot_agent.api.routes.dashboard import router as dashboard_router
from datapilot_agent.api.routes.rca import router as rca_router
from datapilot_agent.api.routes.sessions import router as sessions_proxy_router
from datapilot_agent.api.routes.tools import router as tools_router

__version__ = "0.1.0"


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。"""
    application = FastAPI(
        title="DataPilot Agent Service",
        version=__version__,
        description="Agent 服务：聊天对话、SSE 流式响应、意图路由",
    )

    # CORS 中间件
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: 从配置读取允许的域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    application.include_router(chat_router)
    application.include_router(sessions_proxy_router)
    application.include_router(dag_router)
    application.include_router(rca_router)
    application.include_router(tools_router)
    application.include_router(chart_router)
    application.include_router(dashboard_router)

    @application.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": "agent"}

    # Prometheus 指标导出
    Instrumentator().instrument(application).expose(application, endpoint="/metrics")

    return application


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("AGENT_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
