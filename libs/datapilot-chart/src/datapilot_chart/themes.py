"""内置图表主题定义。"""

from __future__ import annotations

from datapilot_chart.models import ChartTheme

# 深色主题：适合数据大屏和暗色界面
DARK_THEME = ChartTheme(
    colors=[
        "#5470c6",
        "#91cc75",
        "#fac858",
        "#ee6666",
        "#73c0de",
        "#3ba272",
        "#fc8452",
        "#9a60b4",
        "#ea7ccc",
    ],
    font_family="Inter, system-ui, sans-serif",
    background_color="#1a1a2e",
    text_color="#e0e0e0",
)

# 浅色主题：适合普通业务报表
LIGHT_THEME = ChartTheme(
    colors=[
        "#5470c6",
        "#91cc75",
        "#fac858",
        "#ee6666",
        "#73c0de",
        "#3ba272",
        "#fc8452",
        "#9a60b4",
        "#ea7ccc",
    ],
    font_family="Inter, system-ui, sans-serif",
    background_color="#ffffff",
    text_color="#333333",
)

# 高对比度主题：适合无障碍场景
CONTRAST_THEME = ChartTheme(
    colors=[
        "#003f88",
        "#0077b6",
        "#00b4d8",
        "#e63946",
        "#f4a261",
        "#2a9d8f",
        "#264653",
        "#e76f51",
        "#a8dadc",
    ],
    font_family="system-ui, sans-serif",
    background_color="#ffffff",
    text_color="#000000",
)
