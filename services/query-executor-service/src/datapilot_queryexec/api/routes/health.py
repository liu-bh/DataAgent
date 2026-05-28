"""健康检查 API。

提供数据源健康状态的查询和手动触发检查接口。
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, HTTPException

if TYPE_CHECKING:
    from datapilot_queryexec.monitor.health import DataSourceMonitor

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1")

# 全局监控器实例，由应用启动时注入
_monitor: DataSourceMonitor | None = None


def set_monitor(monitor: DataSourceMonitor) -> None:
    """注入监控器实例。

    Args:
        monitor: DataSourceMonitor 实例。
    """
    global _monitor
    _monitor = monitor


def get_monitor() -> DataSourceMonitor:  # type: ignore[valid-type]
    """获取当前监控器实例。

    Returns:
        DataSourceMonitor 实例。

    Raises:
        RuntimeError: 监控器未初始化。
    """
    if _monitor is None:
        raise RuntimeError("DataSourceMonitor 未初始化，请先调用 set_monitor()")
    return _monitor


@router.get("/datasources/health")
async def list_datasource_health() -> list[dict]:
    """获取所有数据源健康状态。"""
    monitor = get_monitor()
    statuses = monitor.get_all_statuses()
    return [asdict(s) for s in statuses]


@router.post("/datasources/{datasource_id}/check")
async def check_datasource(datasource_id: str) -> dict:
    """手动触发单个数据源健康检查。

    Args:
        datasource_id: 数据源唯一标识。

    Returns:
        健康检查后的数据源状态。

    Raises:
        HTTPException: 数据源未注册时返回 404。
    """
    monitor = get_monitor()

    if monitor.get_status(datasource_id) is None:
        raise HTTPException(
            status_code=404,
            detail=f"数据源 {datasource_id} 未注册",
        )

    status = await monitor.check_one(datasource_id)
    return asdict(status)
