"""图表推荐器单元测试。"""

from __future__ import annotations

from datapilot_agent.chart.recommender import (
    ChartRecommender,
    ChartRecommendation,
)


class TestChartRecommender:
    """ChartRecommender 规则推断测试。"""

    def setup_method(self) -> None:
        self.recommender = ChartRecommender()

    def test_recommend_time_numeric(self) -> None:
        """时间列 + 数值列应推荐 line。"""
        columns = [
            {"name": "date", "type": "date"},
            {"name": "sales", "type": "integer"},
        ]
        rows = [
            {"date": "2025-01-01", "sales": 100},
            {"date": "2025-02-01", "sales": 200},
        ]
        result = self.recommender._infer_by_rules(columns, rows, "")
        types = [t for t, _ in result]
        assert "line" in types

    def test_recommend_text_numeric(self) -> None:
        """分类列 + 数值列应推荐 bar。"""
        columns = [
            {"name": "city", "type": "varchar"},
            {"name": "population", "type": "integer"},
        ]
        rows = [
            {"city": "北京", "population": 2100},
            {"city": "上海", "population": 2400},
        ]
        result = self.recommender._infer_by_rules(columns, rows, "")
        types = [t for t, _ in result]
        assert "bar" in types

    def test_recommend_few_categories(self) -> None:
        """少量分类应推荐 pie。"""
        columns = [
            {"name": "category", "type": "varchar"},
            {"name": "count", "type": "integer"},
        ]
        rows = [
            {"category": "A", "count": 30},
            {"category": "B", "count": 50},
            {"category": "C", "count": 20},
        ]
        result = self.recommender._infer_by_rules(columns, rows, "")
        types = [t for t, _ in result]
        assert "pie" in types

    def test_recommend_empty_data(self) -> None:
        """空数据应返回默认。"""
        result = self.recommender._infer_by_rules([], [], "")
        assert len(result) > 0

    def test_question_keyword_boost(self) -> None:
        """用户问题关键词应提升对应图表类型。"""
        columns = [
            {"name": "month", "type": "varchar"},
            {"name": "sales", "type": "integer"},
        ]
        rows = [
            {"month": "1月", "sales": 100},
            {"month": "2月", "sales": 200},
        ]
        result = self.recommender._infer_by_rules(columns, rows, "展示销售额趋势")
        types = [t for t, _ in result]
        assert "line" in types

    def test_detect_fields(self) -> None:
        """自动检测字段映射。"""
        columns = [
            {"name": "date", "type": "date"},
            {"name": "sales", "type": "integer"},
            {"name": "profit", "type": "integer"},
        ]
        rows = [
            {"date": "2025-01-01", "sales": 100, "profit": 30},
            {"date": "2025-02-01", "sales": 200, "profit": 50},
        ]
        x_field, y_fields = self.recommender._detect_fields(columns, rows)
        assert x_field == "date"
        assert "sales" in y_fields
        assert "profit" in y_fields


class TestChartRecommendation:
    """ChartRecommendation 数据模型测试。"""

    def test_creation(self) -> None:
        rec = ChartRecommendation(
            chart_types=[("bar", 0.8), ("line", 0.5)],
            title="销售对比图",
            description="展示各城市销售额",
            x_field="city",
            y_fields=["sales"],
        )
        assert rec.title == "销售对比图"
        assert len(rec.chart_types) == 2
        assert rec.chart_types[0] == ("bar", 0.8)

    def test_default_suggested_config(self) -> None:
        rec = ChartRecommendation(
            chart_types=[("table", 1.0)],
            title="数据表格",
            description="明细数据",
            x_field="",
            y_fields=[],
        )
        assert rec.suggested_config is None
