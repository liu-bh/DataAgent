"""SQLAlchemy Session 与 Message 模型。"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datapilot_session.database import Base


class Session(Base):
    """会话表。"""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="租户 ID",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="用户 ID",
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="新会话",
        comment="会话标题",
    )
    message_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="消息数",
    )
    expires_at: Mapped[datetime] = mapped_column(
        nullable=True,
        comment="过期时间",
    )
    is_archived: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="是否已归档",
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    # 关系
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="session",
        order_by="Message.created_at",
        lazy="selectin",
    )


class Message(Base):
    """消息表。"""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="会话 ID",
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="角色: user/assistant/system",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="消息内容",
    )
    sql: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="生成的 SQL（assistant 角色时）",
    )
    chart_spec: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="图表配置",
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        comment="创建时间",
    )

    # 关系
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="messages",
    )
