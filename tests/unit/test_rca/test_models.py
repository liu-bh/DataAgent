"""RCA 数据模型单元测试。"""
from __future__ import annotations

import pytest

from datapilot_agent.rca.models import (
    AnomalyResult,
    AttributionResult,
    DimensionValue,
    DrillDownResult,
    RCAReport,
)


# ==================================================================
# AnomalyResult
# ==================================================================


class TestAnomalyResult:
    """AnomalyResult 数据模型测试。"""

    def test_create_minimal(self) -> None:
        """最小化创建 AnomalyResult。"""
        result = AnomalyResult(
            metric_name="销售额",
            current_value=850000,
            baseline_value=1000000,
            change_percent=-15.0,
            is_anomaly=True,
            anomaly_type="drop",
            confidence=0.85,
        )
        assert result.metric_name == "销售额"
        assert result.current_value == 850000
        assert result.baseline_value == 1000000
        assert result.change_percent == -15.0
        assert result.is_anomaly is True
        assert result.anomaly_type == "drop"
        assert result.confidence == 0.85

    def test_default_direction(self) -> None:
        """默认方向为 neutral。"""
        result = AnomalyResult(
            metric_name="销售额",
            current_value=100,
            baseline_value=100,
            change_percent=0.0,
            is_anomaly=False,
            anomaly_type="none",
            confidence=0.0,
        )
        assert result.direction == "neutral"

    def test_direction_up(self) -> None:
        """direction 可设置为 up。"""
        result = AnomalyResult(
            metric_name="订单量",
            current_value=1500,
            baseline_value=1000,
            change_percent=50.0,
            is_anomaly=True,
            anomaly_type="spike",
            confidence=0.9,
            direction="up",
        )
        assert result.direction == "up"

    def test_direction_down(self) -> None:
        """direction 可设置为 down。"""
        result = AnomalyResult(
            metric_name="转化率",
            current_value=2.0,
            baseline_value=5.0,
            change_percent=-60.0,
            is_anomaly=True,
            anomaly_type="drop",
            confidence=0.95,
            direction="down",
        )
        assert result.direction == "down"

    def test_anomaly_type_none(self) -> None:
        """anomaly_type 可以是 none。"""
        result = AnomalyResult(
            metric_name="PV",
            current_value=1000,
            baseline_value=1010,
            change_percent=-1.0,
            is_anomaly=False,
            anomaly_type="none",
            confidence=0.1,
        )
        assert result.anomaly_type == "none"

    def test_confidence_range(self) -> None:
        """confidence 应在 0.0 ~ 1.0 范围内。"""
        result = AnomalyResult(
            metric_name="DAU",
            current_value=100,
            baseline_value=100,
            change_percent=0.0,
            is_anomaly=False,
            anomaly_type="none",
            confidence=0.0,
        )
        assert 0.0 <= result.confidence <= 1.0

        result2 = AnomalyResult(
            metric_name="DAU",
            current_value=200,
            baseline_value=100,
            change_percent=100.0,
            is_anomaly=True,
            anomaly_type="spike",
            confidence=1.0,
        )
        assert 0.0 <= result2.confidence <= 1.0


# ==================================================================
# DimensionValue
# ==================================================================


class TestDimensionValue:
    """DimensionValue 数据模型测试。"""

    def test_create_full(self) -> None:
        """完整参数创建 DimensionValue。"""
        dv = DimensionValue(
            value="上海",
            current=500000,
            baseline=580000,
            change=-80000,
            change_percent=-13.79,
            contribution=-80000,
            contribution_percent=53.33,
        )
        assert dv.value == "上海"
        assert dv.current == 500000
        assert dv.baseline == 580000
        assert dv.change == -80000
        assert dv.change == round(dv.change, 2)
        assert dv.contribution == -80000
        assert dv.contribution_percent == 53.33

    def test_positive_contribution(self) -> None:
        """正贡献值。"""
        dv = DimensionValue(
            value="北京",
            current=300000,
            baseline=200000,
            change=100000,
            change_percent=50.0,
            contribution=100000,
            contribution_percent=66.67,
        )
        assert dv.change > 0
        assert dv.contribution > 0

    def test_zero_contribution(self) -> None:
        """零贡献值。"""
        dv = DimensionValue(
            value="广州",
            current=100000,
            baseline=100000,
            change=0.0,
            change_percent=0.0,
            contribution=0.0,
            contribution_percent=0.0,
        )
        assert dv.change == 0.0
        assert dv.contribution == 0.0
        assert dv.contribution_percent == 0.0


# ==================================================================
# DrillDownResult
# ==================================================================


class TestDrillDownResult:
    """DrillDownResult 数据模型测试。"""

    def test_create_minimal(self) -> None:
        """最小化创建 DrillDownResult。"""
        dd = DrillDownResult(dimension_name="城市")
        assert dd.dimension_name == "城市"
        assert dd.values == []
        assert dd.top_contributors == []

    def test_create_with_values(self) -> None:
        """带维度值的 DrillDownResult。"""
        dv1 = DimensionValue(
            value="上海", current=500000, baseline=580000,
            change=-80000, change_percent=-13.79,
            contribution=-80000, contribution_percent=53.33,
        )
        dv2 = DimensionValue(
            value="北京", current=200000, baseline=220000,
            change=-20000, change_percent=-9.09,
            contribution=-20000, contribution_percent=13.33,
        )
        dd = DrillDownResult(
            dimension_name="城市",
            values=[dv1, dv2],
            top_contributors=[dv1],
        )
        assert len(dd.values) == 2
        assert len(dd.top_contributors) == 1
        assert dd.top_contributors[0].value == "上海"


# ==================================================================
# AttributionResult
# ==================================================================


class TestAttributionResult:
    """AttributionResult 数据模型测试。"""

    def test_create_minimal(self) -> None:
        """最小化创建 AttributionResult。"""
        attr = AttributionResult(total_change=-150000)
        assert attr.total_change == -150000
        assert attr.total_change_percent == 0.0
        assert attr.dimensions == []
        assert attr.key_drivers == []

    def test_create_full(self) -> None:
        """完整参数创建 AttributionResult。"""
        attr = AttributionResult(
            total_change=-150000,
            total_change_percent=-15.0,
            dimensions=[
                {
                    "dimension": "城市",
                    "value": "上海",
                    "contribution": -80000,
                    "contribution_percent": 53.33,
                },
            ],
            key_drivers=["城市:上海"],
        )
        assert attr.total_change == -150000
        assert attr.total_change_percent == -15.0
        assert len(attr.dimensions) == 1
        assert attr.key_drivers == ["城市:上海"]


# ==================================================================
# RCAReport
# ==================================================================


class TestRCAReport:
    """RCAReport 数据模型测试。"""

    def _make_sample_report(self) -> RCAReport:
        """创建示例 RCAReport。"""
        anomaly = AnomalyResult(
            metric_name="销售额",
            current_value=850000,
            baseline_value=1000000,
            change_percent=-15.0,
            is_anomaly=True,
            anomaly_type="drop",
            confidence=0.85,
            direction="down",
        )
        dv = DimensionValue(
            value="上海",
            current=500000,
            baseline=580000,
            change=-80000,
            change_percent=-13.79,
            contribution=-80000,
            contribution_percent=53.33,
        )
        dd = DrillDownResult(
            dimension_name="城市",
            values=[dv],
            top_contributors=[dv],
        )
        attr = AttributionResult(
            total_change=-150000,
            total_change_percent=-15.0,
            dimensions=[
                {
                    "dimension": "城市",
                    "value": "上海",
                    "contribution": -80000,
                    "contribution_percent": 53.33,
                },
            ],
            key_drivers=["城市:上海"],
        )
        return RCAReport(
            analysis_id="rca-abc123",
            question="为什么销售额下降了？",
            anomaly=anomaly,
            drill_downs=[dd],
            attribution=attr,
            summary="销售额下降15%，主要原因是上海贡献下降。",
            confidence=0.85,
            execution_time_ms=123.45,
        )

    def test_create_report(self) -> None:
        """创建完整 RCAReport。"""
        report = self._make_sample_report()
        assert report.analysis_id == "rca-abc123"
        assert report.question == "为什么销售额下降了？"
        assert report.anomaly.is_anomaly is True
        assert len(report.drill_downs) == 1
        assert len(report.attribution.key_drivers) == 1
        assert report.confidence == 0.85
        assert report.execution_time_ms == 123.45

    def test_to_dict(self) -> None:
        """序列化为字典。"""
        report = self._make_sample_report()
        d = report.to_dict()
        assert d["analysis_id"] == "rca-abc123"
        assert d["question"] == "为什么销售额下降了？"
        assert d["anomaly"]["metric_name"] == "销售额"
        assert isinstance(d["drill_downs"], list)
        assert len(d["drill_downs"]) == 1
        assert isinstance(d["drill_downs"][0]["values"], list)

    def test_from_dict_roundtrip(self) -> None:
        """字典序列化与反序列化往返。"""
        report = self._make_sample_report()
        d = report.to_dict()
        restored = RCAReport.from_dict(d)

        assert restored.analysis_id == report.analysis_id
        assert restored.question == report.question
        assert restored.anomaly.metric_name == report.anomaly.metric_name
        assert restored.anomaly.current_value == report.anomaly.current_value
        assert restored.anomaly.direction == report.anomaly.direction
        assert len(restored.drill_downs) == len(report.drill_downs)
        assert restored.drill_downs[0].dimension_name == report.drill_downs[0].dimension_name
        assert restored.attribution.total_change == report.attribution.total_change
        assert restored.attribution.total_change_percent == report.attribution.total_change_percent
        assert restored.confidence == report.confidence
        assert restored.execution_time_ms == report.execution_time_ms
