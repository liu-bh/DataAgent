"""统计异常检测器。"""
from __future__ import annotations

import math

from datapilot_agent.rca.models import AnomalyResult


class AnomalyDetector:
    """基于 Z-score 和变化百分比的统计异常检测器。

    异常判定规则：
    1. 变化百分比绝对值超过 threshold_change_percent
    2. Z-score 绝对值超过 threshold_zscore
    3. 满足任一条件即判定为异常
    """

    def __init__(
        self,
        threshold_zscore: float = 1.5,
        threshold_change_percent: float = 5.0,
    ) -> None:
        """初始化异常检测器。

        Args:
            threshold_zscore: Z-score 阈值，默认 1.5
            threshold_change_percent: 变化百分比阈值（绝对值），默认 5.0%
        """
        self._threshold_zscore = threshold_zscore
        self._threshold_change_percent = threshold_change_percent

    def detect(
        self,
        metric_name: str,
        current_value: float,
        baseline_value: float,
    ) -> AnomalyResult:
        """检测单个指标是否异常。

        Args:
            metric_name: 指标名称
            current_value: 当前值
            baseline_value: 基线值

        Returns:
            AnomalyResult: 异常检测结果
        """
        # 计算变化百分比
        if baseline_value == 0:
            # 基线为零时，如果当前值也不为零则视为 100% 变化
            if current_value == 0:
                change_percent = 0.0
            else:
                change_percent = 100.0
        else:
            change_percent = (current_value - baseline_value) / abs(baseline_value) * 100

        # 计算 Z-score（简化版：以基线值作为均值，变化量作为偏离）
        # 实际场景中应使用历史数据的标准差，这里使用基线值的比例作为近似
        z_score = self._calculate_z_score(current_value, baseline_value)

        # 异常判定
        is_anomaly = (
            abs(change_percent) >= self._threshold_change_percent
            or abs(z_score) >= self._threshold_zscore
        )

        # 置信度：基于 Z-score 和变化百分比的加权综合
        confidence = self._calculate_confidence(change_percent, z_score)

        # 变化方向
        direction = self._calculate_direction(change_percent)

        # 异常类型
        anomaly_type = self._determine_anomaly_type(change_percent) if is_anomaly else "none"

        return AnomalyResult(
            metric_name=metric_name,
            current_value=current_value,
            baseline_value=baseline_value,
            change_percent=change_percent,
            is_anomaly=is_anomaly,
            anomaly_type=anomaly_type,
            confidence=confidence,
            direction=direction,
        )

    def detect_batch(
        self,
        metric_name: str,
        current_values: dict[str, float],
        baseline_values: dict[str, float],
    ) -> list[AnomalyResult]:
        """批量检测多个维度的异常。

        Args:
            metric_name: 指标名称前缀
            current_values: 各维度当前值 {维度值: 当前值}
            baseline_values: 各维度基线值 {维度值: 基线值}

        Returns:
            每个维度的异常检测结果列表
        """
        results: list[AnomalyResult] = []
        # 合并所有维度键
        all_keys = set(current_values.keys()) | set(baseline_values.keys())
        for key in sorted(all_keys):
            current = current_values.get(key, 0.0)
            baseline = baseline_values.get(key, 0.0)
            result = self.detect(
                metric_name=f"{metric_name}#{key}",
                current_value=current,
                baseline_value=baseline,
            )
            results.append(result)
        return results

    def _calculate_z_score(self, current_value: float, baseline_value: float) -> float:
        """计算简化版 Z-score。

        使用基线值作为均值估计，标准差使用基线值的 10% 作为近似。
        这种简化适用于没有完整历史数据分布的场景。
        """
        if baseline_value == 0:
            return 0.0

        # 标准差近似：基线值的 10%
        std_approx = abs(baseline_value) * 0.1
        if std_approx == 0:
            return 0.0

        return (current_value - baseline_value) / std_approx

    def _calculate_confidence(self, change_percent: float, z_score: float) -> float:
        """计算异常置信度。

        综合变化百分比和 Z-score，取两者的加权平均映射到 0~1 区间。
        """
        # 变化百分比因子：越大越有信心
        cp_factor = min(abs(change_percent) / 100.0, 1.0)
        # Z-score 因子：越大越有信心
        z_factor = min(abs(z_score) / 3.0, 1.0)
        # 加权平均
        return round(0.4 * cp_factor + 0.6 * z_factor, 4)

    def _calculate_direction(self, change_percent: float) -> str:
        """计算变化方向。

        Args:
            change_percent: 变化百分比

        Returns:
            "up" / "down" / "neutral"
        """
        if change_percent > self._threshold_change_percent * 0.1:
            return "up"
        if change_percent < -self._threshold_change_percent * 0.1:
            return "down"
        return "neutral"

    def _determine_anomaly_type(self, change_percent: float) -> str:
        """判定异常类型。

        Args:
            change_percent: 变化百分比

        Returns:
            "spike"（急剧上升）、"drop"（急剧下降）、"trend_change"（趋势变化）
        """
        if abs(change_percent) >= self._threshold_change_percent * 3:
            # 变化超过 3 倍阈值视为急剧变化
            return "spike" if change_percent > 0 else "drop"
        # 变化在 1~3 倍阈值之间视为趋势变化
        if change_percent > 0:
            return "trend_change"
        return "drop"
