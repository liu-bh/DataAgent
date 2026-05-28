"""RCA 根因分析引擎。

提供异常检测、维度下钻、归因分析和自然语言总结的完整分析流程。
"""

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
from datapilot_agent.rca.store import RCAStore

__all__ = [
    # 数据模型
    "AnomalyResult",
    "DimensionValue",
    "DrillDownResult",
    "AttributionResult",
    "RCAReport",
    # 分析组件
    "AnomalyDetector",
    "DimensionDrillDown",
    "AttributionAnalyzer",
    "DataInterpreter",
    "RCAOrchestrator",
    # 存储
    "RCAStore",
]
