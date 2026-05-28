"""Dashboard 构建器。

提供从图表列表构建 Dashboard、添加/移除面板、自动布局等能力。
"""

from __future__ import annotations

import uuid

from .layout import LayoutEngine
from .models import DashboardFilterDef, DashboardLayout, DashboardPanel, PanelType


class DashboardBuilder:
    """Dashboard 构建器。

    提供链式 API 构建 Dashboard 布局。
    """

    def __init__(self) -> None:
        self._layout_engine = LayoutEngine()

    def build_from_charts(
        self,
        chart_specs: list[dict],
        title: str = "",
        description: str = "",
    ) -> DashboardLayout:
        """从图表列表自动构建 Dashboard。

        每个 chart_spec 自动创建一个 CHART 面板，并自动排列布局。

        Args:
            chart_specs: 图表规范列表，每个 dict 应包含 title 和 chart_spec 字段。
            title: Dashboard 标题。
            description: Dashboard 描述。

        Returns:
            构建好的 DashboardLayout 实例。
        """
        dashboard_id = f"dashboard-{uuid.uuid4().hex[:8]}"
        panels: list[DashboardPanel] = []

        for spec in chart_specs:
            panel = DashboardPanel(
                panel_id=f"panel-{uuid.uuid4().hex[:8]}",
                title=spec.get("title", "未命名图表"),
                panel_type=PanelType.CHART,
                chart_spec=spec,
            )
            panels.append(panel)

        layout = DashboardLayout(
            dashboard_id=dashboard_id,
            title=title or "新建仪表板",
            description=description,
            panels=panels,
        )

        # 自动排列布局
        self.auto_layout(layout)

        return layout

    def add_panel(
        self, layout: DashboardLayout, panel: DashboardPanel
    ) -> None:
        """添加面板到 Dashboard。

        Args:
            layout: 目标 Dashboard 布局。
            panel: 要添加的面板。
        """
        layout.panels.append(panel)

    def add_filter(
        self, layout: DashboardLayout, filter_def: DashboardFilterDef
    ) -> None:
        """添加过滤器到 Dashboard。

        Args:
            layout: 目标 Dashboard 布局。
            filter_def: 要添加的过滤器定义。
        """
        layout.filters.append(filter_def)

    def auto_layout(self, layout: DashboardLayout) -> None:
        """自动排列面板位置（网格布局）。

        根据面板宽度和 Dashboard 列数，计算每个面板的 row/col 位置。

        Args:
            layout: 要排列的 Dashboard 布局。
        """
        positions = self._layout_engine.calculate_positions(
            layout.panels, layout.columns
        )
        pos_map = {p["panel_id"]: p for p in positions}
        for panel in layout.panels:
            if panel.panel_id in pos_map:
                panel.position = {
                    "row": pos_map[panel.panel_id]["row"],
                    "col": pos_map[panel.panel_id]["col"],
                }

    def remove_panel(
        self, layout: DashboardLayout, panel_id: str
    ) -> bool:
        """移除面板。

        Args:
            layout: 目标 Dashboard 布局。
            panel_id: 要移除的面板 ID。

        Returns:
            是否成功移除。
        """
        for i, panel in enumerate(layout.panels):
            if panel.panel_id == panel_id:
                layout.panels.pop(i)
                # 移除后重新排列布局
                self.auto_layout(layout)
                return True
        return False

    def reorder_panels(
        self, layout: DashboardLayout, panel_ids: list[str]
    ) -> None:
        """重新排列面板顺序。

        按照 panel_ids 给定的顺序重新排列面板，不在列表中的面板追加到末尾。

        Args:
            layout: 目标 Dashboard 布局。
            panel_ids: 面板 ID 有序列表。
        """
        panel_map = {p.panel_id: p for p in layout.panels}
        reordered: list[DashboardPanel] = []

        # 按指定顺序排列
        for pid in panel_ids:
            if pid in panel_map:
                reordered.append(panel_map[pid])

        # 追加未在 panel_ids 中的面板
        for panel in layout.panels:
            if panel.panel_id not in panel_ids:
                reordered.append(panel)

        layout.panels = reordered

        # 重新计算布局位置
        self.auto_layout(layout)
