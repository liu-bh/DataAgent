"""DataPilot Guardrail Service 入口。

创建 FastAPI 应用，挂载路由，提供健康检查端点。
"""

from __future__ import annotations

import os

import structlog
import uvicorn
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from datapilot_guardrail import __version__
from datapilot_guardrail.api.routes.guardrail import router as guardrail_router

logger = structlog.get_logger(__name__)

app = FastAPI(
    title="DataPilot Guardrail Service",
    version=__version__,
    description="SQL 风险检测、行数限制和查询配额管理服务",
)


# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查端点。

    Returns:
        服务状态信息。
    """
    return {"status": "ok", "service": "guardrail", "version": __version__}


# ---------------------------------------------------------------------------
# 注册路由
# ---------------------------------------------------------------------------

app.include_router(guardrail_router)

# Prometheus 指标导出
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# ---------------------------------------------------------------------------
# 启动入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("GUARDRAIL_PORT", "8005"))
    uvicorn.run(app, host="0.0.0.0", port=port)
