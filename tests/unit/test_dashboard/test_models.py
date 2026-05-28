"""Dashboard 数据模型测试。

覆盖 PanelType 枚举、DashboardPanel、DashboardFilterDef、DashboardLayout 的
构造、默认值和序列化往返。
"""

from __future__ import annotations

import pytest

from datapilot_chart.dashboard.models import (
    DashboardFilterDef,
    DashboardLayout,
    DashboardPanel,
    PanelType,
)


# ============================================================
# PanelType 枚举测试
# ============================================================


class TestPanelType:
    """PanelType 枚举测试。"""

    def test_chart_value(self) -> None:
        """CHART 类型的值应为 'chart'。"""
        assert PanelType.CHART == "chart"

    def test_table_value(self) -> None:
        """TABLE 类型的值应为 'table'。"""
        assert PanelType.TABLE == "table"

    def test_metric_value(self) -> None:
        """METRIC 类型的值应为 'metric'。"""
        assert PanelType.METRIC == "metric"

    def test_text_value(self) -> None:
        """TEXT 类型的值应为 'text'。"""
        assert PanelType.TEXT == "text"

    def test_enum_members_count(self) -> None:
        """枚举成员数量应为 4。"""
        assert len(PanelType) == 4

    def test_from_string(self) -> None:
        """可以通过字符串构造枚举。"""
        assert PanelType("chart") is PanelType.CHART
        assert PanelType("table") is PanelType.TABLE

    def test_invalid_string_raises(self) -> None:
        """无效字符串应抛出 ValueError。"""
        with pytest.raises(ValueError):
            PanelType("invalid")


# ============================================================
# DashboardPanel 测试
# ============================================================


class TestDashboardPanel:
    """DashboardPanel 数据模型测试。"""

    def test_default_values(self) -> None:
        """默认值应正确设置。"""
        panel = DashboardPanel(panel_id="p1", title="测试面板")
        assert panel.panel_id == "p1"
        assert panel.title == "测试面板"
        assert panel.panel_type == PanelType.CHART
        assert panel.width == 6
        assert panel.height == 400
        assert panel.chart_spec is None
        assert panel.metric_config is None
        assert panel.content == ""
        assert panel.position == {}

    def test_custom_chart_panel(self) -> None:
        """自定义图表面板。"""
        spec = {"chart_type": "bar", "data": [1, 2, 3]}
        panel = DashboardPanel(
            panel_id="p2",
            title="柱状图",
            panel_type=PanelType.CHART,
            width=8,
            height=300,
            chart_spec=spec,
        )
        assert panel.panel_type == PanelType.CHART
        assert panel.width == 8
        assert panel.height == 300
        assert panel.chart_spec == spec

    def test_metric_panel(self) -> None:
        """指标卡片面板。"""
        config = {"metric": 1234, "label": "总收入", "unit": "元", "trend": "up"}
        panel = DashboardPanel(
            panel_id="p3",
            title="总收入指标",
            panel_type=PanelType.METRIC,
            metric_config=config,
        )
        assert panel.panel_type == PanelType.METRIC
        assert panel.metric_config == config

    def test_text_panel(self) -> None:
        """文本面板。"""
        panel = DashboardPanel(
            panel_id="p4",
            title="说明",
            panel_type=PanelType.TEXT,
            content="这是一段说明文字",
        )
        assert panel.panel_type == PanelType.TEXT
        assert panel.content == "这是一段说明文字"

    def test_table_panel(self) -> None:
        """表格面板。"""
        panel = DashboardPanel(
            panel_id="p5",
            title="数据表格",
            panel_type=PanelType.TABLE,
            width=12,
        )
        assert panel.panel_type == PanelType.TABLE
        assert panel.width == 12

    def test_panel_to_dict(self) -> None:
        """to_dict 应正确序列化。"""
        panel = DashboardPanel(
            panel_id="p1",
            title="测试",
            panel_type=PanelType.METRIC,
            position={"row": 0, "col": 0},
        )
        d = panel.to_dict()
        assert d["panel_id"] == "p1"
        assert d["title"] == "测试"
        assert d["panel_type"] == "metric"
        assert d["width"] == 6
        assert d["height"] == 400
        assert d["position"] == {"row": 0, "col": 0}

    def test_panel_from_dict(self) -> None:
        """from_dict 应正确反序列化。"""
        d = {
            "panel_id": "p1",
            "title": "测试",
            "panel_type": "metric",
            "width": 4,
            "height": 200,
            "position": {"row": 1, "col": 2},
        }
        panel = DashboardPanel.from_dict(d)
        assert panel.panel_id == "p1"
        assert panel.title == "测试"
        assert panel.panel_type == PanelType.METRIC
        assert panel.width == 4
        assert panel.height == 200
        assert panel.position == {"row": 1, "col": 2}

    def test_panel_roundtrip(self) -> None:
        """to_dict -> from_dict 往返应保持一致。"""
        original = DashboardPanel(
            panel_id="p_x",
            title="往返测试",
            panel_type=PanelType.TABLE,
            width=10,
            height=500,
            chart_spec={"type": "line"},
            metric_config={"metric": 42},
            content="内容",
            position={"row": 3, "col": 0},
        )
        restored = DashboardPanel.from_dict(original.to_dict())
        assert restored == original


# ============================================================
# DashboardFilterDef 测试
# ============================================================


class TestDashboardFilterDef:
    """DashboardFilterDef 数据模型测试。"""

    def test_default_values(self) -> None:
        """默认值应正确设置。"""
        fd = DashboardFilterDef(
            filter_id="f1",
            field="region",
            label="地区",
        )
        assert fd.filter_id == "f1"
        assert fd.field == "region"
        assert fd.label == "地区"
        assert fd.filter_type == "select"
        assert fd.options == []
        assert fd.default_value is None

    def test_custom_filter_def(self) -> None:
        """自定义过滤器定义。"""
        fd = DashboardFilterDef(
            filter_id="f2",
            field="date",
            label="日期",
            filter_type="time_range",
            default_value="2024-01",
        )
        assert fd.filter_type == "time_range"
        assert fd.default_value == "2024-01"

    def test_multi_select_filter_def(self) -> None:
        """多选过滤器定义。"""
        fd = DashboardFilterDef(
            filter_id="f3",
            field="status",
            label="状态",
            filter_type="multi_select",
            options=["active", "inactive", "pending"],
            default_value=["active"],
        )
        assert fd.filter_type == "multi_select"
        assert len(fd.options) == 3
        assert fd.default_value == ["active"]

    def test_filter_def_to_dict(self) -> None:
        """to_dict 应正确序列化。"""
        fd = DashboardFilterDef(
            filter_id="f1",
            field="type",
            label="类型",
            filter_type="select",
            options=["a", "b"],
        )
        d = fd.to_dict()
        assert d["filter_id"] == "f1"
        assert d["field"] == "type"
        assert d["options"] == ["a", "b"]

    def test_filter_def_from_dict(self) -> None:
        """from_dict 应正确反序列化。"""
        d = {
            "filter_id": "f1",
            "field": "type",
            "label": "类型",
            "filter_type": "multi_select",
            "options": ["x", "y"],
            "default_value": ["x"],
        }
        fd = DashboardFilterDef.from_dict(d)
        assert fd.filter_type == "multi_select"
        assert fd.options == ["x", "y"]
        assert fd.default_value == ["x"]


# ============================================================
# DashboardLayout 测试
# ============================================================


class TestDashboardLayout:
    """DashboardLayout 数据模型测试。"""

    def test_minimal_layout(self) -> None:
        """最小布局构造。"""
        layout = DashboardLayout(
            dashboard_id="d1",
            title="测试仪表板",
        )
        assert layout.dashboard_id == "d1"
        assert layout.title == "测试仪表板"
        assert layout.description == ""
        assert layout.panels == []
        assert layout.filters == []
        assert layout.columns == 12
        assert layout.created_at == ""
        assert layout.updated_at == ""

    def test_full_layout(self) -> None:
        """完整布局构造。"""
        panels = [
            DashboardPanel(panel_id="p1", title="图表1"),
            DashboardPanel(panel_id="p2", title="指标1", panel_type=PanelType.METRIC),
        ]
        filters = [
            DashboardFilterDef(filter_id="f1", field="region", label="地区"),
        ]
        layout = DashboardLayout(
            dashboard_id="d1",
            title="完整仪表板",
            description="包含面板和过滤器",
            panels=panels,
            filters=filters,
            columns=12,
            created_at="2024-01-01",
            updated_at="2024-01-02",
        )
        assert len(layout.panels) == 2
        assert len(layout.filters) == 1
        assert layout.description == "包含面板和过滤器"
        assert layout.created_at == "2024-01-01"

    def test_layout_to_dict(self) -> None:
        """to_dict 应正确序列化。"""
        layout = DashboardLayout(
            dashboard_id="d1",
            title="测试",
            panels=[DashboardPanel(panel_id="p1", title="图1")],
        )
        d = layout.to_dict()
        assert d["dashboard_id"] == "d1"
        assert d["title"] == "测试"
        assert len(d["panels"]) == 1
        assert d["panels"][0]["panel_type"] == "chart"
        assert d["filters"] == []
        assert d["columns"] == 12

    def test_layout_from_dict(self) -> None:
        """from_dict 应正确反序列化。"""
        data = {
            "dashboard_id": "d1",
            "title": "测试",
            "description": "描述",
            "panels": [
                {
                    "panel_id": "p1",
                    "title": "图1",
                    "panel_type": "table",
                }
            ],
            "filters": [
                {
                    "filter_id": "f1",
                    "field": "region",
                    "label": "地区",
                }
            ],
            "columns": 12,
            "created_at": "2024-06-01",
            "updated_at": "2024-06-02",
        }
        layout = DashboardLayout.from_dict(data)
        assert layout.dashboard_id == "d1"
        assert layout.title == "测试"
        assert layout.description == "描述"
        assert len(layout.panels) == 1
        assert layout.panels[0].panel_type == PanelType.TABLE
        assert len(layout.filters) == 1
        assert layout.columns == 12
        assert layout.created_at == "2024-06-01"

    def test_layout_roundtrip(self) -> None:
        """to_dict -> from_dict 往返应保持一致。"""
        original = DashboardLayout(
            dashboard_id="d_full",
            title="完整仪表板",
            description="测试往返",
            panels=[
                DashboardPanel(
                    panel_id="p1",
                    title="图表",
                    chart_spec={"type": "bar"},
                    position={"row": 0, "col": 0},
                ),
                DashboardPanel(
                    panel_id="p2",
                    title="指标",
                    panel_type=PanelType.METRIC,
                    metric_config={"metric": 100},
                    position={"row": 1, "col": 0},
                ),
            ],
            filters=[
                DashboardFilterDef(
                    filter_id="f1",
                    field="region",
                    label="地区",
                    options=["北京", "上海"],
                    default_value="北京",
                ),
            ],
            created_at="2024-01-01",
            updated_at="2024-12-31",
        )
        restored = DashboardLayout.from_dict(original.to_dict())
        assert restored == original

    def test_layout_empty_panels_serialization(self) -> None:
        """空面板列表序列化。"""
        layout = DashboardLayout(dashboard_id="d1", title="空仪表板")
        d = layout.to_dict()
        assert d["panels"] == []
        assert d["filters"] == []

    def test_layout_custom_columns(self) -> None:
        """自定义列数。"""
        layout = DashboardLayout(
            dashboard_id="d1",
            title="测试",
            columns=24,
        )
        assert layout.columns == 24
