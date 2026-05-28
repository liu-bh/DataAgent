"""RCA 根因分析数据模型。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AnomalyResult:
    """异常检测结果。

    Attributes:
        metric_name: 指标名称
        current_value: 当前值
        baseline_value: 基线值
        change_percent: 变化百分比（正数表示上升，负数表示下降）
        is_anomaly: 是否异常
        anomaly_type: 异常类型，"drop" / "spike" / "trend_change" / "none"
        confidence: 置信度，0.0 ~ 1.0
        direction: 变化方向，"up" / "down" / "neutral"
    """

    metric_name: str
    current_value: float
    baseline_value: float
    change_percent: float
    is_anomaly: bool
    anomaly_type: str  # "drop" / "spike" / "trend_change" / "none"
    confidence: float  # 0.0 ~ 1.0
    direction: str = "neutral"  # "up" / "down" / "neutral"


@dataclass
class DimensionValue:
    """维度值及其变化贡献。

    Attributes:
        value: 维度值（如城市名"上海"）
        current: 当前值
        baseline: 基线值
        change: 变化量（current - baseline）
        change_percent: 变化百分比
        contribution: 对总变化的贡献值
        contribution_percent: 贡献百分比
    """

    value: str
    current: float
    baseline: float
    change: float
    change_percent: float
    contribution: float  # 对总变化的贡献值
    contribution_percent: float  # 贡献百分比


@dataclass
class DrillDownResult:
    """维度下钻结果。

    Attributes:
        dimension_name: 维度名称（如"城市"、"品类"）
        values: 所有维度值的变化明细
        top_contributors: 贡献度最大的维度值（按 |contribution| 降序）
    """

    dimension_name: str
    values: list[DimensionValue] = field(default_factory=list)
    top_contributors: list[DimensionValue] = field(default_factory=list)


@dataclass
class AttributionResult:
    """归因分析结果。

    Attributes:
        total_change: 总变化量
        total_change_percent: 总变化百分比
        dimensions: 各维度的归因详情
        key_drivers: 关键驱动因素（累计贡献达到 80% 的维度值）
    """

    total_change: float
    total_change_percent: float = 0.0
    dimensions: list[dict[str, Any]] = field(default_factory=list)
    key_drivers: list[str] = field(default_factory=list)


@dataclass
class RCAReport:
    """完整的 RCA 分析报告。

    Attributes:
        analysis_id: 分析唯一标识
        question: 用户问题
        anomaly: 异常检测结果
        drill_downs: 各维度下钻结果列表
        attribution: 归因分析结果
        summary: 自然语言总结
        confidence: 整体置信度
        execution_time_ms: 执行耗时（毫秒）
    """

    analysis_id: str
    question: str
    anomaly: AnomalyResult
    drill_downs: list[DrillDownResult]
    attribution: AttributionResult
    summary: str
    confidence: float = 0.0
    execution_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RCAReport:
        """从字典反序列化。"""
        anomaly_data = data.get("anomaly", {})
        if isinstance(anomaly_data, dict):
            anomaly = AnomalyResult(**anomaly_data)
        else:
            anomaly = anomaly_data

        drill_downs = []
        for dd in data.get("drill_downs", []):
            if isinstance(dd, dict):
                # 兼容旧格式（dict）和新格式（DimensionValue 对象）
                values = []
                for v in dd.get("values", []):
                    if isinstance(v, dict):
                        values.append(DimensionValue(**v))
                    else:
                        values.append(v)

                top_contributors = []
                for tc in dd.get("top_contributors", []):
                    if isinstance(tc, dict):
                        top_contributors.append(DimensionValue(**tc))
                    else:
                        top_contributors.append(tc)

                drill_downs.append(
                    DrillDownResult(
                        dimension_name=dd.get("dimension_name", ""),
                        values=values,
                        top_contributors=top_contributors,
                    )
                )
            else:
                drill_downs.append(dd)

        attribution_data = data.get("attribution", {})
        if isinstance(attribution_data, dict):
            attribution = AttributionResult(**attribution_data)
        else:
            attribution = attribution_data

        return cls(
            analysis_id=data.get("analysis_id", ""),
            question=data.get("question", ""),
            anomaly=anomaly,
            drill_downs=drill_downs,
            attribution=attribution,
            summary=data.get("summary", ""),
            confidence=data.get("confidence", 0.0),
            execution_time_ms=data.get("execution_time_ms", 0.0),
        )
