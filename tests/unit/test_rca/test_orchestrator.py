"""RCA 编排器单元测试。"""
from __future__ import annotations

import pytest

from datapilot_agent.rca.anomaly_detector import AnomalyDetector
from datapilot_agent.rca.attribution import AttributionAnalyzer
from datapilot_agent.rca.drill_down import DimensionDrillDown
from datapilot_agent.rca.interpreter import DataInterpreter
from datapilot_agent.rca.models import (
    AnomalyResult,
    AttributionResult,
    DimensionValue,
    DrillDownResult,
    RCAReport,
)
from datapilot_agent.rca.orchestrator import RCAOrchestrator


# ==================================================================
# 测试数据
# ==================================================================

CURRENT_DATA = {
    "value": 850000,
    "城市": {"上海": 500000, "北京": 200000, "广州": 100000, "深圳": 50000},
    "品类": {"电子产品": 400000, "服装": 250000, "食品": 200000},
}

BASELINE_DATA = {
    "value": 1000000,
    "城市": {"上海": 580000, "北京": 220000, "广州": 120000, "深圳": 80000},
    "品类": {"电子产品": 500000, "服装": 280000, "食品": 220000},
}


# ==================================================================
# 编排器初始化
# ==================================================================


class TestRCAOrchestratorInit:
    """RCA 编排器初始化测试。"""

    def test_default_init(self) -> None:
        """默认初始化。"""
        orchestrator = RCAOrchestrator()
        assert isinstance(orchestrator._anomaly_detector, AnomalyDetector)
        assert isinstance(orchestrator._drill_down, DimensionDrillDown)
        assert isinstance(orchestrator._attribution, AttributionAnalyzer)
        assert isinstance(orchestrator._interpreter, DataInterpreter)

    def test_custom_init(self) -> None:
        """自定义组件注入。"""
        detector = AnomalyDetector(threshold_zscore=2.0)
        drill = DimensionDrillDown()
        attr = AttributionAnalyzer()
        interp = DataInterpreter()

        orchestrator = RCAOrchestrator(
            anomaly_detector=detector,
            drill_down=drill,
            attribution=attr,
            interpreter=interp,
        )
        assert orchestrator._anomaly_detector is detector
        assert orchestrator._drill_down is drill
        assert orchestrator._attribution is attr
        assert orchestrator._interpreter is interp


# ==================================================================
# 完整分析流程
# ==================================================================


class TestRCAOrchestratorAnalyze:
    """RCA 完整分析流程测试。"""

    @pytest.fixture()
    def orchestrator(self) -> RCAOrchestrator:
        """默认编排器。"""
        return RCAOrchestrator()

    @pytest.mark.asyncio()
    async def test_analyze_returns_report(self, orchestrator: RCAOrchestrator) -> None:
        """分析返回 RCAReport。"""
        report = await orchestrator.analyze(
            question="为什么销售额下降了？",
            metric_name="销售额",
            current_data=CURRENT_DATA,
            baseline_data=BASELINE_DATA,
        )
        assert isinstance(report, RCAReport)
        assert report.question == "为什么销售额下降了？"

    @pytest.mark.asyncio()
    async def test_analyze_has_analysis_id(self, orchestrator: RCAOrchestrator) -> None:
        """分析报告有唯一 ID。"""
        report = await orchestrator.analyze(
            question="为什么销售额下降了？",
            metric_name="销售额",
            current_data=CURRENT_DATA,
            baseline_data=BASELINE_DATA,
        )
        assert report.analysis_id
        assert len(report.analysis_id) == 12

    @pytest.mark.asyncio()
    async def test_analyze_anomaly_detected(self, orchestrator: RCAOrchestrator) -> None:
        """检测到异常（-15% 变化）。"""
        report = await orchestrator.analyze(
            question="为什么销售额下降了？",
            metric_name="销售额",
            current_data=CURRENT_DATA,
            baseline_data=BASELINE_DATA,
        )
        assert report.anomaly.is_anomaly is True
        assert report.anomaly.direction == "down"
        assert report.anomaly.change_percent < 0

    @pytest.mark.asyncio()
    async def test_analyze_drill_downs(self, orchestrator: RCAOrchestrator) -> None:
        """维度下钻结果正确。"""
        report = await orchestrator.analyze(
            question="为什么销售额下降了？",
            metric_name="销售额",
            current_data=CURRENT_DATA,
            baseline_data=BASELINE_DATA,
        )
        # 应有两个维度：城市、品类
        assert len(report.drill_downs) == 2
        dim_names = {dd.dimension_name for dd in report.drill_downs}
        assert "城市" in dim_names
        assert "品类" in dim_names

    @pytest.mark.asyncio()
    async def test_analyze_attribution(self, orchestrator: RCAOrchestrator) -> None:
        """归因分析结果正确。"""
        report = await orchestrator.analyze(
            question="为什么销售额下降了？",
            metric_name="销售额",
            current_data=CURRENT_DATA,
            baseline_data=BASELINE_DATA,
        )
        assert report.attribution.total_change < 0
        assert len(report.attribution.key_drivers) > 0

    @pytest.mark.asyncio()
    async def test_analyze_summary(self, orchestrator: RCAOrchestrator) -> None:
        """自然语言总结非空。"""
        report = await orchestrator.analyze(
            question="为什么销售额下降了？",
            metric_name="销售额",
            current_data=CURRENT_DATA,
            baseline_data=BASELINE_DATA,
        )
        assert report.summary
        assert len(report.summary) > 0

    @pytest.mark.asyncio()
    async def test_analyze_execution_time(self, orchestrator: RCAOrchestrator) -> None:
        """执行耗时非负。"""
        report = await orchestrator.analyze(
            question="为什么销售额下降了？",
            metric_name="销售额",
            current_data=CURRENT_DATA,
            baseline_data=BASELINE_DATA,
        )
        assert report.execution_time_ms >= 0

    @pytest.mark.asyncio()
    async def test_analyze_custom_dimensions(self, orchestrator: RCAOrchestrator) -> None:
        """自定义维度列表。"""
        report = await orchestrator.analyze(
            question="分析城市维度",
            metric_name="销售额",
            current_data=CURRENT_DATA,
            baseline_data=BASELINE_DATA,
            dimensions=[{"name": "城市"}],
        )
        assert len(report.drill_downs) == 1
        assert report.drill_downs[0].dimension_name == "城市"


# ==================================================================
# 无异常场景
# ==================================================================


class TestRCAOrchestratorNoAnomaly:
    """无异常场景测试。"""

    @pytest.fixture()
    def orchestrator(self) -> RCAOrchestrator:
        """默认编排器。"""
        return RCAOrchestrator()

    @pytest.mark.asyncio()
    async def test_no_change_no_anomaly(self, orchestrator: RCAOrchestrator) -> None:
        """数据无变化，不异常。"""
        report = await orchestrator.analyze(
            question="销售额怎么样？",
            metric_name="销售额",
            current_data={"value": 1000000, "城市": {"上海": 500000}},
            baseline_data={"value": 1000000, "城市": {"上海": 500000}},
        )
        assert report.anomaly.is_anomaly is False
        assert report.anomaly.change_percent == 0.0

    @pytest.mark.asyncio()
    async def test_no_dimensions(self, orchestrator: RCAOrchestrator) -> None:
        """无维度数据。"""
        report = await orchestrator.analyze(
            question="销售额怎么样？",
            metric_name="销售额",
            current_data={"value": 850000},
            baseline_data={"value": 1000000},
        )
        assert report.anomaly.is_anomaly is True
        assert len(report.drill_downs) == 0
