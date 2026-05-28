"""聊天路由 Stub：同步消息与 SSE 流式响应。"""

import asyncio
import json
import uuid

from fastapi import APIRouter, Header
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class ChatMessageRequest(BaseModel):
    """聊天消息请求。"""

    session_id: uuid.UUID
    content: str


@router.post("/message")
async def chat_message(
    body: ChatMessageRequest,
    authorization: str = Header(None, description="Bearer {token}"),
) -> dict:
    """发送消息（同步，返回完整结果）。

    TODO: 接入 NL2SQL 引擎和 LLM 推理
    """
    stub_response = {
        "data": {
            "message_id": str(uuid.uuid4()),
            "content": f"[Stub] 收到消息：{body.content}。Agent 服务尚未接入 LLM 引擎。",
            "sql": None,
            "sql_dialect": None,
            "sql_explanation": None,
            "chart_spec": None,
            "freshness_note": None,
            "data_cutoff": None,
            "total_rows": 0,
            "has_more": False,
        },
        "trace_id": f"stub-{uuid.uuid4().hex[:8]}",
    }
    return stub_response


@router.post("/stream")
async def chat_stream(
    body: ChatMessageRequest,
    authorization: str = Header(None, description="Bearer {token}"),
) -> EventSourceResponse:
    """发送消息（SSE 流式响应）。

    阶段式推送：status → sql → message → done。
    TODO: Sprint 12 接入 NL2SQL 引擎和 LLM 推理，替换 stub。
    """

    async def event_generator():
        message_id = str(uuid.uuid4())

        # 阶段 1: 状态 - 正在分析问题
        yield {
            "event": "status",
            "data": json.dumps(
                {"status": "thinking", "message": "正在分析问题..."}
            ),
        }
        await asyncio.sleep(0.5)

        # 阶段 2: SQL
        stub_sql = "SELECT 1 LIMIT 1"
        yield {
            "event": "sql",
            "data": json.dumps(
                {"sql": stub_sql, "dialect": "mysql"}
            ),
        }
        await asyncio.sleep(0.5)

        # 阶段 3: 消息
        yield {
            "event": "message",
            "data": json.dumps(
                {
                    "content": f"查询结果如下（Stub 模式）：收到问题「{body.content}」。Agent 服务尚未接入 LLM 引擎。",
                    "message_id": message_id,
                }
            ),
        }
        await asyncio.sleep(0.3)

        # 阶段 4: 完成
        yield {
            "event": "done",
            "data": json.dumps({"message_id": message_id}),
        }

    return EventSourceResponse(event_generator())


@router.post("/execute-sql")
async def execute_sql(
    body: dict,
    authorization: str = Header(None, description="Bearer {token}"),
) -> dict:
    """用户编辑 SQL 后重新执行。

    TODO: 接入 query-executor-service
    """
    return {
        "data": {
            "message_id": str(uuid.uuid4()),
            "content": "[Stub] SQL 执行结果占位",
            "sql": body.get("edited_sql"),
            "sql_dialect": "mysql",
            "sql_explanation": None,
            "chart_spec": None,
            "total_rows": 0,
            "has_more": False,
        },
        "trace_id": f"stub-{uuid.uuid4().hex[:8]}",
    }


# ---------------------------------------------------------------------------
# Sprint 3b Track D: 端到端查询入口
# ---------------------------------------------------------------------------


class ChatQueryRequest(BaseModel):
    """端到端查询请求。"""

    question: str
    session_id: uuid.UUID
    tenant_id: str = ""
    execute: bool = False


@router.post("/query")
async def chat_query(
    body: ChatQueryRequest,
    authorization: str = Header(None, description="Bearer {token}"),
) -> dict:
    """端到端查询入口：自然语言问题 → SQL → 解释 → 可选执行。

    内部调用 sqlgen-service 的 /api/v1/chat/execute（Phase1 stub）。
    TODO: Sprint 4 通过 httpx 对接 sqlgen-service
    """
    # Phase1 stub: 直接返回提示信息
    # 生产环境应通过 httpx 调用 sqlgen-service 的 /api/v1/chat/execute
    stub_response = {
        "data": {
            "message_id": str(uuid.uuid4()),
            "content": f"[Stub] 收到查询请求：{body.question}。Agent 端到端查询尚未接入 sqlgen-service。",
            "sql": None,
            "sql_dialect": None,
            "sql_explanation": None,
            "chart_spec": None,
            "data": None,
            "columns": [],
            "total_rows": 0,
            "has_more": False,
            "execute": body.execute,
        },
        "trace_id": f"stub-{uuid.uuid4().hex[:8]}",
    }
    return stub_response


# ---------------------------------------------------------------------------
# Sprint 8 Track D: RCA 意图路由
# ---------------------------------------------------------------------------
# 新增路由挂载在 main.py 中完成：
#   from datapilot_agent.api.routes.rca import router as rca_router
#   from datapilot_agent.api.routes.tools import router as tools_router
#   app.include_router(rca_router)
#   app.include_router(tools_router)
#
# TODO: Sprint 9 在意图识别层增加 RCA 意图路由，当检测到根因分析意图时
#   转发至 RCAOrchestrator 处理并返回分析报告。
