"""SQL Generator API 模块。"""

from .routes.sqlgen import router as sqlgen_router

__all__ = ["sqlgen_router"]
