"""会话代理路由 Stub：转发至 Session Service。

TODO: 生产环境应通过 gRPC 或 HTTP 调用 session-service
"""

import uuid

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions-proxy"])


class SessionCreateStub(BaseModel):
    """创建会话请求 Stub。"""

    title: str | None = None


class SessionUpdateStub(BaseModel):
    """更新会话请求 Stub。"""

    title: str | None = None
    is_archived: bool | None = None


@router.get("")
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    authorization: str = Header(None, description="Bearer {token}"),
) -> dict:
    """会话列表 Stub。

    TODO: 转发至 session-service GET /api/v1/sessions
    """
    return {
        "data": [],
        "pagination": {"page": page, "page_size": page_size, "total": 0, "total_pages": 0},
    }


@router.post("", status_code=201)
async def create_session(
    body: SessionCreateStub,
    authorization: str = Header(None, description="Bearer {token}"),
) -> dict:
    """创建会话 Stub。

    TODO: 转发至 session-service POST /api/v1/sessions
    """
    return {
        "id": str(uuid.uuid4()),
        "title": body.title or "新会话",
        "message_count": 0,
        "is_archived": False,
    }


@router.get("/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    authorization: str = Header(None, description="Bearer {token}"),
) -> dict:
    """获取会话详情 Stub。

    TODO: 转发至 session-service GET /api/v1/sessions/{id}
    """
    return {
        "id": str(session_id),
        "title": "[Stub] 会话详情",
        "message_count": 0,
        "is_archived": False,
    }


@router.patch("/{session_id}")
async def update_session(
    session_id: uuid.UUID,
    body: SessionUpdateStub,
    authorization: str = Header(None, description="Bearer {token}"),
) -> dict:
    """更新会话 Stub。

    TODO: 转发至 session-service PATCH /api/v1/sessions/{id}
    """
    return {
        "id": str(session_id),
        **body.model_dump(exclude_unset=True),
    }


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: uuid.UUID,
    authorization: str = Header(None, description="Bearer {token}"),
) -> None:
    """删除会话 Stub。

    TODO: 转发至 session-service DELETE /api/v1/sessions/{id}
    """
    return None


@router.get("/{session_id}/messages")
async def get_messages(
    session_id: uuid.UUID,
    authorization: str = Header(None, description="Bearer {token}"),
) -> dict:
    """获取会话消息列表 Stub。

    TODO: 转发至 session-service GET /api/v1/sessions/{id}/messages
    """
    return []
