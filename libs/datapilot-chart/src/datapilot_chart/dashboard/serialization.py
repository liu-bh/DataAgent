"""Dashboard 序列化。

提供 Dashboard 布局的 JSON 和 dict 序列化/反序列化能力。
"""

from __future__ import annotations

import json

from .models import DashboardLayout


class DashboardSerializer:
    """Dashboard 序列化器。

    支持 JSON 字符串和 Python 字典之间的相互转换。
    """

    def to_json(self, layout: DashboardLayout) -> str:
        """将 Dashboard 布局序列化为 JSON 字符串。

        Args:
            layout: Dashboard 布局。

        Returns:
            JSON 字符串。
        """
        return json.dumps(layout.to_dict(), ensure_ascii=False, indent=2)

    def from_json(self, json_str: str) -> DashboardLayout:
        """从 JSON 字符串反序列化 Dashboard 布局。

        Args:
            json_str: JSON 字符串。

        Returns:
            Dashboard 布局实例。
        """
        data = json.loads(json_str)
        return DashboardLayout.from_dict(data)

    def to_dict(self, layout: DashboardLayout) -> dict:
        """将 Dashboard 布局转换为字典。

        Args:
            layout: Dashboard 布局。

        Returns:
            字典。
        """
        return layout.to_dict()

    def from_dict(self, data: dict) -> DashboardLayout:
        """从字典构建 Dashboard 布局。

        Args:
            data: 字典数据。

        Returns:
            Dashboard 布局实例。
        """
        return DashboardLayout.from_dict(data)
