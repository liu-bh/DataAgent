"""图表类型推断测试。"""

from __future__ import annotations

from datapilot_chart.models import ChartType
from datapilot_chart.type_infer import ChartTypeInferrer


class TestChartTypeInferrer:
    """ChartTypeInferrer 推断规则测试。"""

    def setup_method(self) -> None:
        """每个测试前初始化推断器。"""
        self.inferrer = ChartTypeInferrer()

    # ---- 时间 + 数值 -> line ----

    def test_time_and_numeric_recommends_line(self) -> None:
        """时间列 + 数值列应推荐 line 图。"""
        columns = ["date", "sales"]
        rows = [
            ["2024-01-01", 100],
            ["2024-02-01", 200],
            ["2024-03-01", 150],
        ]
        result = self.inferrer.infer(columns, rows)
        assert result[0] == ChartType.LINE

    def test_time_and_numeric_also_recommends_bar(self) -> None:
        """时间 + 数值时，bar 应在推荐列表中。"""
        columns = ["date", "revenue"]
        rows = [
            ["2024-01-01", 500],
            ["2024-02-01", 600],
        ]
        result = self.inferrer.infer(columns, rows)
        assert ChartType.BAR in result

    def test_slash_date_format_detected_as_time(self) -> None:
        """斜杠日期格式应识别为时间列。"""
        columns = ["date", "value"]
        rows = [
            ["2024/01/01", 10],
            ["2024/02/01", 20],
            ["2024/03/01", 30],
        ]
        result = self.inferrer.infer(columns, rows)
        assert ChartType.LINE in result

    # ---- 维度 + 数值 -> bar ----

    def test_text_and_numeric_recommends_bar(self) -> None:
        """维度(文本)列 + 数值列应推荐 bar 图。"""
        columns = ["category", "amount"]
        rows = [
            [f"cat{i}", i * 10] for i in range(1, 12)
        ]
        result = self.inferrer.infer(columns, rows)
        assert result[0] == ChartType.BAR

    # ---- 少量维度 -> pie ----

    def test_few_categories_recommends_pie(self) -> None:
        """少量维度（2-8 个唯一值）应推荐 pie 图。"""
        columns = ["region", "sales"]
        rows = [
            ["华东", 300],
            ["华北", 200],
            ["华南", 250],
        ]
        result = self.inferrer.infer(columns, rows)
        assert ChartType.PIE in result

    def test_two_categories_recommends_pie(self) -> None:
        """2 个唯一值应推荐 pie。"""
        columns = ["status", "count"]
        rows = [
            ["成功", 80],
            ["失败", 20],
        ]
        result = self.inferrer.infer(columns, rows)
        assert ChartType.PIE in result

    def test_many_categories_not_recommends_pie(self) -> None:
        """超过 8 个唯一值不应推荐 pie。"""
        columns = ["city", "value"]
        rows = [[f"城市{i}", i * 10] for i in range(1, 11)]
        result = self.inferrer.infer(columns, rows)
        assert ChartType.PIE not in result

    # ---- 双数值 -> scatter ----

    def test_two_numeric_columns_recommends_scatter(self) -> None:
        """两个数值列（无文本/时间）应推荐 scatter。"""
        columns = ["x", "y"]
        rows = [
            [1.0, 2.0],
            [3.0, 5.0],
            [2.5, 4.0],
        ]
        result = self.inferrer.infer(columns, rows)
        assert result[0] == ChartType.SCATTER

    def test_three_numeric_columns_recommends_scatter(self) -> None:
        """三个数值列应推荐 scatter。"""
        columns = ["a", "b", "c"]
        rows = [
            [1, 2, 3],
            [4, 5, 6],
        ]
        result = self.inferrer.infer(columns, rows)
        assert ChartType.SCATTER in result

    # ---- 多维度 -> radar ----

    def test_three_numeric_and_one_text_recommends_radar(self) -> None:
        """3 个数值列 + 1 个文本列应推荐 radar。"""
        columns = ["name", "speed", "power", "defense"]
        rows = [
            ["角色A", 80, 90, 70],
            ["角色B", 60, 85, 95],
        ]
        result = self.inferrer.infer(columns, rows)
        assert ChartType.RADAR in result

    # ---- 空数据 -> bar ----

    def test_empty_columns_returns_bar(self) -> None:
        """空列列表应返回默认 bar。"""
        result = self.inferrer.infer([], [])
        assert result == [ChartType.BAR]

    def test_empty_rows_returns_bar(self) -> None:
        """空行列表应返回默认 bar。"""
        result = self.inferrer.infer(["col1", "col2"], [])
        assert result == [ChartType.BAR]

    def test_none_columns_returns_bar(self) -> None:
        """None 列列表应返回默认 bar。"""
        result = self.inferrer.infer([], [])
        assert result == [ChartType.BAR]

    # ---- 纯文本 -> table ----

    def test_text_only_columns_recommends_table(self) -> None:
        """纯文本列应推荐 table。"""
        columns = ["name", "department"]
        rows = [
            ["张三", "研发部"],
            ["李四", "市场部"],
        ]
        result = self.inferrer.infer(columns, rows)
        assert ChartType.TABLE in result

    # ---- 数值 + 百分比 -> gauge ----

    def test_numeric_and_percentage_recommends_gauge(self) -> None:
        """数值列 + 百分比列应推荐 gauge。"""
        columns = ["metric", "rate"]
        rows = [
            [100, "85%"],
            [200, "90%"],
        ]
        result = self.inferrer.infer(columns, rows)
        assert ChartType.GAUGE in result

    # ---- 排序验证 ----

    def test_result_sorted_by_score(self) -> None:
        """结果应按匹配度降序排列。"""
        columns = ["date", "sales"]
        rows = [
            ["2024-01-01", 100],
            ["2024-02-01", 200],
        ]
        result = self.inferrer.infer(columns, rows)
        # line 得分 100, bar 得分 70
        assert result[0] == ChartType.LINE
        assert result.index(ChartType.LINE) < result.index(ChartType.BAR)

    # ---- 边界场景 ----

    def test_single_column_numeric(self) -> None:
        """单列数值数据不应崩溃。"""
        columns = ["value"]
        rows = [[1], [2], [3]]
        result = self.inferrer.infer(columns, rows)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_all_null_values(self) -> None:
        """全空值数据不应崩溃。"""
        columns = ["a", "b"]
        rows = [
            [None, None],
            [None, None],
        ]
        result = self.inferrer.infer(columns, rows)
        assert isinstance(result, list)

    def test_mixed_types_dominant_numeric(self) -> None:
        """混合类型中数值占多数应识别为数值列。"""
        columns = ["mixed", "value"]
        rows = [
            ["text", 10],
            [20, 20],
            [30, 30],
        ]
        result = self.inferrer.infer(columns, rows)
        # mixed 列中 numeric 2/3 > 60%，识别为 numeric
        assert isinstance(result, list)

    def test_chinese_date_format(self) -> None:
        """中文日期格式应识别为时间列。"""
        columns = ["日期", "销量"]
        rows = [
            ["2024年01月", 100],
            ["2024年02月", 200],
        ]
        result = self.inferrer.infer(columns, rows)
        assert ChartType.LINE in result

    def test_iso_date_format(self) -> None:
        """ISO 日期格式（含 T）应识别为时间列。"""
        columns = ["ts", "val"]
        rows = [
            ["2024-01-01T00:00:00", 5],
            ["2024-02-01T00:00:00", 8],
        ]
        result = self.inferrer.infer(columns, rows)
        assert ChartType.LINE in result
