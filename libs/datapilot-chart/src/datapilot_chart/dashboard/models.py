"""Dashboard 数据模型。

定义面板类型、面板、过滤器、Dashboard 布局等核心数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class PanelType(StrEnum):
    """面板类型枚举。"""

    CHART = "chart"
    TABLE = "table"
    METRIC = "metric"
    TEXT = "text"


@dataclass
class DashboardPanel:
    """Dashboard 面板。

    Attributes:
        panel_id: 面板唯一标识。
        title: 面板标题。
        panel_type: 面板类型，默认为图表。
        width: 面板宽度，1-12 栅格列，默认 6。
        height: 面板高度（像素），默认 400。
        chart_spec: 图表规范序列化数据（CHART 类型使用）。
        metric_config: 指标卡片配置（METRIC 类型使用）。
        content: 文本内容（TEXT 类型使用）。
        position: 面板位置 {row, col}。
    """

    panel_id: str
    title: str
    panel_type: PanelType = PanelType.CHART
    width: int = 6  # 1-12 栅格列
    height: int = 400
    chart_spec: dict | None = None  # ChartSpec 序列化
    metric_config: dict | None = None  # 指标卡片配置 {metric, label, unit, trend}
    content: str = ""  # TEXT 类型内容
    position: dict = field(default_factory=dict)  # {row, col}

    def to_dict(self) -> dict[str, Any]:
        """将面板转换为字典。"""
        return {
            "panel_id": self.panel_id,
            "title": self.title,
            "panel_type": self.panel_type.value,
            "width": self.width,
            "height": self.height,
            "chart_spec": self.chart_spec,
            "metric_config": self.metric_config,
            "content": self.content,
            "position": self.position,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DashboardPanel:
        """从字典构建面板。"""
        panel_type = data.get("panel_type", "chart")
        if isinstance(panel_type, str):
            panel_type = PanelType(panel_type)
        return cls(
            panel_id=data["panel_id"],
            title=data["title"],
            panel_type=panel_type,
            width=data.get("width", 6),
            height=data.get("height", 400),
            chart_spec=data.get("chart_spec"),
            metric_config=data.get("metric_config"),
            content=data.get("content", ""),
            position=data.get("position", {}),
        )


@dataclass
class DashboardFilterDef:
    """Dashboard 过滤器定义。

    Attributes:
        filter_id: 过滤器唯一标识。
        field: 对应数据字段名。
        label: 过滤器显示标签。
        filter_type: 过滤器类型，支持 time_range / select / multi_select。
        options: 可选项列表。
        default_value: 默认值。
    """

    filter_id: str
    field: str
    label: str
    filter_type: str = "select"  # time_range / select / multi_select
    options: list[str] = field(default_factory=list)
    default_value: str | list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """将过滤器定义转换为字典。"""
        return {
            "filter_id": self.filter_id,
            "field": self.field,
            "label": self.label,
            "filter_type": self.filter_type,
            "options": self.options,
            "default_value": self.default_value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DashboardFilterDef:
        """从字典构建过滤器定义。"""
        return cls(
            filter_id=data["filter_id"],
            field=data["field"],
            label=data["label"],
            filter_type=data.get("filter_type", "select"),
            options=data.get("options", []),
            default_value=data.get("default_value"),
        )


@dataclass
class DashboardLayout:
    """Dashboard 布局。

    Attributes:
        dashboard_id: Dashboard 唯一标识。
        title: Dashboard 标题。
        description: Dashboard 描述。
        panels: 面板列表。
        filters: 过滤器定义列表。
        columns: 栅格列数，默认 12。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    dashboard_id: str
    title: str
    description: str = ""
    panels: list[DashboardPanel] = field(default_factory=list)
    filters: list[DashboardFilterDef] = field(default_factory=list)
    columns: int = 12
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """将 Dashboard 布局转换为字典。"""
        return {
            "dashboard_id": self.dashboard_id,
            "title": self.title,
            "description": self.description,
            "panels": [p.to_dict() for p in self.panels],
            "filters": [f.to_dict() for f in self.filters],
            "columns": self.columns,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DashboardLayout:
        """从字典构建 Dashboard 布局。"""
        panels = [
            DashboardPanel.from_dict(p) for p in data.get("panels", [])
        ]
        filters = [
            DashboardFilterDef.from_dict(f) for f in data.get("filters", [])
        ]
        return cls(
            dashboard_id=data["dashboard_id"],
            title=data["title"],
            description=data.get("description", ""),
            panels=panels,
            filters=filters,
            columns=data.get("columns", 12),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
