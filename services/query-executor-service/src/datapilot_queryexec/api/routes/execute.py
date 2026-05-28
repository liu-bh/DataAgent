"""SQL 执行 API 路由。

提供同步执行、异步执行、任务状态查询和结果获取的 HTTP 接口。
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Query

from datapilot_common.exceptions import NotFoundError
from datapilot_queryexec.executor.engine import QueryEngine
from datapilot_queryexec.executor.models import ExecuteRequest, FormatType, QueryTask

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1")

# 执行引擎实例，由 main.py 在应用启动时注入
_engine: QueryEngine | None = None


def set_engine(engine: QueryEngine) -> None:
    """设置全局执行引擎实例。

    Args:
        engine: QueryEngine 实例。
    """
    global _engine
    _engine = engine


def get_engine() -> QueryEngine:
    """获取全局执行引擎实例。

    Returns:
        QueryEngine 实例。

    Raises:
        RuntimeError: 引擎未初始化时抛出。
    """
    if _engine is None:
        raise RuntimeError("QueryEngine 未初始化，请检查应用启动配置")
    return _engine


@router.post("/execute", response_model=QueryTask)
async def execute_sql(request: ExecuteRequest) -> QueryTask:
    """同步执行 SQL。

    接收 SQL 语句并同步执行，返回执行结果。

    Args:
        request: 执行请求，包含 SQL、方言、数据源等信息。

    Returns:
        包含执行结果的 QueryTask。
    """
    engine = get_engine()
    logger.info(
        "同步执行请求",
        sql=request.sql[:200],
        dialect=request.dialect,
        datasource_id=request.datasource_id,
    )
    result = await engine.execute_sync(request)
    return result


@router.post("/execute/async", response_model=QueryTask)
async def execute_sql_async(request: ExecuteRequest) -> QueryTask:
    """提交异步执行任务。

    创建后台执行任务，立即返回 task_id，客户端可通过任务状态接口轮询结果。

    Args:
        request: 执行请求。

    Returns:
        包含 task_id 的 QueryTask（状态为 PENDING）。
    """
    engine = get_engine()
    logger.info(
        "异步执行请求",
        sql=request.sql[:200],
        dialect=request.dialect,
        datasource_id=request.datasource_id,
    )
    result = await engine.execute_async(request)
    return result


@router.get("/execute/{task_id}/status", response_model=QueryTask)
async def get_task_status(task_id: str) -> QueryTask:
    """查询异步任务状态。

    Args:
        task_id: 任务唯一标识。

    Returns:
        QueryTask 实例。

    Raises:
        NotFoundError: 任务不存在时抛出。
    """
    engine = get_engine()
    task = await engine.get_result(task_id)
    if task is None:
        raise NotFoundError(resource="查询任务", resource_id=task_id)
    return task


@router.get("/execute/{task_id}/result")
async def get_task_result(
    task_id: str,
    format: FormatType = Query(default=FormatType.JSON),
) -> Any:
    """获取异步任务结果。

    支持按格式返回结果（JSON 或 CSV）。

    Args:
        task_id: 任务唯一标识。
        format: 结果格式，默认 JSON。

    Returns:
        JSON 格式返回 dict，CSV 格式返回字符串。

    Raises:
        NotFoundError: 任务不存在时抛出。
    """
    from fastapi.responses import PlainTextResponse

    engine = get_engine()
    task = await engine.get_result(task_id)
    if task is None:
        raise NotFoundError(resource="查询任务", resource_id=task_id)

    if task.status.value == "completed" and task.result is not None:
        columns = task.result.get("columns", [])
        # task.result["data"] 是按列顺序排列的列表，需要转换为字典列表
        data_rows = task.result.get("data", [])
        rows: list[dict] = []
        for row in data_rows:
            row_dict = {}
            for i, col in enumerate(columns):
                row_dict[col] = row[i] if i < len(row) else None
            rows.append(row_dict)

        if format == FormatType.CSV:
            from datapilot_queryexec.executor.formatter import ResultFormatter

            csv_content = ResultFormatter.to_csv(columns, rows)
            return PlainTextResponse(
                content=csv_content,
                media_type="text/csv; charset=utf-8",
            )

        return task.result

    # 任务未完成或执行失败，返回任务状态
    return {
        "task_id": task_id,
        "status": task.status.value,
        "error": task.error or None,
    }
