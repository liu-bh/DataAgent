"""Dashboard 引擎单元测试。"""

from __future__ import annotations

import json

from datapilot_chart.dashboard.models import (
    DashboardFilterDef,
    DashboardLayout,
    DashboardPanel,
    PanelType,
)
from datapilot_chart.dashboard.builder import DashboardBuilder
from datapilot_chart.dashboard.layout import LayoutEngine
from datapilot_chart.dashboard.filter import DashboardFilter
from datapilot_chart.dashboard.serialization import DashboardSerializer


class TestPanelType:
    """PanelType 枚举测试。"""

    def test_chart(self) -> None:
        assert PanelType.CHART == "chart"

    def test_table(self) -> None:
        assert PanelType.TABLE == "table"

    def test_metric(self) -> None:
        assert PanelType.METRIC == "metric"

    def test_text(self) -> None:
        assert PanelType.TEXT == "text"


class TestDashboardPanel:
    """DashboardPanel 测试。"""

    def test_default_values(self) -> None:
        panel = DashboardPanel(panel_id="p1", title="测试面板")
        assert panel.panel_type == PanelType.CHART
        assert panel.width == 6
        assert panel.height == 400
        assert panel.position == {}

    def test_to_dict(self) -> None:
        panel = DashboardPanel(panel_id="p1", title="销售图")
        d = panel.to_dict()
        assert d["panel_id"] == "p1"
        assert d["title"] == "销售图"
        assert d["panel_type"] == "chart"

    def test_from_dict(self) -> None:
        data = {
            "panel_id": "p2",
            "title": "利润图",
            "panel_type": "metric",
            "width": 4,
            "height": 200,
        }
        panel = DashboardPanel.from_dict(data)
        assert panel.panel_id == "p2"
        assert panel.panel_type == PanelType.METRIC
        assert panel.width == 4


class TestDashboardFilterDef:
    """DashboardFilterDef 测试。"""

    def test_default_values(self) -> None:
        f = DashboardFilterDef(filter_id="f1", field="city", label="城市")
        assert f.filter_type == "select"
        assert f.options == []
        assert f.default_value is None

    def test_to_dict(self) -> None:
        f = DashboardFilterDef(
            filter_id="f1",
            field="city",
            label="城市",
            filter_type="multi_select",
            options=["北京", "上海"],
        )
        d = f.to_dict()
        assert d["filter_id"] == "f1"
        assert d["options"] == ["北京", "上海"]

    def test_from_dict(self) -> None:
        data = {
            "filter_id": "f1",
            "field": "city",
            "label": "城市",
            "filter_type": "select",
            "options": ["北京", "上海"],
        }
        f = DashboardFilterDef.from_dict(data)
        assert f.field == "city"
        assert f.filter_type == "select"


class TestDashboardLayout:
    """DashboardLayout 测试。"""

    def test_default_values(self) -> None:
        layout = DashboardLayout(dashboard_id="d1", title="测试仪表板")
        assert layout.description == ""
        assert layout.panels == []
        assert layout.filters == []
        assert layout.columns == 12

    def test_to_dict_roundtrip(self) -> None:
        layout = DashboardLayout(
            dashboard_id="d1",
            title="销售仪表板",
            description="展示销售数据",
            panels=[
                DashboardPanel(panel_id="p1", title="销售额"),
            ],
            filters=[
                DashboardFilterDef(
                    filter_id="f1", field="city", label="城市"
                ),
            ],
        )
        d = layout.to_dict()
        assert d["dashboard_id"] == "d1"
        assert len(d["panels"]) == 1
        assert len(d["filters"]) == 1

        restored = DashboardLayout.from_dict(d)
        assert restored.dashboard_id == "d1"
        assert restored.title == "销售仪表板"
        assert len(restored.panels) == 1
        assert restored.panels[0].panel_id == "p1"


class TestLayoutEngine:
    """LayoutEngine 测试。"""

    def setup_method(self) -> None:
        self.engine = LayoutEngine()

    def test_calculate_positions_single_row(self) -> None:
        panels = [
            DashboardPanel(panel_id="p1", title="A", width=6),
            DashboardPanel(panel_id="p2", title="B", width=6),
        ]
        positions = self.engine.calculate_positions(panels, columns=12)
        assert len(positions) == 2
        assert positions[0] == {"panel_id": "p1", "row": 0, "col": 0}
        assert positions[1] == {"panel_id": "p2", "row": 0, "col": 6}

    def test_calculate_positions_wrap(self) -> None:
        panels = [
            DashboardPanel(panel_id="p1", title="A", width=6),
            DashboardPanel(panel_id="p2", title="B", width=6),
            DashboardPanel(panel_id="p3", title="C", width=6),
        ]
        positions = self.engine.calculate_positions(panels, columns=12)
        assert positions[2]["row"] == 1
        assert positions[2]["col"] == 0

    def test_calculate_positions_empty(self) -> None:
        positions = self.engine.calculate_positions([], columns=12)
        assert positions == []

    def test_validate_layout_valid(self) -> None:
        panels = [
            DashboardPanel(panel_id="p1", title="A", width=6),
            DashboardPanel(panel_id="p2", title="B", width=6),
        ]
        issues = self.engine.validate_layout(panels, 12)
        assert issues == []

    def test_validate_layout_invalid_width(self) -> None:
        panels = [
            DashboardPanel(panel_id="p1", title="A", width=15),
        ]
        issues = self.engine.validate_layout(panels, 12)
        assert len(issues) >= 1
        assert "宽度" in issues[0]

    def test_validate_layout_duplicate_id(self) -> None:
        panels = [
            DashboardPanel(panel_id="p1", title="A", width=6),
            DashboardPanel(panel_id="p1", title="B", width=6),
        ]
        issues = self.engine.validate_layout(panels, 12)
        assert any("重复" in i for i in issues)

    def test_validate_layout_empty_title(self) -> None:
        panels = [
            DashboardPanel(panel_id="p1", title="", width=6),
        ]
        issues = self.engine.validate_layout(panels, 12)
        assert any("标题" in i for i in issues)


class TestDashboardFilter:
    """DashboardFilter 测试。"""

    def setup_method(self) -> None:
        self.filter = DashboardFilter()

    def test_apply_no_filters(self) -> None:
        data = [{"city": "北京"}, {"city": "上海"}]
        result = self.filter.apply(data, {})
        assert len(result) == 2

    def test_apply_select_filter(self) -> None:
        data = [{"city": "北京", "sales": 100}, {"city": "上海", "sales": 200}]
        filter_defs = [
            DashboardFilterDef(
                filter_id="city_filter", field="city", label="城市"
            )
        ]
        result = self.filter.apply(
            data, {"city_filter": "北京"}, filter_defs
        )
        assert len(result) == 1
        assert result[0]["city"] == "北京"

    def test_apply_multi_select_filter(self) -> None:
        data = [
            {"city": "北京", "sales": 100},
            {"city": "上海", "sales": 200},
            {"city": "广州", "sales": 150},
        ]
        filter_defs = [
            DashboardFilterDef(
                filter_id="city_filter",
                field="city",
                label="城市",
                filter_type="multi_select",
            )
        ]
        result = self.filter.apply(
            data, {"city_filter": ["北京", "上海"]}, filter_defs
        )
        assert len(result) == 2

    def test_validate_valid(self) -> None:
        filter_defs = [
            DashboardFilterDef(
                filter_id="f1",
                field="city",
                label="城市",
                options=["北京", "上海"],
            )
        ]
        issues = self.filter.validate({"f1": "北京"}, filter_defs)
        assert issues == []

    def test_validate_unknown_filter(self) -> None:
        filter_defs = [
            DashboardFilterDef(filter_id="f1", field="city", label="城市")
        ]
        issues = self.filter.validate({"f99": "北京"}, filter_defs)
        assert any("未知" in i for i in issues)

    def test_validate_invalid_option(self) -> None:
        filter_defs = [
            DashboardFilterDef(
                filter_id="f1",
                field="city",
                label="城市",
                options=["北京", "上海"],
            )
        ]
        issues = self.filter.validate({"f1": "广州"}, filter_defs)
        assert any("不在可选项" in i for i in issues)


class TestDashboardSerializer:
    """DashboardSerializer 测试。"""

    def setup_method(self) -> None:
        self.serializer = DashboardSerializer()

    def test_to_json_and_back(self) -> None:
        layout = DashboardLayout(
            dashboard_id="d1",
            title="测试",
            panels=[
                DashboardPanel(panel_id="p1", title="面板1"),
            ],
        )
        json_str = self.serializer.to_json(layout)
        assert isinstance(json_str, str)

        restored = self.serializer.from_json(json_str)
        assert restored.dashboard_id == "d1"
        assert restored.title == "测试"
        assert len(restored.panels) == 1
        assert restored.panels[0].panel_id == "p1"

    def test_to_dict_and_back(self) -> None:
        layout = DashboardLayout(
            dashboard_id="d2",
            title="测试2",
            description="描述",
        )
        d = self.serializer.to_dict(layout)
        assert d["dashboard_id"] == "d2"

        restored = self.serializer.from_dict(d)
        assert restored.title == "测试2"


class TestDashboardBuilder:
    """DashboardBuilder 测试。"""

    def setup_method(self) -> None:
        self.builder = DashboardBuilder()

    def test_build_from_charts(self) -> None:
        chart_specs = [
            {"title": "销售额柱状图", "chart_type": "bar"},
            {"title": "利润饼图", "chart_type": "pie"},
        ]
        layout = self.builder.build_from_charts(
            chart_specs, title="销售仪表板"
        )
        assert layout.title == "销售仪表板"
        assert len(layout.panels) == 2
        # 自动布局应该分配了位置
        assert layout.panels[0].position != {}

    def test_add_panel(self) -> None:
        layout = DashboardLayout(dashboard_id="d1", title="测试")
        panel = DashboardPanel(panel_id="p1", title="新面板")
        self.builder.add_panel(layout, panel)
        assert len(layout.panels) == 1

    def test_add_filter(self) -> None:
        layout = DashboardLayout(dashboard_id="d1", title="测试")
        filter_def = DashboardFilterDef(
            filter_id="f1", field="city", label="城市"
        )
        self.builder.add_filter(layout, filter_def)
        assert len(layout.filters) == 1

    def test_remove_panel(self) -> None:
        layout = DashboardLayout(
            dashboard_id="d1",
            title="测试",
            panels=[
                DashboardPanel(panel_id="p1", title="A"),
                DashboardPanel(panel_id="p2", title="B"),
            ],
        )
        result = self.builder.remove_panel(layout, "p1")
        assert result is True
        assert len(layout.panels) == 1
        assert layout.panels[0].panel_id == "p2"

    def test_remove_nonexistent_panel(self) -> None:
        layout = DashboardLayout(dashboard_id="d1", title="测试")
        result = self.builder.remove_panel(layout, "p99")
        assert result is False

    def test_reorder_panels(self) -> None:
        layout = DashboardLayout(
            dashboard_id="d1",
            title="测试",
            panels=[
                DashboardPanel(panel_id="p1", title="A", width=12),
                DashboardPanel(panel_id="p2", title="B", width=12),
                DashboardPanel(panel_id="p3", title="C", width=12),
            ],
        )
        self.builder.reorder_panels(layout, ["p3", "p1"])
        assert layout.panels[0].panel_id == "p3"
        assert layout.panels[1].panel_id == "p1"
        assert layout.panels[2].panel_id == "p2"
