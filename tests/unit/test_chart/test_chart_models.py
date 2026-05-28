"""Chart 核心库单元测试。"""

from __future__ import annotations

import pytest

from datapilot_chart.models import (
    ChartAxis,
    ChartAxisType,
    ChartSeries,
    ChartSpec,
    ChartTheme,
    ChartType,
)
from datapilot_chart.type_infer import ChartTypeInferrer
from datapilot_chart.config_factory import ChartConfigFactory
from datapilot_chart.adapter import DataAdapter
from datapilot_chart.themes import DARK_THEME, LIGHT_THEME, CONTRAST_THEME


class TestChartType:
    """ChartType 枚举测试。"""

    def test_line_value(self) -> None:
        assert ChartType.LINE == "line"

    def test_bar_value(self) -> None:
        assert ChartType.BAR == "bar"

    def test_pie_value(self) -> None:
        assert ChartType.PIE == "pie"

    def test_scatter_value(self) -> None:
        assert ChartType.SCATTER == "scatter"

    def test_heatmap_value(self) -> None:
        assert ChartType.HEATMAP == "heatmap"

    def test_table_value(self) -> None:
        assert ChartType.TABLE == "table"

    def test_radar_value(self) -> None:
        assert ChartType.RADAR == "radar"

    def test_funnel_value(self) -> None:
        assert ChartType.FUNNEL == "funnel"

    def test_treemap_value(self) -> None:
        assert ChartType.TREEMAP == "treemap"

    def test_boxplot_value(self) -> None:
        assert ChartType.BOXPLOT == "boxplot"

    def test_gauge_value(self) -> None:
        assert ChartType.GAUGE == "gauge"

    def test_all_values_count(self) -> None:
        assert len(ChartType) == 11


class TestChartAxisType:
    """ChartAxisType 枚举测试。"""

    def test_category_value(self) -> None:
        assert ChartAxisType.CATEGORY == "category"

    def test_value_type(self) -> None:
        assert ChartAxisType.VALUE == "value"

    def test_time_value(self) -> None:
        assert ChartAxisType.TIME == "time"


class TestChartAxis:
    """ChartAxis 数据模型测试。"""

    def test_default_values(self) -> None:
        axis = ChartAxis(field="date")
        assert axis.field == "date"
        assert axis.name == ""
        assert axis.type == ChartAxisType.CATEGORY
        assert axis.show is True

    def test_custom_values(self) -> None:
        axis = ChartAxis(
            field="sales",
            name="销售额",
            type=ChartAxisType.VALUE,
            show=False,
        )
        assert axis.field == "sales"
        assert axis.name == "销售额"
        assert axis.type == ChartAxisType.VALUE
        assert axis.show is False


class TestChartSeries:
    """ChartSeries 数据模型测试。"""

    def test_default_values(self) -> None:
        series = ChartSeries(name="销售额")
        assert series.name == "销售额"
        assert series.data == []
        assert series.type == ""
        assert series.item_style == {}

    def test_with_data(self) -> None:
        series = ChartSeries(
            name="利润",
            data=[100, 200, 300],
            type="bar",
            item_style={"color": "#ff0000"},
        )
        assert series.data == [100, 200, 300]
        assert series.type == "bar"
        assert series.item_style["color"] == "#ff0000"


class TestChartSpec:
    """ChartSpec 数据模型测试。"""

    def test_minimal_spec(self) -> None:
        spec = ChartSpec(chart_type=ChartType.BAR)
        assert spec.chart_type == ChartType.BAR
        assert spec.title == ""
        assert spec.x_axis is None
        assert spec.y_axis is None
        assert spec.series == []

    def test_full_spec(self) -> None:
        spec = ChartSpec(
            chart_type=ChartType.LINE,
            title="销售趋势",
            x_axis=ChartAxis(field="date", name="日期"),
            y_axis=ChartAxis(field="sales", name="销售额", type=ChartAxisType.VALUE),
            series=[ChartSeries(name="销售额", data=[100, 200])],
            width=800,
            height=500,
        )
        assert spec.title == "销售趋势"
        assert spec.width == 800
        assert spec.height == 500
        assert len(spec.series) == 1

    def test_default_dimensions(self) -> None:
        spec = ChartSpec(chart_type=ChartType.PIE)
        assert spec.width == 800
        assert spec.height == 500


class TestChartTypeInferrer:
    """ChartTypeInferrer 测试。"""

    def setup_method(self) -> None:
        self.inferrer = ChartTypeInferrer()

    def test_time_and_numeric_recommends_line(self) -> None:
        columns = ["date", "sales"]
        rows = [["2025-01-01", 100], ["2025-02-01", 200], ["2025-03-01", 150]]
        result = self.inferrer.infer(columns, rows)
        assert ChartType.LINE in result
        assert result[0] == ChartType.LINE

    def test_text_and_numeric_recommends_bar(self) -> None:
        columns = ["city", "population"]
        rows = [["北京", 2100], ["上海", 2400], ["广州", 1800]]
        result = self.inferrer.infer(columns, rows)
        assert ChartType.BAR in result

    def test_few_categories_recommends_pie(self) -> None:
        columns = ["category", "count"]
        rows = [["A", 30], ["B", 50], ["C", 20]]
        result = self.inferrer.infer(columns, rows)
        assert ChartType.PIE in result

    def test_two_numeric_recommends_scatter(self) -> None:
        columns = ["height", "weight"]
        rows = [[170, 65], [175, 70], [160, 55], [180, 80]]
        result = self.inferrer.infer(columns, rows)
        assert ChartType.SCATTER in result

    def test_empty_data_returns_bar(self) -> None:
        result = self.inferrer.infer([], [])
        assert result == [ChartType.BAR]

    def test_result_is_sorted_by_score(self) -> None:
        columns = ["date", "sales", "profit"]
        rows = [["2025-01-01", 100, 30], ["2025-02-01", 200, 50]]
        result = self.inferrer.infer(columns, rows)
        # 时间列（>=8字符）+ 数值列 → line 得分最高
        assert ChartType.LINE in result[:2]


class TestChartConfigFactory:
    """ChartConfigFactory 测试。"""

    def setup_method(self) -> None:
        self.factory = ChartConfigFactory()

    def test_build_bar_option(self) -> None:
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            title="测试柱状图",
            x_axis=ChartAxis(field="city", name="城市"),
            y_axis=ChartAxis(field="sales", name="销售额", type=ChartAxisType.VALUE),
            series=[ChartSeries(name="销售额", data=[100, 200, 300])],
        )
        option = self.factory.build_option(spec)
        assert option["title"]["text"] == "测试柱状图"
        assert "series" in option
        assert len(option["series"]) == 1
        assert option["series"][0]["type"] == "bar"

    def test_build_line_option(self) -> None:
        spec = ChartSpec(
            chart_type=ChartType.LINE,
            series=[ChartSeries(name="销售额", data=[100, 200, 300])],
        )
        option = self.factory.build_option(spec)
        assert option["series"][0]["type"] == "line"
        assert option["series"][0]["smooth"] is True

    def test_build_pie_option(self) -> None:
        spec = ChartSpec(
            chart_type=ChartType.PIE,
            series=[ChartSeries(name="销售占比", data=[
                {"name": "A", "value": 30},
                {"name": "B", "value": 50},
            ])],
        )
        option = self.factory.build_option(spec)
        assert option["series"][0]["type"] == "pie"

    def test_build_option_has_tooltip(self) -> None:
        spec = ChartSpec(chart_type=ChartType.BAR)
        option = self.factory.build_option(spec)
        assert "tooltip" in option

    def test_build_option_has_theme_colors(self) -> None:
        spec = ChartSpec(chart_type=ChartType.BAR)
        option = self.factory.build_option(spec)
        assert "color" in option
        assert isinstance(option["color"], list)


class TestDataAdapter:
    """DataAdapter 测试。"""

    def setup_method(self) -> None:
        self.adapter = DataAdapter()

    def test_adapt_basic(self) -> None:
        columns = ["city", "sales"]
        rows = [["北京", 100], ["上海", 200], ["广州", 150]]
        series = self.adapter.adapt(columns, rows, x_field="city", y_fields=["sales"])
        assert len(series) == 1
        assert series[0].name == "sales"
        assert series[0].data == [100, 200, 150]

    def test_adapt_multiple_y_fields(self) -> None:
        columns = ["city", "sales", "profit"]
        rows = [["北京", 100, 30], ["上海", 200, 50]]
        series = self.adapter.adapt(columns, rows, x_field="city", y_fields=["sales", "profit"])
        assert len(series) == 2
        assert series[0].name == "sales"
        assert series[1].name == "profit"

    def test_adapt_empty_data(self) -> None:
        series = self.adapter.adapt([], [])
        assert series == []

    def test_detect_axes(self) -> None:
        columns = ["date", "sales"]
        rows = [["2025-01-01", 100], ["2025-02-01", 200]]
        x_field, y_fields = self.adapter.detect_axes(columns, rows)
        assert x_field == "date"
        assert "sales" in y_fields


class TestThemes:
    """内置主题测试。"""

    def test_dark_theme(self) -> None:
        assert DARK_THEME.background_color == "#1a1a2e"
        assert DARK_THEME.text_color == "#e0e0e0"
        assert len(DARK_THEME.colors) == 9

    def test_light_theme(self) -> None:
        assert LIGHT_THEME.background_color == "#ffffff"
        assert LIGHT_THEME.text_color == "#333333"

    def test_contrast_theme(self) -> None:
        assert CONTRAST_THEME.text_color == "#000000"
        assert len(CONTRAST_THEME.colors) == 9
