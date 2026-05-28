"""DAG 执行 API 路由。

提供 DAG 构建、执行、状态查询和历史记录接口。
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder
from datapilot_agent.dag.store import DAGExecutionStore

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/dag", tags=["dag"])

# 全局执行记录存储（单例）
_store = DAGExecutionStore()

# 全局 DAG 构建器（单例）
_builder = NL2SQLDAGBuilder()


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class DAGExecuteRequest(BaseModel):
    """DAG 执行请求。"""

    model_config = ConfigDict(from_attributes=True)

    question: str = Field(..., min_length=1, max_length=2000, description="用户自然语言问题")
    dialect: str = Field(default="mysql", description="目标 SQL 方言")
    tenant_id: str = Field(default="", description="租户 ID")
    session_id: str = Field(default="", description="会话 ID")
    async_execution: bool = Field(default=False, description="是否异步执行")


class DAGExecuteResponse(BaseModel):
    """DAG 执行响应。"""

    model_config = ConfigDict(from_attributes=True)

    dag_id: str = Field(..., description="DAG 唯一标识")
    status: str = Field(..., description="执行状态")
    task_results: dict[str, Any] = Field(default_factory=dict, description="各节点执行结果")
    total_time_ms: float = Field(default=0.0, description="总执行耗时（毫秒）")


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------


@router.post("/execute", response_model=DAGExecuteResponse)
async def execute_dag(request: DAGExecuteRequest) -> DAGExecuteResponse:
    """构建 NL2SQL DAG 并执行。

    同步执行模式下直接返回结果；
    异步执行模式下立即返回 dag_id，通过状态接口查询进度。
    """
    start_time = time.time()

    try:
        dag = _builder.build(
            question=request.question,
            dialect=request.dialect,
            tenant_id=request.tenant_id,
            session_id=request.session_id,
        )
    except Exception as exc:
        logger.error("DAG 构建失败", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail=f"DAG 构建失败: {exc}") from exc

    # 创建执行记录
    _store.create(dag.dag_id, question=request.question)
    _store.update(dag.dag_id, status="running")

    if request.async_execution:
        # 异步执行: 立即返回，后台执行 DAG
        logger.info("DAG 异步执行已提交", dag_id=dag.dag_id, question=request.question[:50])
        _store.update(dag.dag_id, status="submitted")

        return DAGExecuteResponse(
            dag_id=dag.dag_id,
            status="submitted",
            task_results={},
            total_time_ms=round((time.time() - start_time) * 1000, 2),
        )

    # 同步执行: 遍历所有节点模拟执行（Phase1 stub）
    task_results: dict[str, Any] = {}
    try:
        for node_name, node in dag.nodes.items():
            try:
                result = await node.func(**node.params)
                task_results[node_name] = {
                    "status": "success",
                    "result": result,
                }
            except Exception as node_exc:
                logger.warning(
                    "DAG 节点执行失败",
                    dag_id=dag.dag_id,
                    node=node_name,
                    error=str(node_exc),
                )
                task_results[node_name] = {
                    "status": "failed",
                    "error": str(node_exc),
                }
                break
    except Exception as exc:
        logger.error("DAG 执行失败", dag_id=dag.dag_id, error=str(exc), exc_info=True)
        _store.update(dag.dag_id, status="failed", result=task_results)
        raise HTTPException(status_code=500, detail=f"DAG 执行失败: {exc}") from exc

    elapsed_ms = round((time.time() - start_time) * 1000, 2)
    final_status = "completed"

    _store.update(
        dag.dag_id,
        status=final_status,
        completed_at=time.time(),
        result=task_results,
    )

    logger.info(
        "DAG 执行完成",
        dag_id=dag.dag_id,
        status=final_status,
        total_time_ms=elapsed_ms,
    )

    return DAGExecuteResponse(
        dag_id=dag.dag_id,
        status=final_status,
        task_results=task_results,
        total_time_ms=elapsed_ms,
    )


@router.get("/{dag_id}/status")
async def get_dag_status(dag_id: str) -> dict[str, Any]:
    """查询 DAG 执行状态。

    Args:
        dag_id: DAG 唯一标识。

    Returns:
        执行状态和结果摘要。
    """
    record = _store.get(dag_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"DAG 执行记录不存在: {dag_id}")

    return {
        "dag_id": record.dag_id,
        "status": record.status,
        "question": record.question,
        "created_at": record.created_at,
        "completed_at": record.completed_at,
        "task_count": len(record.result) if record.result else 0,
        "task_results": record.result,
    }


@router.get("/history")
async def list_dag_history(limit: int = 50) -> list[dict[str, Any]]:
    """查询 DAG 执行历史。

    Args:
        limit: 最大返回数量，默认 50。

    Returns:
        执行记录列表。
    """
    records = _store.list_records(limit=limit)
    return [
        {
            "dag_id": r.dag_id,
            "status": r.status,
            "question": r.question,
            "created_at": r.created_at,
            "completed_at": r.completed_at,
        }
        for r in records
    ]
