"""RCA 分析编排器。"""
from __future__ import annotations

import time
import uuid
from typing import Any

from datapilot_agent.rca.anomaly_detector import AnomalyDetector
from datapilot_agent.rca.attribution import AttributionAnalyzer
from datapilot_agent.rca.drill_down import DimensionDrillDown
from datapilot_agent.rca.interpreter import DataInterpreter
from datapilot_agent.rca.models import RCAReport


class RCAOrchestrator:
    """RCA 分析编排器，串联异常检测、维度下钻、归因分析和自然语言总结。"""

    def __init__(
        self,
        anomaly_detector: AnomalyDetector | None = None,
        drill_down: DimensionDrillDown | None = None,
        attribution: AttributionAnalyzer | None = None,
        interpreter: DataInterpreter | None = None,
    ) -> None:
        """初始化 RCA 编排器。

        各组件均可注入，便于测试时替换为 mock。

        Args:
            anomaly_detector: 异常检测器
            drill_down: 维度下钻分析器
            attribution: 归因分析器
            interpreter: 数据解释器
        """
        self._anomaly_detector = anomaly_detector or AnomalyDetector()
        self._drill_down = drill_down or DimensionDrillDown()
        self._attribution = attribution or AttributionAnalyzer()
        self._interpreter = interpreter or DataInterpreter()

    async def analyze(
        self,
        question: str,
        metric_name: str,
        current_data: dict[str, Any],
        baseline_data: dict[str, Any],
        dimensions: list[dict[str, Any]] | None = None,
    ) -> RCAReport:
        """执行完整的 RCA 分析流程。

        参数说明：
        - current_data: 当前时段的汇总数据
          {"value": 850000, "城市": {"上海": 500000, ...}}
        - baseline_data: 对比时段的汇总数据（同结构）
        - dimensions: 需要下钻的维度列表（默认为 current_data 中除 value 外的所有键）

        流程：
        1. AnomalyDetector.detect() — 异常检测
        2. DimensionDrillDown.drill() — 逐维度下钻
        3. AttributionAnalyzer.analyze() — 归因分析
        4. DataInterpreter.generate_full_summary() — 生成总结

        Args:
            question: 用户问题
            metric_name: 指标名称
            current_data: 当前时段数据
            baseline_data: 对比时段数据
            dimensions: 需要下钻的维度列表（可选）

        Returns:
            RCAReport: 完整的 RCA 分析报告
        """
        start_time = time.perf_counter()
        analysis_id = uuid.uuid4().hex[:12]

        # ---- 步骤 1：异常检测 ----
        current_value = float(current_data.get("value", 0))
        baseline_value = float(baseline_data.get("value", 0))
        anomaly = self._anomaly_detector.detect(
            metric_name=metric_name,
            current_value=current_value,
            baseline_value=baseline_value,
        )

        # ---- 步骤 2：维度下钻 ----
        total_change = current_value - baseline_value

        # 确定需要下钻的维度
        if dimensions is None:
            # 默认取 current_data 中除 "value" 外的键作为维度
            dimension_keys = [
                k for k in current_data.keys() if k != "value" and isinstance(current_data[k], dict)
            ]
        else:
            dimension_keys = [d.get("name", d) if isinstance(d, dict) else str(d) for d in dimensions]

        drill_downs: list[Any] = []
        for dim_key in dimension_keys:
            dim_current = current_data.get(dim_key, {})
            dim_baseline = baseline_data.get(dim_key, {})
            if isinstance(dim_current, dict) and isinstance(dim_baseline, dict):
                dd_result = await self._drill_down.drill(
                    dimension_name=str(dim_key),
                    dimension_values={str(k): float(v) for k, v in dim_current.items()},
                    baseline_values={str(k): float(v) for k, v in dim_baseline.items()},
                    total_change=total_change,
                )
                drill_downs.append(dd_result)

        # ---- 步骤 3：归因分析 ----
        attribution = self._attribution.analyze(
            drill_downs=drill_downs,
            total_change=total_change,
        )

        # ---- 步骤 4：生成总结 ----
        report = RCAReport(
            analysis_id=analysis_id,
            question=question,
            anomaly=anomaly,
            drill_downs=drill_downs,
            attribution=attribution,
            summary="",  # 先占位
            confidence=anomaly.confidence,
        )
        report.summary = self._interpreter.generate_full_summary(report)

        # ---- 计算耗时 ----
        end_time = time.perf_counter()
        report.execution_time_ms = (end_time - start_time) * 1000

        return report
