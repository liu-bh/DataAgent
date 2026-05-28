"""会话 CRUD 路由。"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from datapilot_session.config import settings
from datapilot_session.database import get_db
from datapilot_session.exceptions import (
    AuthenticationError,
    NotFoundError,
)
from datapilot_session.models.session import Message, Session
from datapilot_session.schemas.session import (
    MessageResponse,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


async def get_current_user_id(
    authorization: str = Header(..., description="Bearer {token}"),
) -> uuid.UUID:
    """从 Authorization 头解析用户 ID（简化版，仅提取 sub）。

    TODO: 生产环境应通过 datapilot-common 统一解析 JWT
    """
    from jose import JWTError, jwt

    # 临时 JWT 配置
    jwt_secret = _get_jwt_secret()

    if not authorization.startswith("Bearer "):
        raise AuthenticationError("缺少 Bearer Token")

    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        return uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise AuthenticationError("无效的 Token") from exc


def _get_jwt_secret() -> str:
    """获取 JWT Secret（从环境变量或默认值）。

    TODO: 通过 datapilot-common config 统一管理
    """
    import os

    return os.getenv(
        "JWT_SECRET_KEY",
        "dev-secret-key-change-in-production-min-32-chars!",
    )


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SessionListResponse:
    """获取会话列表（分页）。"""
    # 查询总数
    count_stmt = (
        select(func.count())
        .select_from(Session)
        .where(
            Session.user_id == user_id,
            Session.is_archived.is_(False),
        )
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    # 查询分页数据
    offset = (page - 1) * page_size
    stmt = (
        select(Session)
        .where(
            Session.user_id == user_id,
            Session.is_archived.is_(False),
        )
        .order_by(Session.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size

    return SessionListResponse(
        data=[SessionResponse.model_validate(s) for s in sessions],
        pagination={
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
    )


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SessionResponse:
    """创建新会话。"""
    # TODO: 从 JWT 提取 tenant_id，当前使用默认值
    session = Session(
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),  # TODO: 从 JWT 获取
        user_id=user_id,
        title=body.title or "新会话",
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.session_expire_minutes),
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    return SessionResponse.model_validate(session)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SessionResponse:
    """获取会话详情。"""
    stmt = select(Session).where(
        Session.id == session_id,
        Session.user_id == user_id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        raise NotFoundError("会话")

    return SessionResponse.model_validate(session)


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: uuid.UUID,
    body: SessionUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SessionResponse:
    """更新会话（标题/归档状态）。"""
    stmt = select(Session).where(
        Session.id == session_id,
        Session.user_id == user_id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        raise NotFoundError("会话")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(session, key, value)

    await db.flush()
    await db.refresh(session)

    return SessionResponse.model_validate(session)


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    """删除会话。"""
    stmt = select(Session).where(
        Session.id == session_id,
        Session.user_id == user_id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        raise NotFoundError("会话")

    await db.delete(session)


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[MessageResponse]:
    """获取会话消息列表。"""
    # 先验证会话存在且属于当前用户
    stmt = select(Session).where(
        Session.id == session_id,
        Session.user_id == user_id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        raise NotFoundError("会话")

    # 查询消息
    msg_stmt = select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    msg_result = await db.execute(msg_stmt)
    messages = msg_result.scalars().all()

    return [MessageResponse.model_validate(m) for m in messages]
