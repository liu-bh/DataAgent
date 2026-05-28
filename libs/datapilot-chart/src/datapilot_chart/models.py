"""图表数据模型定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ChartType(StrEnum):
    """支持的图表类型枚举。"""

    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    TABLE = "table"
    RADAR = "radar"
    FUNNEL = "funnel"
    TREEMAP = "treemap"
    BOXPLOT = "boxplot"
    GAUGE = "gauge"


class ChartAxisType(StrEnum):
    """坐标轴类型枚举。"""

    CATEGORY = "category"
    VALUE = "value"
    TIME = "time"


@dataclass
class ChartAxis:
    """坐标轴定义。"""

    field: str
    name: str = ""
    type: ChartAxisType = ChartAxisType.CATEGORY
    show: bool = True


@dataclass
class ChartSeries:
    """数据系列定义。"""

    name: str
    data: list[Any] = field(default_factory=list)
    type: str = ""
    item_style: dict[str, Any] = field(default_factory=dict)
    encode: dict[str, str] = field(default_factory=dict)


@dataclass
class ChartTheme:
    """图表主题配置。"""

    colors: list[str] = field(default_factory=list)
    font_family: str = "Inter, system-ui, sans-serif"
    background_color: str = "#ffffff"
    text_color: str = "#333333"


@dataclass
class ChartSpec:
    """图表规范，描述一张完整图表的所有配置。"""

    chart_type: ChartType
    title: str = ""
    x_axis: ChartAxis | None = None
    y_axis: ChartAxis | None = None
    series: list[ChartSeries] = field(default_factory=list)
    tooltip: dict[str, Any] = field(default_factory=dict)
    legend: dict[str, Any] = field(default_factory=dict)
    grid: dict[str, Any] = field(default_factory=dict)
    theme: ChartTheme | None = None
    width: int = 800
    height: int = 500
