"""API 模块：执行路由、健康检查、配置管理。"""

from datapilot_queryexec.api.routes.config import router as config_router
from datapilot_queryexec.api.routes.execute import router as execute_router
from datapilot_queryexec.api.routes.health import router as health_router

__all__ = ["config_router", "execute_router", "health_router"]
