"""数据库工具模块。

提供 async engine / session 工厂，以及声明式基类。

用法::

    from datapilot_common.database import (
        create_async_engine,
        async_session_maker,
        Base,
        TenantBase,
    )

    engine = create_async_engine("postgresql+asyncpg://...")
    AsyncSessionLocal = async_session_maker(engine)

    class MyModel(TenantBase, Base):
        __tablename__ = "my_models"
        name: Mapped[str] = mapped_column(String(100))
"""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003 — SQLAlchemy Mapped[datetime] 需要运行时可用
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine as sa_create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ---------------------------------------------------------------------------
# Base 声明式基类
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """DataPilot 声明式基类，所有 SQLAlchemy 模型必须继承。

    公共字段: id (UUID PK), created_at, updated_at。
    """

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# TenantBase 多租户 mixin
# ---------------------------------------------------------------------------


class TenantBase:
    """多租户 mixin，所有业务模型必须混入。

    自动注入 tenant_id 字段，Phase1 hardcode 为默认租户。

    用法::

        class Metric(TenantBase, Base):
            __tablename__ = "metrics"
            ...
    """

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        default=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    )


# ---------------------------------------------------------------------------
# Engine / Session 工厂
# ---------------------------------------------------------------------------


def create_async_engine(
    database_url: str,
    *,
    echo: bool = False,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_pre_ping: bool = True,
    **kwargs: Any,
) -> Any:
    """创建异步 SQLAlchemy engine。

    Args:
        database_url: 数据库连接串，如 postgresql+asyncpg://user:pass@host/db。
        echo: 是否输出 SQL 语句（调试用）。
        pool_size: 连接池大小。
        max_overflow: 连接池最大溢出数。
        pool_pre_ping: 连接前是否发送测试查询。
        **kwargs: 其他传给 create_async_engine 的参数。

    Returns:
        AsyncEngine 实例。
    """
    return sa_create_async_engine(
        database_url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=pool_pre_ping,
        **kwargs,
    )


def async_session_maker(
    engine: Any, *, expire_on_commit: bool = False
) -> async_sessionmaker[AsyncSession]:
    """创建 async_sessionmaker 工厂。

    Args:
        engine: SQLAlchemy AsyncEngine 实例。
        expire_on_commit: 提交后是否过期属性访问。默认 False 以便在 async 场景下
            提交后仍可访问已提交对象的属性。

    Returns:
        async_sessionmaker 实例。
    """
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=expire_on_commit,
    )
