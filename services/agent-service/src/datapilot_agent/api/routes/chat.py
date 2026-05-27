"""聊天路由 Stub：同步消息与 SSE 流式响应。"""

import uuid

from fastapi import APIRouter, Header
from pydantic import BaseModel

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
) -> dict:
    """发送消息（SSE 流式响应 Stub）。

    TODO: 实现 SSE 流式响应，使用 sse-starlette
    """
    # Stub: 返回 JSON 说明而非真实 SSE 流
    return {
        "message": "SSE 流式端点 Stub。生产环境应返回 text/event-stream。",
        "session_id": str(body.session_id),
        "content_preview": body.content[:50],
    }


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
