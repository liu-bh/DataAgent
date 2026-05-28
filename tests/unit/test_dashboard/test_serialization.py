"""Dashboard 序列化测试。

覆盖 JSON 序列化/反序列化往返、dict 序列化/反序列化、
空面板列表处理。
"""

from __future__ import annotations

import json

import pytest

from datapilot_chart.dashboard.models import (
    DashboardFilterDef,
    DashboardLayout,
    DashboardPanel,
    PanelType,
)
from datapilot_chart.dashboard.serialization import DashboardSerializer


@pytest.fixture
def serializer() -> DashboardSerializer:
    """创建序列化器实例。"""
    return DashboardSerializer()


@pytest.fixture
def sample_layout() -> DashboardLayout:
    """创建测试 Dashboard 布局。"""
    return DashboardLayout(
        dashboard_id="d1",
        title="测试仪表板",
        description="序列化测试",
        panels=[
            DashboardPanel(
                panel_id="p1",
                title="柱状图",
                panel_type=PanelType.CHART,
                width=8,
                height=400,
                chart_spec={"chart_type": "bar", "data": [1, 2, 3]},
                position={"row": 0, "col": 0},
            ),
            DashboardPanel(
                panel_id="p2",
                title="总收入",
                panel_type=PanelType.METRIC,
                width=4,
                height=200,
                metric_config={"metric": 12345, "label": "元", "unit": "CNY", "trend": "up"},
                position={"row": 0, "col": 8},
            ),
        ],
        filters=[
            DashboardFilterDef(
                filter_id="f1",
                field="region",
                label="地区",
                filter_type="select",
                options=["北京", "上海", "广州"],
                default_value="北京",
            ),
        ],
        created_at="2024-01-01",
        updated_at="2024-06-01",
    )


class TestJsonSerialization:
    """JSON 序列化/反序列化测试。"""

    def test_to_json_returns_string(self, serializer: DashboardSerializer, sample_layout: DashboardLayout) -> None:
        """to_json 应返回字符串。"""
        result = serializer.to_json(sample_layout)
        assert isinstance(result, str)

    def test_to_json_valid_json(self, serializer: DashboardSerializer, sample_layout: DashboardLayout) -> None:
        """to_json 应返回合法 JSON。"""
        result = serializer.to_json(sample_layout)
        parsed = json.loads(result)
        assert parsed["dashboard_id"] == "d1"
        assert parsed["title"] == "测试仪表板"

    def test_json_roundtrip(self, serializer: DashboardSerializer, sample_layout: DashboardLayout) -> None:
        """JSON 序列化/反序列化往返应保持一致。"""
        json_str = serializer.to_json(sample_layout)
        restored = serializer.from_json(json_str)
        assert restored == sample_layout

    def test_json_preserves_chinese(self, serializer: DashboardSerializer, sample_layout: DashboardLayout) -> None:
        """JSON 序列化应保留中文字符。"""
        json_str = serializer.to_json(sample_layout)
        assert "测试仪表板" in json_str
        assert "柱状图" in json_str

    def test_json_preserves_all_fields(self, serializer: DashboardSerializer, sample_layout: DashboardLayout) -> None:
        """JSON 应保留所有字段。"""
        json_str = serializer.to_json(sample_layout)
        parsed = json.loads(json_str)
        assert len(parsed["panels"]) == 2
        assert len(parsed["filters"]) == 1
        assert parsed["panels"][0]["chart_spec"]["chart_type"] == "bar"
        assert parsed["panels"][1]["metric_config"]["metric"] == 12345
        assert parsed["filters"][0]["options"] == ["北京", "上海", "广州"]


class TestDictSerialization:
    """dict 序列化/反序列化测试。"""

    def test_to_dict(self, serializer: DashboardSerializer, sample_layout: DashboardLayout) -> None:
        """to_dict 应返回字典。"""
        result = serializer.to_dict(sample_layout)
        assert isinstance(result, dict)
        assert result["dashboard_id"] == "d1"

    def test_from_dict(self, serializer: DashboardSerializer) -> None:
        """from_dict 应正确反序列化。"""
        data = {
            "dashboard_id": "d2",
            "title": "新仪表板",
            "description": "描述",
            "panels": [
                {
                    "panel_id": "p1",
                    "title": "图1",
                    "panel_type": "chart",
                    "width": 12,
                }
            ],
            "filters": [],
            "columns": 12,
            "created_at": "",
            "updated_at": "",
        }
        layout = serializer.from_dict(data)
        assert layout.dashboard_id == "d2"
        assert layout.title == "新仪表板"
        assert len(layout.panels) == 1

    def test_dict_roundtrip(self, serializer: DashboardSerializer, sample_layout: DashboardLayout) -> None:
        """dict 序列化/反序列化往返应保持一致。"""
        d = serializer.to_dict(sample_layout)
        restored = serializer.from_dict(d)
        assert restored == sample_layout


class TestEmptyLayoutSerialization:
    """空布局序列化测试。"""

    def test_empty_layout_to_json(self, serializer: DashboardSerializer) -> None:
        """空布局 JSON 序列化。"""
        layout = DashboardLayout(dashboard_id="empty", title="空")
        json_str = serializer.to_json(layout)
        restored = serializer.from_json(json_str)
        assert restored == layout

    def test_empty_layout_to_dict(self, serializer: DashboardSerializer) -> None:
        """空布局 dict 序列化。"""
        layout = DashboardLayout(dashboard_id="empty", title="空")
        d = serializer.to_dict(layout)
        assert d["panels"] == []
        assert d["filters"] == []

    def test_empty_panels_json_roundtrip(self, serializer: DashboardSerializer) -> None:
        """空面板列表 JSON 往返。"""
        layout = DashboardLayout(
            dashboard_id="d1",
            title="无面板",
            filters=[
                DashboardFilterDef(filter_id="f1", field="x", label="X"),
            ],
        )
        json_str = serializer.to_json(layout)
        restored = serializer.from_json(json_str)
        assert len(restored.panels) == 0
        assert len(restored.filters) == 1
