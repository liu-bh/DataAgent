"""DataPilot Agent Service."""
__version__ = "0.1.0"

import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from datapilot_agent.api.routes.chat import router as chat_router
from datapilot_agent.api.routes.dag import router as dag_router
from datapilot_agent.api.routes.rca import router as rca_router
from datapilot_agent.api.routes.sessions import router as sessions_proxy_router
from datapilot_agent.api.routes.tools import router as tools_router

app = FastAPI(
    title="DataPilot Agent Service",
    version=__version__,
    description="Agent 服务：聊天对话、SSE 流式响应、意图路由",
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: 从配置读取允许的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat_router)
app.include_router(sessions_proxy_router)
app.include_router(dag_router)
app.include_router(rca_router)
app.include_router(tools_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "agent"}


if __name__ == "__main__":
    port = int(os.getenv("AGENT_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
