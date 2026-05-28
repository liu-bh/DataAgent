"""数据解释器（自然语言总结）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datapilot_agent.rca.models import (
        AnomalyResult,
        AttributionResult,
        DrillDownResult,
        RCAReport,
    )


class DataInterpreter:
    """将 RCA 分析结果转换为自然语言描述。"""

    def summarize_anomaly(self, anomaly: AnomalyResult) -> str:
        """生成异常检测的自然语言描述。

        Args:
            anomaly: 异常检测结果

        Returns:
            自然语言描述
        """
        direction_text = {
            "up": "上升",
            "down": "下降",
            "neutral": "持平",
        }.get(anomaly.direction, "变化")

        if not anomaly.is_anomaly:
            return (
                f"指标「{anomaly.metric_name}」无异常，"
                f"当前值 {anomaly.current_value:,.2f}，"
                f"较基线值 {anomaly.baseline_value:,.2f} "
                f"变化 {anomaly.change_percent:+.2f}%。"
            )

        anomaly_type_text = {
            "spike": "急剧上升",
            "drop": "急剧下降",
            "trend_change": "趋势变化",
        }.get(anomaly.anomaly_type, "异常")

        return (
            f"指标「{anomaly.metric_name}」检测到{anomaly_type_text}异常，"
            f"当前值 {anomaly.current_value:,.2f}，"
            f"较基线值 {anomaly.baseline_value:,.2f} "
            f"{direction_text} {abs(anomaly.change_percent):.2f}%，"
            f"置信度 {anomaly.confidence:.2%}。"
        )

    def summarize_drill_down(self, drill_down: DrillDownResult) -> str:
        """生成维度下钻的自然语言描述。

        Args:
            drill_down: 维度下钻结果

        Returns:
            自然语言描述
        """
        if not drill_down.values:
            return f"维度「{drill_down.dimension_name}」无数据。"

        # 取 top 3 贡献者
        top = drill_down.top_contributors[:3]
        parts: list[str] = []
        for dv in top:
            direction = "增长" if dv.change > 0 else "下降" if dv.change < 0 else "持平"
            parts.append(
                f"{dv.value}（{direction} {abs(dv.change):,.2f}，"
                f"变化率 {dv.change_percent:+.2f}%，"
                f"贡献度 {dv.contribution_percent:.2f}%）"
            )

        top_desc = "；".join(parts)
        return f"按「{drill_down.dimension_name}」维度下钻，主要变化来源：{top_desc}。"

    def summarize_attribution(self, attribution: AttributionResult) -> str:
        """生成归因分析的自然语言描述。

        Args:
            attribution: 归因分析结果

        Returns:
            自然语言描述
        """
        if not attribution.key_drivers:
            return "未识别到关键驱动因素。"

        drivers_desc = "、".join(attribution.key_drivers[:5])
        total_direction = (
            "下降"
            if attribution.total_change < 0
            else "上升"
            if attribution.total_change > 0
            else "持平"
        )

        return (
            f"整体{total_direction} {abs(attribution.total_change):,.2f}，"
            f"关键驱动因素：{drivers_desc}，"
            f"共涉及 {len(attribution.key_drivers)} 个主要维度值。"
        )

    def generate_full_summary(self, report: RCAReport) -> str:
        """生成完整的 RCA 自然语言总结。

        Args:
            report: 完整的 RCA 分析报告

        Returns:
            自然语言总结
        """
        parts: list[str] = []

        # 1. 异常检测
        parts.append(self.summarize_anomaly(report.anomaly))

        # 2. 维度下钻
        for dd in report.drill_downs:
            parts.append(self.summarize_drill_down(dd))

        # 3. 归因分析
        parts.append(self.summarize_attribution(report.attribution))

        return "\n".join(parts)
