"""DataPilot Chart — 图表规范统一库。

提供图表类型定义、数据模型、类型推断、ECharts 配置生成、
内置主题和数据适配等核心能力。
"""

from datapilot_chart.adapter import DataAdapter
from datapilot_chart.config_factory import ChartConfigFactory
from datapilot_chart.models import (
    ChartAxis,
    ChartAxisType,
    ChartSeries,
    ChartSpec,
    ChartTheme,
    ChartType,
)
from datapilot_chart.themes import CONTRAST_THEME, DARK_THEME, LIGHT_THEME
from datapilot_chart.type_infer import ChartTypeInferrer

__all__ = [
    "ChartAxis",
    "ChartAxisType",
    "ChartSeries",
    "ChartSpec",
    "ChartTheme",
    "ChartType",
    "ChartTypeInferrer",
    "ChartConfigFactory",
    "CONTRAST_THEME",
    "DARK_THEME",
    "LIGHT_THEME",
    "DataAdapter",
]
