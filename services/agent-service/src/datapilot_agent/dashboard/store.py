"""Dashboard 存储管理。

提供 Dashboard 的内存存储实现，支持 CRUD 操作。
依赖 Track C 的 DashboardLayout 模型（TYPE_CHECKING 延迟导入）。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from datapilot_chart.dashboard.models import DashboardLayout

logger = structlog.get_logger(__name__)


class DashboardStore:
    """Dashboard 内存存储。

    管理所有 Dashboard 的生命周期：创建、查询、更新、删除。
    Phase1 使用内存字典存储，后续可替换为数据库持久化。
    """

    def __init__(self) -> None:
        self._dashboards: dict[str, DashboardLayout] = {}
        self._created_at: dict[str, str] = {}

    def save(self, layout: Any) -> str:
        """保存 Dashboard 布局。

        Args:
            layout: DashboardLayout 实例或包含 title 的字典。

        Returns:
            Dashboard ID。
        """
        dashboard_id = str(uuid.uuid4())

        # 兼容字典和 DashboardLayout 对象
        if isinstance(layout, dict):
            title = layout.get("title", "未命名 Dashboard")
            description = layout.get("description", "")
            chart_specs = layout.get("chart_specs", [])
            columns = layout.get("columns", 2)
            panels = [
                {
                    "panel_id": str(uuid.uuid4()),
                    "title": spec.get("title", "未命名面板"),
                    "chart_type": spec.get("chart_type", "bar"),
                    "chart_config": spec.get("chart_config", {}),
                    "data_source": spec.get("data_source", {}),
                    "row": idx // columns,
                    "col": idx % columns,
                }
                for idx, spec in enumerate(chart_specs)
            ]
            # 将 layout 对象存储为兼容格式
            stored_layout = type(
                "DashboardLayout",
                (),
                {
                    "dashboard_id": dashboard_id,
                    "title": title,
                    "description": description,
                    "panels": panels,
                    "filters": [],
                    "columns": columns,
                },
            )()
        else:
            stored_layout = layout
            if not hasattr(stored_layout, "dashboard_id"):
                stored_layout.dashboard_id = dashboard_id

        self._dashboards[dashboard_id] = stored_layout
        self._created_at[dashboard_id] = datetime.now(timezone.utc).isoformat()

        logger.info("Dashboard 已保存", dashboard_id=dashboard_id, title=getattr(stored_layout, "title", ""))
        return dashboard_id

    def get(self, dashboard_id: str) -> DashboardLayout | None:
        """获取 Dashboard。

        Args:
            dashboard_id: Dashboard ID。

        Returns:
            DashboardLayout 实例，不存在时返回 None。
        """
        return self._dashboards.get(dashboard_id)

    def list_all(self, limit: int = 50) -> list[DashboardLayout]:
        """列出所有 Dashboard。

        Args:
            limit: 返回数量上限。

        Returns:
            DashboardLayout 列表。
        """
        all_dashboards = list(self._dashboards.values())
        return all_dashboards[:limit]

    def delete(self, dashboard_id: str) -> bool:
        """删除 Dashboard。

        Args:
            dashboard_id: Dashboard ID。

        Returns:
            是否删除成功。
        """
        if dashboard_id not in self._dashboards:
            logger.warning("Dashboard 不存在，无法删除", dashboard_id=dashboard_id)
            return False

        del self._dashboards[dashboard_id]
        self._created_at.pop(dashboard_id, None)
        logger.info("Dashboard 已删除", dashboard_id=dashboard_id)
        return True

    def update(self, dashboard_id: str, updates: dict[str, Any]) -> DashboardLayout | None:
        """更新 Dashboard。

        Args:
            dashboard_id: Dashboard ID。
            updates: 更新字段字典，支持 title, description, add_panels, remove_panel_ids。

        Returns:
            更新后的 DashboardLayout，不存在时返回 None。
        """
        layout = self._dashboards.get(dashboard_id)
        if layout is None:
            logger.warning("Dashboard 不存在，无法更新", dashboard_id=dashboard_id)
            return None

        # 更新标题
        if "title" in updates and updates["title"] is not None:
            layout.title = updates["title"]

        # 更新描述
        if "description" in updates and updates["description"] is not None:
            layout.description = updates["description"]

        # 添加面板
        if "add_panels" in updates and updates["add_panels"]:
            panels = list(layout.panels) if layout.panels else []
            col_count = getattr(layout, "columns", 2) or 2
            for spec in updates["add_panels"]:
                panel = {
                    "panel_id": str(uuid.uuid4()),
                    "title": spec.get("title", "未命名面板"),
                    "chart_type": spec.get("chart_type", "bar"),
                    "chart_config": spec.get("chart_config", {}),
                    "data_source": spec.get("data_source", {}),
                    "row": len(panels) // col_count,
                    "col": len(panels) % col_count,
                }
                panels.append(panel)
            layout.panels = panels

        # 移除面板
        if "remove_panel_ids" in updates and updates["remove_panel_ids"]:
            panels = list(layout.panels) if layout.panels else []
            remove_ids = set(updates["remove_panel_ids"])
            layout.panels = [
                p for p in panels if p.get("panel_id") not in remove_ids
            ]

        logger.info("Dashboard 已更新", dashboard_id=dashboard_id, updates=list(updates.keys()))
        return layout

    def get_created_at(self, dashboard_id: str) -> str | None:
        """获取 Dashboard 创建时间。

        Args:
            dashboard_id: Dashboard ID。

        Returns:
            ISO 格式创建时间，不存在时返回 None。
        """
        return self._created_at.get(dashboard_id)

    def clear(self) -> None:
        """清空所有 Dashboard（仅用于测试）。"""
        self._dashboards.clear()
        self._created_at.clear()
