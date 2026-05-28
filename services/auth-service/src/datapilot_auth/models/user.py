"""SQLAlchemy User 模型。"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from datapilot_auth.database import Base  # type: ignore[attr-defined]


class UserRole(StrEnum):
    """用户角色枚举。"""

    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class User(Base):
    """用户表。"""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="租户 ID",
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="用户邮箱",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt 哈希密码",
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="显示名称",
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=UserRole.VIEWER.value,
        comment="角色: admin/analyst/viewer",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        comment="是否激活",
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
