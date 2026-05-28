"""异常检测器单元测试。"""
from __future__ import annotations

import math

import pytest

from datapilot_agent.rca.anomaly_detector import AnomalyDetector
from datapilot_agent.rca.models import AnomalyResult


# ==================================================================
# 基本检测
# ==================================================================


class TestAnomalyDetectorInit:
    """AnomalyDetector 初始化测试。"""

    def test_default_thresholds(self) -> None:
        """默认阈值。"""
        detector = AnomalyDetector()
        assert detector._threshold_zscore == 1.5
        assert detector._threshold_change_percent == 5.0

    def test_custom_thresholds(self) -> None:
        """自定义阈值。"""
        detector = AnomalyDetector(threshold_zscore=2.0, threshold_change_percent=10.0)
        assert detector._threshold_zscore == 2.0
        assert detector._threshold_change_percent == 10.0


# ==================================================================
# 变化百分比检测
# ==================================================================


class TestChangePercentDetection:
    """基于变化百分比的异常检测测试。"""

    @pytest.fixture()
    def detector(self) -> AnomalyDetector:
        """默认检测器。"""
        return AnomalyDetector(threshold_zscore=999.0, threshold_change_percent=5.0)

    def test_no_change(self, detector: AnomalyDetector) -> None:
        """无变化，不异常。"""
        result = detector.detect("销售额", 1000, 1000)
        assert result.is_anomaly is False
        assert result.change_percent == 0.0

    def test_small_change_not_anomaly(self, detector: AnomalyDetector) -> None:
        """变化小于阈值，不异常。"""
        result = detector.detect("销售额", 1030, 1000)
        assert result.change_percent == pytest.approx(3.0, abs=0.01)
        assert result.is_anomaly is False

    def test_exactly_at_threshold(self, detector: AnomalyDetector) -> None:
        """恰好等于阈值，应判定为异常。"""
        result = detector.detect("销售额", 1050, 1000)
        assert result.change_percent == pytest.approx(5.0, abs=0.01)
        assert result.is_anomaly is True

    def test_large_drop(self, detector: AnomalyDetector) -> None:
        """大幅下降。"""
        result = detector.detect("销售额", 500, 1000)
        assert result.change_percent == pytest.approx(-50.0, abs=0.01)
        assert result.is_anomaly is True

    def test_large_spike(self, detector: AnomalyDetector) -> None:
        """大幅上升。"""
        result = detector.detect("销售额", 2000, 1000)
        assert result.change_percent == pytest.approx(100.0, abs=0.01)
        assert result.is_anomaly is True

    def test_negative_baseline(self, detector: AnomalyDetector) -> None:
        """负数基线值。"""
        result = detector.detect("利润", -500, -1000)
        assert result.change_percent == pytest.approx(50.0, abs=0.01)
        assert result.is_anomaly is True


# ==================================================================
# 零值基线
# ==================================================================


class TestZeroBaseline:
    """零值基线测试。"""

    @pytest.fixture()
    def detector(self) -> AnomalyDetector:
        """默认检测器。"""
        return AnomalyDetector()

    def test_zero_baseline_zero_current(self, detector: AnomalyDetector) -> None:
        """基线和当前值都为零。"""
        result = detector.detect("错误数", 0, 0)
        assert result.change_percent == 0.0
        assert result.is_anomaly is False

    def test_zero_baseline_nonzero_current(self, detector: AnomalyDetector) -> None:
        """基线为零，当前值非零。"""
        result = detector.detect("错误数", 100, 0)
        assert result.change_percent == 100.0
        assert result.is_anomaly is True


# ==================================================================
# Z-score 检测
# ==================================================================


class TestZScoreDetection:
    """基于 Z-score 的异常检测测试。"""

    @pytest.fixture()
    def detector(self) -> AnomalyDetector:
        """低阈值检测器，使 Z-score 更容易触发。"""
        return AnomalyDetector(threshold_zscore=1.0, threshold_change_percent=999.0)

    def test_zscore_triggers_on_large_change(self, detector: AnomalyDetector) -> None:
        """Z-score 在大幅变化时触发。"""
        # Z-score = (850000 - 1000000) / (1000000 * 0.1) = -1.5
        result = detector.detect("销售额", 850000, 1000000)
        assert result.is_anomaly is True

    def test_zscore_no_trigger_small_change(self, detector: AnomalyDetector) -> None:
        """Z-score 在小幅变化时不触发。"""
        result = detector.detect("销售额", 1005000, 1000000)
        assert result.is_anomaly is False


# ==================================================================
# 方向和类型
# ==================================================================


class TestDirectionAndType:
    """方向和异常类型测试。"""

    @pytest.fixture()
    def detector(self) -> AnomalyDetector:
        """默认检测器。"""
        return AnomalyDetector(threshold_change_percent=5.0)

    def test_direction_up(self, detector: AnomalyDetector) -> None:
        """上升方向。"""
        result = detector.detect("销售额", 1100, 1000)
        assert result.direction == "up"

    def test_direction_down(self, detector: AnomalyDetector) -> None:
        """下降方向。"""
        result = detector.detect("销售额", 900, 1000)
        assert result.direction == "down"

    def test_direction_neutral(self, detector: AnomalyDetector) -> None:
        """持平方向。"""
        result = detector.detect("销售额", 1000, 1000)
        assert result.direction == "neutral"

    def test_anomaly_type_spike(self, detector: AnomalyDetector) -> None:
        """急剧上升判定为 spike。"""
        # 超过 3 倍阈值 (15%) 才是 spike
        result = detector.detect("销售额", 1200, 1000)
        assert result.is_anomaly is True
        assert result.anomaly_type == "spike"

    def test_anomaly_type_drop(self, detector: AnomalyDetector) -> None:
        """急剧下降判定为 drop。"""
        result = detector.detect("销售额", 800, 1000)
        assert result.is_anomaly is True
        assert result.anomaly_type == "drop"

    def test_anomaly_type_trend_change_up(self, detector: AnomalyDetector) -> None:
        """小幅上升趋势变化。"""
        # 5%~15% 之间为 trend_change
        result = detector.detect("销售额", 1070, 1000)
        assert result.is_anomaly is True
        assert result.anomaly_type == "trend_change"

    def test_anomaly_type_none(self, detector: AnomalyDetector) -> None:
        """无异常时类型为 none。"""
        result = detector.detect("销售额", 1001, 1000)
        assert result.is_anomaly is False
        assert result.anomaly_type == "none"


# ==================================================================
# 置信度
# ==================================================================


class TestConfidence:
    """置信度计算测试。"""

    @pytest.fixture()
    def detector(self) -> AnomalyDetector:
        """默认检测器。"""
        return AnomalyDetector()

    def test_confidence_zero_change(self, detector: AnomalyDetector) -> None:
        """无变化时置信度接近零。"""
        result = detector.detect("销售额", 1000, 1000)
        assert result.confidence == pytest.approx(0.0, abs=0.01)

    def test_confidence_large_change(self, detector: AnomalyDetector) -> None:
        """大幅变化时置信度高。"""
        result = detector.detect("销售额", 500, 1000)
        assert result.confidence > 0.5

    def test_confidence_range(self, detector: AnomalyDetector) -> None:
        """置信度在 0~1 范围内。"""
        result = detector.detect("销售额", 1000, 1000)
        assert 0.0 <= result.confidence <= 1.0


# ==================================================================
# 批量检测
# ==================================================================


class TestBatchDetection:
    """批量检测测试。"""

    def test_batch_detect(self) -> None:
        """批量检测多个维度。"""
        detector = AnomalyDetector()
        current = {"上海": 500000, "北京": 200000, "广州": 100000}
        baseline = {"上海": 580000, "北京": 220000, "广州": 120000}
        results = detector.detect_batch("销售额", current, baseline)

        assert len(results) == 3
        # 所有维度都有下降
        assert all(r.change_percent < 0 for r in results)

    def test_batch_detect_extra_keys(self) -> None:
        """批量检测时维度键不一致。"""
        detector = AnomalyDetector()
        current = {"上海": 500000, "北京": 200000, "广州": 100000}
        baseline = {"上海": 580000, "深圳": 80000}
        results = detector.detect_batch("销售额", current, baseline)

        # 合并所有键，按字母排序
        assert len(results) == 4
        names = [r.metric_name for r in results]
        assert "销售额#上海" in names
        assert "销售额#北京" in names
        assert "销售额#广州" in names
        assert "销售额#深圳" in names

    def test_batch_detect_empty(self) -> None:
        """空数据批量检测。"""
        detector = AnomalyDetector()
        results = detector.detect_batch("销售额", {}, {})
        assert results == []


# ==================================================================
# 辅助方法
# ==================================================================


class TestHelperMethods:
    """辅助方法测试。"""

    def test_calculate_direction_up(self) -> None:
        """_calculate_direction 上升。"""
        detector = AnomalyDetector()
        assert detector._calculate_direction(10.0) == "up"

    def test_calculate_direction_down(self) -> None:
        """_calculate_direction 下降。"""
        detector = AnomalyDetector()
        assert detector._calculate_direction(-10.0) == "down"

    def test_calculate_direction_neutral(self) -> None:
        """_calculate_direction 持平。"""
        detector = AnomalyDetector()
        assert detector._calculate_direction(0.1) == "neutral"

    def test_determine_anomaly_type_spike(self) -> None:
        """_determine_anomaly_type spike。"""
        detector = AnomalyDetector(threshold_change_percent=5.0)
        # 超过 3 倍阈值 = 15%
        assert detector._determine_anomaly_type(20.0) == "spike"

    def test_determine_anomaly_type_drop(self) -> None:
        """_determine_anomaly_type drop。"""
        detector = AnomalyDetector(threshold_change_percent=5.0)
        assert detector._determine_anomaly_type(-20.0) == "drop"

    def test_determine_anomaly_type_trend_change(self) -> None:
        """_determine_anomaly_type trend_change。"""
        detector = AnomalyDetector(threshold_change_percent=5.0)
        # 在 5%~15% 之间
        assert detector._determine_anomaly_type(8.0) == "trend_change"
