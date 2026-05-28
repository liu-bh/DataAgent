"""API 公共依赖注入。

提供统一的数据库会话获取，所有路由文件共享使用。
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from datapilot_common.database import async_session_maker, create_async_engine

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _get_engine():
    """延迟创建 engine（避免模块加载时就连接数据库）。"""
    database_url = os.getenv(
        "SEMANTIC_DATABASE_URL",
        "postgresql+asyncpg://datapilot:datapilot@localhost:5432/datapilot",
    )
    return create_async_engine(database_url, pool_size=5, max_overflow=10)


def _get_session_factory():
    """延迟创建 session factory。"""
    return async_session_maker(_get_engine())


async def get_db() -> AsyncSession:
    """FastAPI 依赖：获取异步数据库会话。"""
    session_factory = _get_session_factory()
    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
