"""DataPilot 通用库。

导出公共接口供各微服务使用。
"""

from datapilot_common.config import BaseAppSettings
from datapilot_common.database import (
    Base,
    TenantBase,
    async_session_maker,
    create_async_engine,
)
from datapilot_common.exceptions import (
    AppError,
    AuthError,
    ForbiddenError,
    LicenseError,
    NotFoundError,
    QuotaError,
    ValidationError,
)
from datapilot_common.logging import get_logger, setup_logging
from datapilot_common.metrics import REQUEST_COUNT, REQUEST_LATENCY, setup_metrics
from datapilot_common.middleware.error_handler import register_error_handlers

__all__ = [
    # 配置
    "BaseAppSettings",
    # 异常
    "AppError",
    "AuthError",
    "ForbiddenError",
    "LicenseError",
    "NotFoundError",
    "QuotaError",
    "ValidationError",
    # 日志
    "setup_logging",
    "get_logger",
    # 数据库
    "Base",
    "TenantBase",
    "create_async_engine",
    "async_session_maker",
    # 中间件
    "register_error_handlers",
    # 指标
    "REQUEST_COUNT",
    "REQUEST_LATENCY",
    "setup_metrics",
]
