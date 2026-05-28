"""布局引擎。

计算 Dashboard 面板位置，验证布局合理性。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import DashboardPanel


class LayoutEngine:
    """Dashboard 布局引擎。

    负责面板位置的自动计算和布局验证。
    """

    def calculate_positions(
        self,
        panels: list[DashboardPanel],
        columns: int = 12,
    ) -> list[dict]:
        """计算面板位置。

        算法：
        - 面板按顺序排列
        - 当前面板占满一行（累计 width >= columns）时换行
        - 返回 [{panel_id, row, col}]

        Args:
            panels: 面板列表。
            columns: 栅格总列数。

        Returns:
            面板位置列表，每个元素包含 panel_id、row、col。
        """
        positions: list[dict] = []
        row = 0
        col = 0

        for panel in panels:
            positions.append({
                "panel_id": panel.panel_id,
                "row": row,
                "col": col,
            })
            col += panel.width

            # 当累计宽度达到或超过列数时换行
            if col >= columns:
                row += 1
                col = 0

        return positions

    def validate_layout(
        self,
        panels: list[DashboardPanel],
        columns: int,
    ) -> list[str]:
        """验证布局合理性，返回问题列表。

        检查项：
        - 面板宽度是否在 1-12 范围内
        - 面板宽度是否超过总列数
        - 面板 ID 是否重复
        - 面板标题是否为空

        Args:
            panels: 面板列表。
            columns: 栅格总列数。

        Returns:
            问题描述列表，空列表表示布局合法。
        """
        issues: list[str] = []

        if not panels:
            return issues

        # 检查面板宽度范围
        for panel in panels:
            if panel.width < 1 or panel.width > 12:
                issues.append(
                    f"面板 '{panel.panel_id}' 的宽度 {panel.width} "
                    f"不在有效范围 1-12 内"
                )

            # 检查宽度是否超过总列数
            if panel.width > columns:
                issues.append(
                    f"面板 '{panel.panel_id}' 的宽度 {panel.width} "
                    f"超过总列数 {columns}"
                )

            # 检查标题是否为空
            if not panel.title:
                issues.append(
                    f"面板 '{panel.panel_id}' 的标题为空"
                )

        # 检查面板 ID 是否重复
        panel_ids = [p.panel_id for p in panels]
        seen: set[str] = set()
        for pid in panel_ids:
            if pid in seen:
                issues.append(f"面板 ID '{pid}' 重复")
            seen.add(pid)

        return issues
