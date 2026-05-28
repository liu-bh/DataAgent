"""通用 FastAPI 依赖注入。

提供数据库 session 获取等公共依赖。

用法::

    from fastapi import APIRouter, Depends
    from datapilot_common.deps.auth import get_db

    router = APIRouter()

    @router.get("/items")
    async def list_items(db: AsyncSession = Depends(get_db)):
        ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import Request
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """获取 AsyncSession 依赖。

    从 request.state 获取已注入的 async_session_maker，创建 session 并在请求结束后关闭。
    各服务启动时需将 session_maker 存入 app.state.async_session_maker。

    Yields:
        AsyncSession 实例。
    """
    session_maker = request.app.state.async_session_maker
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
