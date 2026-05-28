"""ECharts 配置工厂测试。"""

from __future__ import annotations

from datapilot_chart.models import (
    ChartAxis,
    ChartAxisType,
    ChartSeries,
    ChartSpec,
    ChartTheme,
    ChartType,
)
from datapilot_chart.config_factory import ChartConfigFactory
from datapilot_chart.themes import DARK_THEME, LIGHT_THEME


class TestChartConfigFactory:
    """ChartConfigFactory 测试。"""

    def setup_method(self) -> None:
        """每个测试前初始化工厂。"""
        self.factory = ChartConfigFactory()

    # ---- Line Chart ----

    def test_line_chart_has_xaxis(self) -> None:
        """折线图应包含 xAxis 配置。"""
        spec = ChartSpec(
            chart_type=ChartType.LINE,
            x_axis=ChartAxis(field="month"),
            y_axis=ChartAxis(field="sales", type=ChartAxisType.VALUE),
            series=[ChartSeries(name="sales", data=[100, 200, 300])],
        )
        option = self.factory.build_option(spec)
        assert "xAxis" in option
        assert option["xAxis"]["type"] == "category"

    def test_line_chart_has_yaxis(self) -> None:
        """折线图应包含 yAxis 配置。"""
        spec = ChartSpec(
            chart_type=ChartType.LINE,
            x_axis=ChartAxis(field="month"),
            y_axis=ChartAxis(field="sales", type=ChartAxisType.VALUE),
            series=[ChartSeries(name="sales", data=[100, 200])],
        )
        option = self.factory.build_option(spec)
        assert "yAxis" in option
        assert option["yAxis"]["type"] == "value"

    def test_line_chart_series_type(self) -> None:
        """折线图 series 类型应为 line。"""
        spec = ChartSpec(
            chart_type=ChartType.LINE,
            x_axis=ChartAxis(field="x"),
            series=[ChartSeries(name="s1", data=[1, 2, 3])],
        )
        option = self.factory.build_option(spec)
        assert len(option["series"]) == 1
        assert option["series"][0]["type"] == "line"

    def test_line_chart_smooth(self) -> None:
        """折线图应启用平滑曲线。"""
        spec = ChartSpec(
            chart_type=ChartType.LINE,
            x_axis=ChartAxis(field="x"),
            series=[ChartSeries(name="s1", data=[1, 2, 3])],
        )
        option = self.factory.build_option(spec)
        assert option["series"][0]["smooth"] is True

    # ---- Bar Chart ----

    def test_bar_chart_series_type(self) -> None:
        """柱状图 series 类型应为 bar。"""
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            x_axis=ChartAxis(field="category"),
            series=[ChartSeries(name="s1", data=[10, 20])],
        )
        option = self.factory.build_option(spec)
        assert option["series"][0]["type"] == "bar"

    def test_bar_chart_has_xaxis(self) -> None:
        """柱状图应包含 xAxis。"""
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            x_axis=ChartAxis(field="x"),
            series=[ChartSeries(name="s1", data=[1, 2])],
        )
        option = self.factory.build_option(spec)
        assert "xAxis" in option

    def test_bar_chart_has_yaxis(self) -> None:
        """柱状图应包含 yAxis。"""
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            y_axis=ChartAxis(field="y", type=ChartAxisType.VALUE),
            series=[ChartSeries(name="s1", data=[1, 2])],
        )
        option = self.factory.build_option(spec)
        assert "yAxis" in option

    # ---- Pie Chart ----

    def test_pie_chart_series_type(self) -> None:
        """饼图 series 类型应为 pie。"""
        spec = ChartSpec(
            chart_type=ChartType.PIE,
            series=[ChartSeries(name="s1", data=[10, 20, 30])],
        )
        option = self.factory.build_option(spec)
        assert option["series"][0]["type"] == "pie"

    def test_pie_chart_has_radius(self) -> None:
        """饼图应有 radius 配置。"""
        spec = ChartSpec(
            chart_type=ChartType.PIE,
            series=[ChartSeries(name="s1", data=[10, 20])],
        )
        option = self.factory.build_option(spec)
        assert "radius" in option["series"][0]

    # ---- Scatter Chart ----

    def test_scatter_chart_series_type(self) -> None:
        """散点图 series 类型应为 scatter。"""
        spec = ChartSpec(
            chart_type=ChartType.SCATTER,
            x_axis=ChartAxis(field="x", type=ChartAxisType.VALUE),
            series=[ChartSeries(name="s1", data=[[1, 2], [3, 4]])],
        )
        option = self.factory.build_option(spec)
        assert option["series"][0]["type"] == "scatter"

    def test_scatter_chart_has_both_axes(self) -> None:
        """散点图应有 xAxis 和 yAxis。"""
        spec = ChartSpec(
            chart_type=ChartType.SCATTER,
            series=[ChartSeries(name="s1", data=[[1, 2]])],
        )
        option = self.factory.build_option(spec)
        assert "xAxis" in option
        assert "yAxis" in option
        assert option["xAxis"]["type"] == "value"

    # ---- Theme ----

    def test_dark_theme_applied(self) -> None:
        """深色主题应正确应用到 backgroundColor 和 textStyle。"""
        spec = ChartSpec(
            chart_type=ChartType.LINE,
            theme=DARK_THEME,
            series=[ChartSeries(name="s1", data=[1, 2])],
        )
        option = self.factory.build_option(spec)
        assert option["backgroundColor"] == "#1a1a2e"
        assert option["textStyle"]["color"] == "#e0e0e0"

    def test_light_theme_applied(self) -> None:
        """浅色主题应正确应用。"""
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            theme=LIGHT_THEME,
            series=[ChartSeries(name="s1", data=[1, 2])],
        )
        option = self.factory.build_option(spec)
        assert option["backgroundColor"] == "#ffffff"

    def test_default_theme_is_dark(self) -> None:
        """未指定主题时应使用深色主题。"""
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            series=[ChartSeries(name="s1", data=[1, 2])],
        )
        option = self.factory.build_option(spec)
        assert option["backgroundColor"] == "#1a1a2e"

    # ---- Tooltip & Legend ----

    def test_default_tooltip(self) -> None:
        """默认 tooltip 应为 trigger: axis。"""
        spec = ChartSpec(
            chart_type=ChartType.LINE,
            series=[ChartSeries(name="s1", data=[1, 2])],
        )
        option = self.factory.build_option(spec)
        assert option["tooltip"] == {"trigger": "axis"}

    def test_custom_tooltip(self) -> None:
        """自定义 tooltip 应被正确应用。"""
        spec = ChartSpec(
            chart_type=ChartType.LINE,
            series=[ChartSeries(name="s1", data=[1, 2])],
            tooltip={"trigger": "item", "formatter": "{b}: {c}"},
        )
        option = self.factory.build_option(spec)
        assert option["tooltip"]["formatter"] == "{b}: {c}"

    def test_legend_from_series(self) -> None:
        """legend 应自动从 series 名称生成。"""
        spec = ChartSpec(
            chart_type=ChartType.LINE,
            series=[
                ChartSeries(name="sales", data=[1, 2]),
                ChartSeries(name="profit", data=[3, 4]),
            ],
        )
        option = self.factory.build_option(spec)
        assert option["legend"]["data"] == ["sales", "profit"]

    # ---- Title ----

    def test_title_configured(self) -> None:
        """标题应正确配置。"""
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            title="月度销售报告",
            series=[ChartSeries(name="s1", data=[1, 2])],
        )
        option = self.factory.build_option(spec)
        assert option["title"]["text"] == "月度销售报告"
        assert option["title"]["left"] == "center"

    def test_no_title_when_empty(self) -> None:
        """空标题时不应包含 title 配置。"""
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            series=[ChartSeries(name="s1", data=[1, 2])],
        )
        option = self.factory.build_option(spec)
        assert "title" not in option

    # ---- Radar Chart ----

    def test_radar_chart_has_radar_config(self) -> None:
        """雷达图应包含 radar 配置。"""
        spec = ChartSpec(
            chart_type=ChartType.RADAR,
            x_axis=ChartAxis(field="dim"),
            series=[ChartSeries(name="s1", data=[80, 90, 70])],
        )
        option = self.factory.build_option(spec)
        assert "radar" in option
        assert "indicator" in option["radar"]

    # ---- Gauge Chart ----

    def test_gauge_chart_series_type(self) -> None:
        """仪表盘 series 类型应为 gauge。"""
        spec = ChartSpec(
            chart_type=ChartType.GAUGE,
            series=[ChartSeries(name="完成率", data=[{"value": 85, "name": "完成率"}])],
        )
        option = self.factory.build_option(spec)
        assert option["series"][0]["type"] == "gauge"

    # ---- Colors ----

    def test_theme_colors_applied(self) -> None:
        """主题色板应应用到 option。"""
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            theme=DARK_THEME,
            series=[ChartSeries(name="s1", data=[1, 2])],
        )
        option = self.factory.build_option(spec)
        assert option["color"] == DARK_THEME.colors
