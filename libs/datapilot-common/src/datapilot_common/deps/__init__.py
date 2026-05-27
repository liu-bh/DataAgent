"""FastAPI 依赖注入模块。"""

from datapilot_common.deps.auth import get_db

__all__ = ["get_db"]
