"""图表数据模型测试。"""

from __future__ import annotations

from datapilot_chart.models import (
    ChartAxis,
    ChartAxisType,
    ChartSeries,
    ChartSpec,
    ChartTheme,
    ChartType,
)


class TestChartType:
    """ChartType 枚举测试。"""

    def test_enum_member_count(self) -> None:
        """ChartType 应包含 11 个成员。"""
        assert len(ChartType) == 11

    def test_enum_values(self) -> None:
        """ChartType 成员值应为预期字符串。"""
        assert ChartType.LINE == "line"
        assert ChartType.BAR == "bar"
        assert ChartType.PIE == "pie"
        assert ChartType.SCATTER == "scatter"
        assert ChartType.HEATMAP == "heatmap"
        assert ChartType.TABLE == "table"
        assert ChartType.RADAR == "radar"
        assert ChartType.FUNNEL == "funnel"
        assert ChartType.TREEMAP == "treemap"
        assert ChartType.BOXPLOT == "boxplot"
        assert ChartType.GAUGE == "gauge"

    def test_enum_is_str_enum(self) -> None:
        """ChartType 应是 StrEnum 子类，可直接与字符串比较。"""
        assert isinstance(ChartType.LINE, str)
        assert ChartType.LINE == "line"

    def test_enum_iteration(self) -> None:
        """ChartType 可迭代。"""
        types = list(ChartType)
        assert len(types) == 11
        assert types[0] == ChartType.LINE


class TestChartAxisType:
    """ChartAxisType 枚举测试。"""

    def test_member_count(self) -> None:
        """ChartAxisType 应包含 3 个成员。"""
        assert len(ChartAxisType) == 3

    def test_values(self) -> None:
        """ChartAxisType 成员值应为预期字符串。"""
        assert ChartAxisType.CATEGORY == "category"
        assert ChartAxisType.VALUE == "value"
        assert ChartAxisType.TIME == "time"


class TestChartAxis:
    """ChartAxis 数据类测试。"""

    def test_default_values(self) -> None:
        """ChartAxis 默认值测试。"""
        axis = ChartAxis(field="date")
        assert axis.field == "date"
        assert axis.name == ""
        assert axis.type == ChartAxisType.CATEGORY
        assert axis.show is True

    def test_custom_values(self) -> None:
        """ChartAxis 自定义值测试。"""
        axis = ChartAxis(
            field="amount",
            name="金额",
            type=ChartAxisType.VALUE,
            show=False,
        )
        assert axis.field == "amount"
        assert axis.name == "金额"
        assert axis.type == ChartAxisType.VALUE
        assert axis.show is False

    def test_time_axis(self) -> None:
        """ChartAxis 时间轴类型测试。"""
        axis = ChartAxis(field="ts", type=ChartAxisType.TIME)
        assert axis.type == ChartAxisType.TIME


class TestChartSeries:
    """ChartSeries 数据类测试。"""

    def test_default_values(self) -> None:
        """ChartSeries 默认值测试。"""
        series = ChartSeries(name="sales")
        assert series.name == "sales"
        assert series.data == []
        assert series.type == ""
        assert series.item_style == {}
        assert series.encode == {}

    def test_with_data(self) -> None:
        """ChartSeries 带数据测试。"""
        series = ChartSeries(
            name="revenue",
            data=[100, 200, 300],
            type="bar",
            item_style={"color": "#5470c6"},
        )
        assert series.name == "revenue"
        assert series.data == [100, 200, 300]
        assert series.type == "bar"
        assert series.item_style == {"color": "#5470c6"}


class TestChartTheme:
    """ChartTheme 数据类测试。"""

    def test_default_values(self) -> None:
        """ChartTheme 默认值测试。"""
        theme = ChartTheme()
        assert theme.colors == []
        assert theme.font_family == "Inter, system-ui, sans-serif"
        assert theme.background_color == "#ffffff"
        assert theme.text_color == "#333333"

    def test_custom_colors(self) -> None:
        """ChartTheme 自定义色板测试。"""
        theme = ChartTheme(colors=["#ff0000", "#00ff00"])
        assert len(theme.colors) == 2
        assert theme.colors[0] == "#ff0000"


class TestChartSpec:
    """ChartSpec 数据类测试。"""

    def test_minimal_construction(self) -> None:
        """ChartSpec 最简构造测试。"""
        spec = ChartSpec(chart_type=ChartType.LINE)
        assert spec.chart_type == ChartType.LINE
        assert spec.title == ""
        assert spec.x_axis is None
        assert spec.y_axis is None
        assert spec.series == []
        assert spec.tooltip == {}
        assert spec.legend == {}
        assert spec.grid == {}
        assert spec.theme is None
        assert spec.width == 800
        assert spec.height == 500

    def test_full_construction(self) -> None:
        """ChartSpec 完整构造测试。"""
        series = [ChartSeries(name="sales", data=[10, 20, 30])]
        theme = ChartTheme(colors=["#5470c6"])
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            title="月度销售额",
            x_axis=ChartAxis(field="month", name="月份"),
            y_axis=ChartAxis(field="sales", name="销售额", type=ChartAxisType.VALUE),
            series=series,
            tooltip={"trigger": "axis"},
            legend={"bottom": 0},
            grid={"left": "5%", "right": "5%"},
            theme=theme,
            width=1200,
            height=600,
        )
        assert spec.chart_type == ChartType.BAR
        assert spec.title == "月度销售额"
        assert spec.x_axis is not None
        assert spec.x_axis.field == "month"
        assert spec.y_axis is not None
        assert spec.y_axis.field == "sales"
        assert len(spec.series) == 1
        assert spec.series[0].name == "sales"
        assert spec.theme is not None
        assert spec.theme.colors == ["#5470c6"]
        assert spec.width == 1200
        assert spec.height == 600

    def test_default_dimensions(self) -> None:
        """ChartSpec 默认尺寸测试。"""
        spec = ChartSpec(chart_type=ChartType.PIE)
        assert spec.width == 800
        assert spec.height == 500

    def test_custom_dimensions(self) -> None:
        """ChartSpec 自定义尺寸测试。"""
        spec = ChartSpec(chart_type=ChartType.PIE, width=400, height=300)
        assert spec.width == 400
        assert spec.height == 300
