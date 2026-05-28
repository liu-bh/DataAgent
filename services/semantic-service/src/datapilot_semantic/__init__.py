"""DataPilot Semantic Service."""

__version__ = "0.1.0"

import os

import uvicorn
from fastapi import FastAPI

from datapilot_semantic.api.routes.data_sources import router as data_sources_router
from datapilot_semantic.api.routes.dimensions import router as dimensions_router
from datapilot_semantic.api.routes.metrics import router as metrics_router
from datapilot_semantic.api.routes.search import router as search_router
from datapilot_semantic.api.routes.semantic_models import router as semantic_models_router

app = FastAPI(title="DataPilot Semantic Service", version=__version__)

# 注册 API 路由

app.include_router(data_sources_router)
app.include_router(semantic_models_router)
app.include_router(metrics_router)
app.include_router(dimensions_router)
app.include_router(search_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "semantic"}


if __name__ == "__main__":
    port = int(os.getenv("SEMANTIC_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
