"""Dashboard 管理 API。

提供 Dashboard 的创建、查询、更新、删除等 CRUD 操作。
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from datapilot_agent.dashboard.store import DashboardStore

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

# 全局 Dashboard 存储实例
_store = DashboardStore()


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class CreateDashboardRequest(BaseModel):
    """创建 Dashboard 请求。"""

    model_config = ConfigDict(from_attributes=True)

    title: str = Field(..., min_length=1, max_length=200, description="Dashboard 标题")
    description: str = Field(default="", max_length=2000, description="Dashboard 描述")
    chart_specs: list[dict[str, Any]] = Field(
        default_factory=list,
        description="图表规格列表，每项包含 title, chart_type, chart_config, data_source",
    )
    columns: int = Field(default=2, ge=1, le=6, description="面板列数")


class DashboardPanelResponse(BaseModel):
    """Dashboard 面板响应。"""

    panel_id: str = Field(..., description="面板 ID")
    title: str = Field(default="", description="面板标题")
    chart_type: str = Field(default="", description="图表类型")
    chart_config: dict[str, Any] = Field(default_factory=dict, description="图表配置")
    data_source: dict[str, Any] = Field(default_factory=dict, description="数据源配置")
    row: int = Field(default=0, description="行位置")
    col: int = Field(default=0, description="列位置")


class DashboardResponse(BaseModel):
    """Dashboard 响应。"""

    model_config = ConfigDict(from_attributes=True)

    dashboard_id: str = Field(..., description="Dashboard ID")
    title: str = Field(..., description="Dashboard 标题")
    description: str = Field(default="", description="Dashboard 描述")
    panels: list[dict[str, Any]] = Field(default_factory=list, description="面板列表")
    filters: list[dict[str, Any]] = Field(default_factory=list, description="过滤器列表")
    columns: int = Field(default=2, description="面板列数")
    created_at: str = Field(default="", description="创建时间")


class DashboardListResponse(BaseModel):
    """Dashboard 列表响应。"""

    dashboards: list[DashboardResponse] = Field(default_factory=list, description="Dashboard 列表")
    total: int = Field(default=0, description="总数")


class UpdateDashboardRequest(BaseModel):
    """更新 Dashboard 请求。"""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = Field(default=None, min_length=1, max_length=200, description="新标题")
    description: str | None = Field(default=None, max_length=2000, description="新描述")
    add_panels: list[dict[str, Any]] | None = Field(
        default=None,
        description="新增面板列表",
    )
    remove_panel_ids: list[str] | None = Field(
        default=None,
        description="要移除的面板 ID 列表",
    )


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _layout_to_response(layout: Any, dashboard_id: str) -> DashboardResponse:
    """将 DashboardLayout 转换为 API 响应。"""
    return DashboardResponse(
        dashboard_id=dashboard_id,
        title=getattr(layout, "title", ""),
        description=getattr(layout, "description", ""),
        panels=getattr(layout, "panels", []) or [],
        filters=getattr(layout, "filters", []) or [],
        columns=getattr(layout, "columns", 2) or 2,
        created_at=_store.get_created_at(dashboard_id) or "",
    )


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------


@router.post("/create", response_model=DashboardResponse)
async def create_dashboard(request: CreateDashboardRequest) -> DashboardResponse:
    """创建 Dashboard。

    Args:
        request: 创建请求。

    Returns:
        创建的 Dashboard 信息。
    """
    logger.info("创建 Dashboard", title=request.title)

    # 构建 layout 字典
    layout_dict = {
        "title": request.title,
        "description": request.description,
        "chart_specs": request.chart_specs,
        "columns": request.columns,
    }

    dashboard_id = _store.save(layout_dict)
    layout = _store.get(dashboard_id)

    logger.info("Dashboard 创建成功", dashboard_id=dashboard_id, title=request.title)
    return _layout_to_response(layout, dashboard_id)


@router.get("/list", response_model=DashboardListResponse)
async def list_dashboards(
    limit: int = Query(default=50, ge=1, le=200, description="返回数量上限"),
) -> DashboardListResponse:
    """列出所有 Dashboard。

    Args:
        limit: 返回数量上限。

    Returns:
        Dashboard 列表。
    """
    all_layouts = _store.list_all(limit=limit)
    responses = [
        _layout_to_response(layout, getattr(layout, "dashboard_id", ""))
        for layout in all_layouts
        if hasattr(layout, "dashboard_id")
    ]

    logger.info("列出 Dashboard", count=len(responses))
    return DashboardListResponse(
        dashboards=responses,
        total=len(responses),
    )


@router.get("/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard(dashboard_id: str) -> DashboardResponse:
    """获取 Dashboard 详情。

    Args:
        dashboard_id: Dashboard ID。

    Returns:
        Dashboard 详情。

    Raises:
        HTTPException: Dashboard 不存在时返回 404。
    """
    layout = _store.get(dashboard_id)
    if layout is None:
        raise HTTPException(status_code=404, detail=f"Dashboard 不存在: {dashboard_id}")

    logger.info("获取 Dashboard", dashboard_id=dashboard_id)
    return _layout_to_response(layout, dashboard_id)


@router.put("/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: str,
    request: UpdateDashboardRequest,
) -> DashboardResponse:
    """更新 Dashboard。

    Args:
        dashboard_id: Dashboard ID。
        request: 更新请求。

    Returns:
        更新后的 Dashboard 信息。

    Raises:
        HTTPException: Dashboard 不存在时返回 404。
    """
    layout = _store.get(dashboard_id)
    if layout is None:
        raise HTTPException(status_code=404, detail=f"Dashboard 不存在: {dashboard_id}")

    # 构建更新字典
    updates: dict[str, Any] = {}
    if request.title is not None:
        updates["title"] = request.title
    if request.description is not None:
        updates["description"] = request.description
    if request.add_panels is not None:
        updates["add_panels"] = request.add_panels
    if request.remove_panel_ids is not None:
        updates["remove_panel_ids"] = request.remove_panel_ids

    if not updates:
        raise HTTPException(status_code=400, detail="未提供任何更新字段")

    updated_layout = _store.update(dashboard_id, updates)
    logger.info("Dashboard 更新成功", dashboard_id=dashboard_id)
    return _layout_to_response(updated_layout, dashboard_id)


@router.delete("/{dashboard_id}")
async def delete_dashboard(dashboard_id: str) -> dict[str, Any]:
    """删除 Dashboard。

    Args:
        dashboard_id: Dashboard ID。

    Returns:
        删除结果。

    Raises:
        HTTPException: Dashboard 不存在时返回 404。
    """
    success = _store.delete(dashboard_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Dashboard 不存在: {dashboard_id}")

    logger.info("Dashboard 删除成功", dashboard_id=dashboard_id)
    return {"success": True, "dashboard_id": dashboard_id}
