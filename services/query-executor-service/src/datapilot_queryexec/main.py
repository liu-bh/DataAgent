"""DataPilot Query Executor Service — 应用入口。

定义 FastAPI 应用实例、生命周期管理和路由挂载。
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from datapilot_queryexec.api import config_router, execute_router, health_router
from datapilot_queryexec.executor.engine import QueryEngine
from datapilot_queryexec.executor.task_manager import AsyncTaskManager

__version__ = "0.1.0"

# 全局执行引擎实例
_engine: QueryEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。

    启动时初始化 QueryEngine，关闭时清理资源。
    """
    global _engine

    # 启动：初始化任务管理器和执行引擎
    task_manager = AsyncTaskManager()
    _engine = QueryEngine(task_manager=task_manager)

    # 注入引擎到路由模块
    from datapilot_queryexec.api.routes.execute import set_engine

    set_engine(_engine)

    yield

    # 关闭：清理已完成的任务
    cleaned = await task_manager.cleanup_completed(max_age_seconds=0)
    if cleaned:
        print(f"清理了 {cleaned} 个过期任务")

    _engine = None


app = FastAPI(
    title="DataPilot Query Executor Service",
    version=__version__,
    lifespan=lifespan,
)

# 挂载路由
app.include_router(execute_router)
app.include_router(health_router)
app.include_router(config_router)


@app.get("/health")
async def health() -> dict:
    """健康检查接口。"""
    return {"status": "ok", "service": "queryexec"}


if __name__ == "__main__":
    port = int(os.getenv("QUERYEXEC_PORT", "8003"))
    uvicorn.run(app, host="0.0.0.0", port=port)
