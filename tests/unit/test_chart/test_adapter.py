"""数据适配器测试。"""

from __future__ import annotations

from datapilot_chart.adapter import DataAdapter
from datapilot_chart.models import ChartSeries


class TestDataAdapter:
    """DataAdapter 测试。"""

    def setup_method(self) -> None:
        """每个测试前初始化适配器。"""
        self.adapter = DataAdapter()

    # ---- 基本适配 ----

    def test_basic_adapt(self) -> None:
        """基本适配：columns + rows -> ChartSeries 列表。"""
        columns = ["month", "sales"]
        rows = [
            ["1月", 100],
            ["2月", 200],
            ["3月", 150],
        ]
        series_list = self.adapter.adapt(columns, rows)
        assert len(series_list) == 1
        assert series_list[0].name == "sales"
        assert series_list[0].data == [100, 200, 150]

    def test_adapt_multiple_y_fields(self) -> None:
        """适配多个 y 字段。"""
        columns = ["month", "sales", "profit"]
        rows = [
            ["1月", 100, 30],
            ["2月", 200, 50],
        ]
        series_list = self.adapter.adapt(columns, rows)
        assert len(series_list) == 2
        names = [s.name for s in series_list]
        assert "sales" in names
        assert "profit" in names

    def test_adapt_series_data_length(self) -> None:
        """适配后每个 series 的数据长度应与行数一致。"""
        columns = ["x", "y"]
        rows = [[1, 10], [2, 20], [3, 30], [4, 40]]
        series_list = self.adapter.adapt(columns, rows)
        assert all(len(s.data) == 4 for s in series_list)

    # ---- 指定 x_field / y_fields ----

    def test_specified_x_and_y_fields(self) -> None:
        """手动指定 x/y 字段。"""
        columns = ["month", "sales", "profit"]
        rows = [
            ["1月", 100, 30],
            ["2月", 200, 50],
        ]
        series_list = self.adapter.adapt(
            columns, rows, x_field="month", y_fields=["sales"]
        )
        assert len(series_list) == 1
        assert series_list[0].name == "sales"
        assert series_list[0].data == [100, 200]

    def test_specified_multiple_y_fields(self) -> None:
        """手动指定多个 y 字段。"""
        columns = ["x", "a", "b", "c"]
        rows = [[1, 10, 20, 30]]
        series_list = self.adapter.adapt(
            columns, rows, x_field="x", y_fields=["a", "c"]
        )
        assert len(series_list) == 2
        names = [s.name for s in series_list]
        assert "a" in names
        assert "c" in names

    # ---- 自动检测轴字段 ----

    def test_detect_axes_time_column(self) -> None:
        """自动检测：时间列应作为 x 轴。"""
        columns = ["date", "sales"]
        rows = [
            ["2024-01-01", 100],
            ["2024-02-01", 200],
        ]
        x_field, y_fields = self.adapter.detect_axes(columns, rows)
        assert x_field == "date"
        assert y_fields == ["sales"]

    def test_detect_axes_text_column(self) -> None:
        """自动检测：文本列应作为 x 轴。"""
        columns = ["category", "value"]
        rows = [
            ["A", 10],
            ["B", 20],
        ]
        x_field, y_fields = self.adapter.detect_axes(columns, rows)
        assert x_field == "category"
        assert y_fields == ["value"]

    def test_detect_axes_numeric_as_x_when_no_text_or_time(self) -> None:
        """自动检测：无文本/时间列时，第一列作为 x。"""
        columns = ["x_val", "y_val"]
        rows = [
            [1, 10],
            [2, 20],
        ]
        x_field, y_fields = self.adapter.detect_axes(columns, rows)
        assert x_field == "x_val"
        assert "y_val" in y_fields

    # ---- 空数据处理 ----

    def test_empty_columns(self) -> None:
        """空列列表应返回空 series 列表。"""
        result = self.adapter.adapt([], [])
        assert result == []

    def test_empty_rows(self) -> None:
        """空行列表应返回空 series 列表。"""
        result = self.adapter.adapt(["col1", "col2"], [])
        assert result == []

    def test_adapt_returns_chart_series(self) -> None:
        """适配结果应为 ChartSeries 实例。"""
        columns = ["x", "y"]
        rows = [[1, 10]]
        series_list = self.adapter.adapt(columns, rows)
        assert all(isinstance(s, ChartSeries) for s in series_list)

    # ---- 边界场景 ----

    def test_uneven_rows(self) -> None:
        """行长度不一时应安全处理。"""
        columns = ["a", "b"]
        rows = [
            [1, 10],
            [2],  # 缺少 b 值
            [3, 30],
        ]
        series_list = self.adapter.adapt(columns, rows)
        assert len(series_list) == 1
        # 第二行缺少 b，应跳过
        assert series_list[0].data == [10, 30]

    def test_none_values_in_rows(self) -> None:
        """行中包含 None 值时应安全处理。"""
        columns = ["x", "y"]
        rows = [
            ["a", 10],
            ["b", None],
            ["c", 30],
        ]
        series_list = self.adapter.adapt(columns, rows)
        assert len(series_list) == 1
        assert series_list[0].data == [10, None, 30]

    def test_detect_axes_empty_columns(self) -> None:
        """空列列表检测轴应返回空元组。"""
        x_field, y_fields = self.adapter.detect_axes([], [])
        assert x_field == ""
        assert y_fields == []

    def test_detect_axes_empty_rows(self) -> None:
        """空行检测轴：第一列作为 x，其余作为 y。"""
        x_field, y_fields = self.adapter.detect_axes(["a", "b", "c"], [])
        assert x_field == "a"
        assert y_fields == ["b", "c"]

    def test_x_field_not_in_columns_fallback(self) -> None:
        """指定的 x_field 不在 columns 中时应回退到第一列。"""
        columns = ["actual_x", "y"]
        rows = [[1, 10], [2, 20]]
        series_list = self.adapter.adapt(
            columns, rows, x_field="nonexistent", y_fields=["y"]
        )
        assert len(series_list) == 1
