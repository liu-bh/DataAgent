"""数据库连接与会话管理。

TODO: 迁移到 datapilot-common
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from datapilot_auth.config import settings

# 延迟初始化：避免模块导入时即创建数据库连接
_engine = None
_async_session_factory = None


def _get_engine():
    """延迟获取数据库引擎，首次调用时才创建。"""
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.database_url, echo=settings.debug)
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """延迟获取会话工厂，首次调用时才创建。"""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


class Base(DeclarativeBase):
    """所有模型的声明式基类。"""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：获取异步数据库会话。"""
    async with _get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
