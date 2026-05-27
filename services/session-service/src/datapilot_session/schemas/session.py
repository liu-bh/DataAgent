"""会话相关 Pydantic Schema。"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SessionCreate(BaseModel):
    """创建会话请求。"""

    title: str | None = None
    user_id: uuid.UUID


class SessionUpdate(BaseModel):
    """更新会话请求。"""

    title: str | None = None
    is_archived: bool | None = None


class MessageResponse(BaseModel):
    """消息响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    sql: str | None = None
    chart_spec: dict | None = None
    created_at: datetime


class SessionResponse(BaseModel):
    """会话响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    message_count: int
    expires_at: datetime | None = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class SessionListResponse(BaseModel):
    """会话列表响应（含分页）。"""

    data: list[SessionResponse]
    pagination: dict
