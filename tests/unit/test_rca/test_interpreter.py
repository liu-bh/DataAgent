"""数据解释器（自然语言总结）单元测试。"""
from __future__ import annotations

import pytest

from datapilot_agent.rca.interpreter import DataInterpreter
from datapilot_agent.rca.models import (
    AnomalyResult,
    AttributionResult,
    DimensionValue,
    DrillDownResult,
    RCAReport,
)


# ==================================================================
# 异常检测总结
# ==================================================================


class TestSummarizeAnomaly:
    """异常检测自然语言总结测试。"""

    @pytest.fixture()
    def interpreter(self) -> DataInterpreter:
        """数据解释器。"""
        return DataInterpreter()

    def test_no_anomaly(self, interpreter: DataInterpreter) -> None:
        """无异常时的描述。"""
        anomaly = AnomalyResult(
            metric_name="销售额",
            current_value=1000000,
            baseline_value=1010000,
            change_percent=-1.0,
            is_anomaly=False,
            anomaly_type="none",
            confidence=0.1,
            direction="neutral",
        )
        summary = interpreter.summarize_anomaly(anomaly)
        assert "无异常" in summary
        assert "销售额" in summary

    def test_drop_anomaly(self, interpreter: DataInterpreter) -> None:
        """下降异常的描述。"""
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
        summary = interpreter.summarize_anomaly(anomaly)
        assert "异常" in summary
        assert "销售额" in summary
        assert "15.00%" in summary

    def test_spike_anomaly(self, interpreter: DataInterpreter) -> None:
        """急剧上升异常的描述。"""
        anomaly = AnomalyResult(
            metric_name="访问量",
            current_value=50000,
            baseline_value=20000,
            change_percent=150.0,
            is_anomaly=True,
            anomaly_type="spike",
            confidence=0.95,
            direction="up",
        )
        summary = interpreter.summarize_anomaly(anomaly)
        assert "急剧上升" in summary
        assert "访问量" in summary

    def test_confidence_in_summary(self, interpreter: DataInterpreter) -> None:
        """总结中包含置信度。"""
        anomaly = AnomalyResult(
            metric_name="转化率",
            current_value=2.0,
            baseline_value=5.0,
            change_percent=-60.0,
            is_anomaly=True,
            anomaly_type="drop",
            confidence=0.92,
            direction="down",
        )
        summary = interpreter.summarize_anomaly(anomaly)
        assert "92.00%" in summary


# ==================================================================
# 维度下钻总结
# ==================================================================


class TestSummarizeDrillDown:
    """维度下钻自然语言总结测试。"""

    @pytest.fixture()
    def interpreter(self) -> DataInterpreter:
        """数据解释器。"""
        return DataInterpreter()

    def test_empty_drill_down(self, interpreter: DataInterpreter) -> None:
        """空下钻结果的描述。"""
        dd = DrillDownResult(dimension_name="城市")
        summary = interpreter.summarize_drill_down(dd)
        assert "无数据" in summary
        assert "城市" in summary

    def test_drill_down_with_values(self, interpreter: DataInterpreter) -> None:
        """有数据的下钻描述。"""
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
            top_contributors=[dv1, dv2],
        )
        summary = interpreter.summarize_drill_down(dd)
        assert "城市" in summary
        assert "上海" in summary

    def test_drill_down_positive_change(self, interpreter: DataInterpreter) -> None:
        """正向变化的描述。"""
        dv = DimensionValue(
            value="华东", current=600000, baseline=500000,
            change=100000, change_percent=20.0,
            contribution=100000, contribution_percent=100.0,
        )
        dd = DrillDownResult(
            dimension_name="地区",
            values=[dv],
            top_contributors=[dv],
        )
        summary = interpreter.summarize_drill_down(dd)
        assert "增长" in summary


# ==================================================================
# 归因分析总结
# ==================================================================


class TestSummarizeAttribution:
    """归因分析自然语言总结测试。"""

    @pytest.fixture()
    def interpreter(self) -> DataInterpreter:
        """数据解释器。"""
        return DataInterpreter()

    def test_no_key_drivers(self, interpreter: DataInterpreter) -> None:
        """无关键驱动因素。"""
        attr = AttributionResult(total_change=0, total_change_percent=0)
        summary = interpreter.summarize_attribution(attr)
        assert "未识别" in summary

    def test_with_key_drivers(self, interpreter: DataInterpreter) -> None:
        """有关键驱动因素。"""
        attr = AttributionResult(
            total_change=-150000,
            total_change_percent=-15.0,
            dimensions=[],
            key_drivers=["城市:上海", "品类:电子产品"],
        )
        summary = interpreter.summarize_attribution(attr)
        assert "下降" in summary
        # 格式化输出使用 :,.2f 带千分位逗号
        assert "150,000" in summary
        assert "上海" in summary


# ==================================================================
# 完整总结
# ==================================================================


class TestGenerateFullSummary:
    """完整 RCA 自然语言总结测试。"""

    @pytest.fixture()
    def interpreter(self) -> DataInterpreter:
        """数据解释器。"""
        return DataInterpreter()

    @pytest.fixture()
    def sample_report(self) -> RCAReport:
        """示例 RCA 报告。"""
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
            dimensions=[],
            key_drivers=["城市:上海"],
        )
        return RCAReport(
            analysis_id="rca-test",
            question="为什么销售额下降了？",
            anomaly=anomaly,
            drill_downs=[dd],
            attribution=attr,
            summary="",
        )

    def test_full_summary_contains_all_sections(
        self, interpreter: DataInterpreter, sample_report: RCAReport
    ) -> None:
        """完整总结包含所有部分。"""
        summary = interpreter.generate_full_summary(sample_report)
        # 包含异常描述
        assert "异常" in summary
        # 包含维度下钻描述
        assert "城市" in summary
        # 包含归因描述
        assert "驱动" in summary

    def test_full_summary_multiline(self, interpreter: DataInterpreter, sample_report: RCAReport) -> None:
        """完整总结是多行的。"""
        summary = interpreter.generate_full_summary(sample_report)
        lines = summary.strip().split("\n")
        assert len(lines) >= 2
