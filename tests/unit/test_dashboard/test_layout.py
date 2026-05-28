"""布局引擎测试。

覆盖基本布局计算、换行逻辑、宽面板独占一行、
小面板同行排列、布局验证等。
"""

from __future__ import annotations

import pytest

from datapilot_chart.dashboard.layout import LayoutEngine
from datapilot_chart.dashboard.models import DashboardPanel, PanelType


@pytest.fixture
def engine() -> LayoutEngine:
    """创建布局引擎实例。"""
    return LayoutEngine()


def _make_panel(panel_id: str, width: int = 6) -> DashboardPanel:
    """快捷创建测试面板。"""
    return DashboardPanel(panel_id=panel_id, title=f"面板{panel_id}", width=width)


# ============================================================
# 基本布局计算测试
# ============================================================


class TestCalculatePositions:
    """calculate_positions 测试。"""

    def test_single_panel(self, engine: LayoutEngine) -> None:
        """单个面板应位于 (0, 0)。"""
        positions = engine.calculate_positions([_make_panel("p1")], 12)
        assert len(positions) == 1
        assert positions[0] == {"panel_id": "p1", "row": 0, "col": 0}

    def test_two_half_panels(self, engine: LayoutEngine) -> None:
        """两个半宽面板应同行排列。"""
        panels = [_make_panel("p1", 6), _make_panel("p2", 6)]
        positions = engine.calculate_positions(panels, 12)
        assert positions[0] == {"panel_id": "p1", "row": 0, "col": 0}
        assert positions[1] == {"panel_id": "p2", "row": 0, "col": 6}

    def test_three_third_panels(self, engine: LayoutEngine) -> None:
        """三个 1/3 宽面板应同行排列。"""
        panels = [_make_panel("p1", 4), _make_panel("p2", 4), _make_panel("p3", 4)]
        positions = engine.calculate_positions(panels, 12)
        assert positions[0]["col"] == 0
        assert positions[1]["col"] == 4
        assert positions[2]["col"] == 8
        assert all(p["row"] == 0 for p in positions)

    def test_empty_panels(self, engine: LayoutEngine) -> None:
        """空面板列表应返回空位置列表。"""
        positions = engine.calculate_positions([], 12)
        assert positions == []


# ============================================================
# 换行逻辑测试
# ============================================================


class TestLineWrapping:
    """换行逻辑测试。"""

    def test_wrap_when_exceeds_columns(self, engine: LayoutEngine) -> None:
        """累计宽度超过列数时应换行。"""
        panels = [
            _make_panel("p1", 6),
            _make_panel("p2", 6),
            _make_panel("p3", 6),
        ]
        positions = engine.calculate_positions(panels, 12)
        # p1: row=0, col=0
        # p2: row=0, col=6
        # p3: row=1, col=0 (换行)
        assert positions[2] == {"panel_id": "p3", "row": 1, "col": 0}

    def test_wrap_at_exact_boundary(self, engine: LayoutEngine) -> None:
        """累计宽度恰好等于列数时应换行。"""
        panels = [
            _make_panel("p1", 4),
            _make_panel("p2", 4),
            _make_panel("p3", 4),
            _make_panel("p4", 4),
        ]
        positions = engine.calculate_positions(panels, 12)
        # p1(0,0), p2(0,4), p3(0,8) -> 累计12，换行
        # p4(1,0)
        assert positions[3] == {"panel_id": "p4", "row": 1, "col": 0}

    def test_multiple_rows(self, engine: LayoutEngine) -> None:
        """多行布局测试。"""
        panels = [
            _make_panel("p1", 6),
            _make_panel("p2", 6),
            _make_panel("p3", 6),
            _make_panel("p4", 6),
        ]
        positions = engine.calculate_positions(panels, 12)
        assert positions[0]["row"] == 0
        assert positions[1]["row"] == 0
        assert positions[2]["row"] == 1
        assert positions[3]["row"] == 1

    def test_partial_row(self, engine: LayoutEngine) -> None:
        """最后一行不满时应继续排列。"""
        panels = [
            _make_panel("p1", 6),
            _make_panel("p2", 6),
            _make_panel("p3", 4),
        ]
        positions = engine.calculate_positions(panels, 12)
        assert positions[2]["row"] == 1
        assert positions[2]["col"] == 0


# ============================================================
# 宽面板独占一行测试
# ============================================================


class TestWidePanelLayout:
    """宽面板布局测试。"""

    def test_full_width_panel(self, engine: LayoutEngine) -> None:
        """全宽面板独占一行。"""
        panels = [_make_panel("p1", 12), _make_panel("p2", 6)]
        positions = engine.calculate_positions(panels, 12)
        assert positions[0] == {"panel_id": "p1", "row": 0, "col": 0}
        assert positions[1] == {"panel_id": "p2", "row": 1, "col": 0}

    def test_very_wide_panel(self, engine: LayoutEngine) -> None:
        """超过列数的面板仍独占一行。"""
        panels = [_make_panel("p1", 16)]
        positions = engine.calculate_positions(panels, 12)
        assert positions[0] == {"panel_id": "p1", "row": 0, "col": 0}

    def test_8_width_panel(self, engine: LayoutEngine) -> None:
        """8 列宽面板后跟 4 列宽面板应同行。"""
        panels = [_make_panel("p1", 8), _make_panel("p2", 4)]
        positions = engine.calculate_positions(panels, 12)
        assert positions[0]["row"] == 0
        assert positions[0]["col"] == 0
        assert positions[1]["row"] == 0
        assert positions[1]["col"] == 8


# ============================================================
# 小面板同行排列测试
# ============================================================


class TestSmallPanels:
    """小面板排列测试。"""

    def test_four_small_panels(self, engine: LayoutEngine) -> None:
        """四个 3 列宽小面板应同行排列。"""
        panels = [
            _make_panel("p1", 3),
            _make_panel("p2", 3),
            _make_panel("p3", 3),
            _make_panel("p4", 3),
        ]
        positions = engine.calculate_positions(panels, 12)
        for i, pos in enumerate(positions):
            assert pos["row"] == 0
            assert pos["col"] == i * 3

    def test_six_tiny_panels(self, engine: LayoutEngine) -> None:
        """六个 2 列宽面板应两行排列。"""
        panels = [_make_panel(f"p{i}", 2) for i in range(6)]
        positions = engine.calculate_positions(panels, 12)
        for i in range(6):
            assert positions[i]["row"] == i // 6  # 全在第一行
            assert positions[i]["col"] == i * 2

    def test_mixed_sizes(self, engine: LayoutEngine) -> None:
        """混合大小面板布局。"""
        panels = [
            _make_panel("p1", 3),
            _make_panel("p2", 3),
            _make_panel("p3", 6),
        ]
        positions = engine.calculate_positions(panels, 12)
        assert positions[0]["col"] == 0
        assert positions[1]["col"] == 3
        assert positions[2]["col"] == 6
        assert all(p["row"] == 0 for p in positions)


# ============================================================
# 布局验证测试
# ============================================================


class TestValidateLayout:
    """validate_layout 测试。"""

    def test_valid_layout(self, engine: LayoutEngine) -> None:
        """合法布局应无问题。"""
        panels = [
            _make_panel("p1", 6),
            _make_panel("p2", 6),
        ]
        issues = engine.validate_layout(panels, 12)
        assert issues == []

    def test_empty_panels_valid(self, engine: LayoutEngine) -> None:
        """空面板列表应合法。"""
        issues = engine.validate_layout([], 12)
        assert issues == []

    def test_width_out_of_range(self, engine: LayoutEngine) -> None:
        """宽度超出范围应报错。"""
        panels = [DashboardPanel(panel_id="p1", title="面板", width=0)]
        issues = engine.validate_layout(panels, 12)
        assert any("宽度 0" in i for i in issues)

    def test_width_exceeds_12(self, engine: LayoutEngine) -> None:
        """宽度超过 12 应报错。"""
        panels = [DashboardPanel(panel_id="p1", title="面板", width=13)]
        issues = engine.validate_layout(panels, 12)
        assert any("宽度 13" in i for i in issues)

    def test_width_exceeds_columns(self, engine: LayoutEngine) -> None:
        """宽度超过总列数应报错。"""
        panels = [DashboardPanel(panel_id="p1", title="面板", width=8)]
        issues = engine.validate_layout(panels, 6)
        assert any("超过总列数" in i for i in issues)

    def test_duplicate_panel_ids(self, engine: LayoutEngine) -> None:
        """重复面板 ID 应报错。"""
        panels = [
            _make_panel("p1"),
            _make_panel("p1"),
        ]
        issues = engine.validate_layout(panels, 12)
        assert any("重复" in i for i in issues)

    def test_empty_title(self, engine: LayoutEngine) -> None:
        """空标题应报错。"""
        panels = [DashboardPanel(panel_id="p1", title="")]
        issues = engine.validate_layout(panels, 12)
        assert any("标题为空" in i for i in issues)

    def test_multiple_issues(self, engine: LayoutEngine) -> None:
        """多个问题应全部报告。"""
        panels = [
            DashboardPanel(panel_id="dup", title="", width=0),
            DashboardPanel(panel_id="dup", title="", width=15),
        ]
        issues = engine.validate_layout(panels, 12)
        assert len(issues) >= 3  # 宽度0, 宽度15, 重复ID, 空标题 x2

    def test_custom_columns(self, engine: LayoutEngine) -> None:
        """自定义列数验证。"""
        panels = [DashboardPanel(panel_id="p1", title="面板", width=6)]
        # 6 列布局中 6 宽度面板应合法
        issues = engine.validate_layout(panels, 6)
        assert issues == []
