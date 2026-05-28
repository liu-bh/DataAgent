"""Dashboard 构建器测试。

覆盖 build_from_charts、add_panel、remove_panel、add_filter、
auto_layout、reorder_panels 等。
"""

from __future__ import annotations

import pytest

from datapilot_chart.dashboard.builder import DashboardBuilder
from datapilot_chart.dashboard.models import (
    DashboardFilterDef,
    DashboardLayout,
    DashboardPanel,
    PanelType,
)


class TestBuildFromCharts:
    """build_from_charts 测试。"""

    def test_basic_build(self) -> None:
        """从图表列表构建基础 Dashboard。"""
        builder = DashboardBuilder()
        specs = [
            {"title": "柱状图", "chart_type": "bar"},
            {"title": "折线图", "chart_type": "line"},
        ]
        layout = builder.build_from_charts(specs, title="销售仪表板")

        assert layout.title == "销售仪表板"
        assert len(layout.panels) == 2
        assert all(p.panel_type == PanelType.CHART for p in layout.panels)

    def test_auto_layout_applied(self) -> None:
        """构建时应自动应用布局。"""
        builder = DashboardBuilder()
        specs = [
            {"title": "图1"},
            {"title": "图2"},
        ]
        layout = builder.build_from_charts(specs)
        # 自动布局后应有位置信息
        for panel in layout.panels:
            assert "row" in panel.position
            assert "col" in panel.position

    def test_empty_chart_list(self) -> None:
        """空图表列表应生成空面板 Dashboard。"""
        builder = DashboardBuilder()
        layout = builder.build_from_charts([])
        assert len(layout.panels) == 0

    def test_default_title(self) -> None:
        """未指定标题时应使用默认标题。"""
        builder = DashboardBuilder()
        layout = builder.build_from_charts([{"title": "图1"}])
        assert layout.title == "新建仪表板"

    def test_custom_title(self) -> None:
        """自定义标题应被保留。"""
        builder = DashboardBuilder()
        layout = builder.build_from_charts(
            [{"title": "图1"}], title="自定义标题"
        )
        assert layout.title == "自定义标题"

    def test_dashboard_id_generated(self) -> None:
        """应自动生成 dashboard_id。"""
        builder = DashboardBuilder()
        layout = builder.build_from_charts([{"title": "图1"}])
        assert layout.dashboard_id.startswith("dashboard-")

    def test_chart_titles_preserved(self) -> None:
        """图表标题应作为面板标题。"""
        builder = DashboardBuilder()
        specs = [{"title": "销售趋势"}, {"title": "收入分析"}]
        layout = builder.build_from_charts(specs)
        assert layout.panels[0].title == "销售趋势"
        assert layout.panels[1].title == "收入分析"

    def test_chart_spec_stored(self) -> None:
        """图表规范应存储在面板中。"""
        builder = DashboardBuilder()
        spec = {"title": "测试", "chart_type": "pie", "data": [10, 20]}
        layout = builder.build_from_charts([spec])
        assert layout.panels[0].chart_spec == spec


class TestAddPanel:
    """add_panel 测试。"""

    def test_add_panel(self) -> None:
        """添加面板到 Dashboard。"""
        builder = DashboardBuilder()
        layout = DashboardLayout(dashboard_id="d1", title="测试")
        panel = DashboardPanel(panel_id="p1", title="新面板")
        builder.add_panel(layout, panel)
        assert len(layout.panels) == 1
        assert layout.panels[0].panel_id == "p1"

    def test_add_multiple_panels(self) -> None:
        """添加多个面板。"""
        builder = DashboardBuilder()
        layout = DashboardLayout(dashboard_id="d1", title="测试")
        builder.add_panel(layout, DashboardPanel(panel_id="p1", title="面板1"))
        builder.add_panel(layout, DashboardPanel(panel_id="p2", title="面板2"))
        builder.add_panel(layout, DashboardPanel(panel_id="p3", title="面板3"))
        assert len(layout.panels) == 3

    def test_add_different_panel_types(self) -> None:
        """添加不同类型的面板。"""
        builder = DashboardBuilder()
        layout = DashboardLayout(dashboard_id="d1", title="测试")
        builder.add_panel(
            layout,
            DashboardPanel(panel_id="p1", title="图表", panel_type=PanelType.CHART),
        )
        builder.add_panel(
            layout,
            DashboardPanel(panel_id="p2", title="指标", panel_type=PanelType.METRIC),
        )
        builder.add_panel(
            layout,
            DashboardPanel(panel_id="p3", title="文本", panel_type=PanelType.TEXT),
        )
        assert layout.panels[0].panel_type == PanelType.CHART
        assert layout.panels[1].panel_type == PanelType.METRIC
        assert layout.panels[2].panel_type == PanelType.TEXT


class TestRemovePanel:
    """remove_panel 测试。"""

    def test_remove_existing_panel(self) -> None:
        """移除存在的面板。"""
        builder = DashboardBuilder()
        layout = DashboardLayout(
            dashboard_id="d1",
            title="测试",
            panels=[
                DashboardPanel(panel_id="p1", title="面板1"),
                DashboardPanel(panel_id="p2", title="面板2"),
            ],
        )
        result = builder.remove_panel(layout, "p1")
        assert result is True
        assert len(layout.panels) == 1
        assert layout.panels[0].panel_id == "p2"

    def test_remove_nonexistent_panel(self) -> None:
        """移除不存在的面板。"""
        builder = DashboardBuilder()
        layout = DashboardLayout(
            dashboard_id="d1",
            title="测试",
            panels=[DashboardPanel(panel_id="p1", title="面板1")],
        )
        result = builder.remove_panel(layout, "p999")
        assert result is False
        assert len(layout.panels) == 1

    def test_remove_recalculates_layout(self) -> None:
        """移除面板后应重新计算布局。"""
        builder = DashboardBuilder()
        layout = builder.build_from_charts(
            [{"title": "图1"}, {"title": "图2"}, {"title": "图3"}]
        )
        builder.remove_panel(layout, layout.panels[1].panel_id)
        # 剩余面板应有有效的位置
        for panel in layout.panels:
            assert "row" in panel.position


class TestAddFilter:
    """add_filter 测试。"""

    def test_add_filter(self) -> None:
        """添加过滤器。"""
        builder = DashboardBuilder()
        layout = DashboardLayout(dashboard_id="d1", title="测试")
        fd = DashboardFilterDef(
            filter_id="f1",
            field="region",
            label="地区",
        )
        builder.add_filter(layout, fd)
        assert len(layout.filters) == 1
        assert layout.filters[0].filter_id == "f1"

    def test_add_multiple_filters(self) -> None:
        """添加多个过滤器。"""
        builder = DashboardBuilder()
        layout = DashboardLayout(dashboard_id="d1", title="测试")
        builder.add_filter(
            layout,
            DashboardFilterDef(filter_id="f1", field="region", label="地区"),
        )
        builder.add_filter(
            layout,
            DashboardFilterDef(
                filter_id="f2", field="date", label="日期", filter_type="time_range"
            ),
        )
        assert len(layout.filters) == 2


class TestAutoLayout:
    """auto_layout 测试。"""

    def test_auto_layout_positions(self) -> None:
        """自动布局应计算位置。"""
        builder = DashboardBuilder()
        layout = DashboardLayout(
            dashboard_id="d1",
            title="测试",
            panels=[
                DashboardPanel(panel_id="p1", title="面板1", width=6),
                DashboardPanel(panel_id="p2", title="面板2", width=6),
            ],
        )
        builder.auto_layout(layout)
        assert layout.panels[0].position == {"row": 0, "col": 0}
        assert layout.panels[1].position == {"row": 0, "col": 6}

    def test_auto_layout_wraps(self) -> None:
        """自动布局应处理换行。"""
        builder = DashboardBuilder()
        layout = DashboardLayout(
            dashboard_id="d1",
            title="测试",
            panels=[
                DashboardPanel(panel_id="p1", title="面板1", width=6),
                DashboardPanel(panel_id="p2", title="面板2", width=6),
                DashboardPanel(panel_id="p3", title="面板3", width=6),
            ],
        )
        builder.auto_layout(layout)
        assert layout.panels[2].position == {"row": 1, "col": 0}


class TestReorderPanels:
    """reorder_panels 测试。"""

    def test_reorder_basic(self) -> None:
        """基本重新排序。"""
        builder = DashboardBuilder()
        layout = builder.build_from_charts(
            [{"title": "图1"}, {"title": "图2"}, {"title": "图3"}]
        )
        ids = [layout.panels[2].panel_id, layout.panels[0].panel_id, layout.panels[1].panel_id]
        builder.reorder_panels(layout, ids)
        assert layout.panels[0].panel_id == ids[0]
        assert layout.panels[1].panel_id == ids[1]
        assert layout.panels[2].panel_id == ids[2]

    def test_reorder_partial(self) -> None:
        """部分重新排序（未指定的面板追加到末尾）。"""
        builder = DashboardBuilder()
        layout = builder.build_from_charts(
            [{"title": "图1"}, {"title": "图2"}, {"title": "图3"}]
        )
        ids = [layout.panels[2].panel_id]
        builder.reorder_panels(layout, ids)
        assert layout.panels[0].panel_id == ids[0]
        assert len(layout.panels) == 3

    def test_reorder_recalculates_positions(self) -> None:
        """重新排序后应重新计算位置。"""
        builder = DashboardBuilder()
        layout = builder.build_from_charts(
            [{"title": "图1"}, {"title": "图2"}]
        )
        # 交换顺序
        ids = [layout.panels[1].panel_id, layout.panels[0].panel_id]
        builder.reorder_panels(layout, ids)
        # 第一个面板位置应在 (0, 0)
        assert layout.panels[0].position == {"row": 0, "col": 0}
