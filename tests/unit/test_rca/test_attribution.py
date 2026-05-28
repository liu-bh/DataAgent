"""归因分析器单元测试。"""
from __future__ import annotations

import pytest

from datapilot_agent.rca.attribution import AttributionAnalyzer
from datapilot_agent.rca.models import AttributionResult, DimensionValue, DrillDownResult


def _make_drill_down(
    dimension_name: str,
    values: list[DimensionValue],
) -> DrillDownResult:
    """创建 DrillDownResult，top_contributors 与 values 相同（模拟真实行为）。"""
    return DrillDownResult(
        dimension_name=dimension_name,
        values=list(values),
        top_contributors=list(values),
    )


# ==================================================================
# 基本归因分析
# ==================================================================


class TestAttributionAnalyzerBasic:
    """归因分析基本功能测试。"""

    @pytest.fixture()
    def analyzer(self) -> AttributionAnalyzer:
        """归因分析器。"""
        return AttributionAnalyzer()

    @pytest.fixture()
    def sample_drill_downs(self) -> list[DrillDownResult]:
        """示例维度下钻结果。"""
        city_values = [
            DimensionValue(
                value="上海", current=500000, baseline=580000,
                change=-80000, change_percent=-13.79,
                contribution=-80000, contribution_percent=53.33,
            ),
            DimensionValue(
                value="北京", current=200000, baseline=220000,
                change=-20000, change_percent=-9.09,
                contribution=-20000, contribution_percent=13.33,
            ),
            DimensionValue(
                value="广州", current=100000, baseline=120000,
                change=-20000, change_percent=-16.67,
                contribution=-20000, contribution_percent=13.33,
            ),
            DimensionValue(
                value="深圳", current=50000, baseline=80000,
                change=-30000, change_percent=-37.5,
                contribution=-30000, contribution_percent=20.0,
            ),
        ]
        category_values = [
            DimensionValue(
                value="电子产品", current=400000, baseline=500000,
                change=-100000, change_percent=-20.0,
                contribution=-100000, contribution_percent=66.67,
            ),
            DimensionValue(
                value="服装", current=250000, baseline=280000,
                change=-30000, change_percent=-10.71,
                contribution=-30000, contribution_percent=20.0,
            ),
            DimensionValue(
                value="食品", current=200000, baseline=220000,
                change=-20000, change_percent=-9.09,
                contribution=-20000, contribution_percent=13.33,
            ),
        ]
        return [
            _make_drill_down("城市", city_values),
            _make_drill_down("品类", category_values),
        ]

    def test_analyze_returns_result(self, analyzer: AttributionAnalyzer, sample_drill_downs: list[DrillDownResult]) -> None:
        """归因分析返回 AttributionResult。"""
        result = analyzer.analyze(drill_downs=sample_drill_downs, total_change=-150000)
        assert isinstance(result, AttributionResult)
        assert result.total_change == -150000

    def test_analyze_dimensions_sorted(
        self, analyzer: AttributionAnalyzer, sample_drill_downs: list[DrillDownResult]
    ) -> None:
        """归因维度按贡献度绝对值降序排列。"""
        result = analyzer.analyze(drill_downs=sample_drill_downs, total_change=-150000)
        contributions = [abs(d["contribution"]) for d in result.dimensions]
        assert contributions == sorted(contributions, reverse=True)

    def test_analyze_has_key_drivers(self, analyzer: AttributionAnalyzer, sample_drill_downs: list[DrillDownResult]) -> None:
        """归因分析有关键驱动因素。"""
        result = analyzer.analyze(drill_downs=sample_drill_downs, total_change=-150000)
        assert len(result.key_drivers) > 0


# ==================================================================
# Key Drivers 提取
# ==================================================================


class TestKeyDriversExtraction:
    """关键驱动因素提取测试。"""

    @pytest.fixture()
    def analyzer(self) -> AttributionAnalyzer:
        """归因分析器。"""
        return AttributionAnalyzer()

    def test_empty_dimensions(self, analyzer: AttributionAnalyzer) -> None:
        """空维度列表返回空 key_drivers。"""
        result = analyzer.analyze(drill_downs=[], total_change=-100)
        assert result.key_drivers == []

    def test_single_driver(self, analyzer: AttributionAnalyzer) -> None:
        """单个维度值贡献 100%。"""
        dv = DimensionValue(
            value="华东", current=500, baseline=1000,
            change=-500, change_percent=-50.0,
            contribution=-500, contribution_percent=100.0,
        )
        dd = _make_drill_down("地区", [dv])
        result = analyzer.analyze(drill_downs=[dd], total_change=-500)
        assert result.key_drivers == ["地区:华东"]

    def test_80_percent_threshold(self, analyzer: AttributionAnalyzer) -> None:
        """80% 阈值测试。"""
        # 城市维度，贡献度按绝对值排序：上海 80000 > 深圳 30000 > 北京 20000 = 广州 20000
        city_values = [
            DimensionValue(
                value="上海", current=500000, baseline=580000,
                change=-80000, change_percent=-13.79,
                contribution=-80000, contribution_percent=53.33,
            ),
            DimensionValue(
                value="北京", current=200000, baseline=220000,
                change=-20000, change_percent=-9.09,
                contribution=-20000, contribution_percent=13.33,
            ),
            DimensionValue(
                value="广州", current=100000, baseline=120000,
                change=-20000, change_percent=-16.67,
                contribution=-20000, contribution_percent=13.33,
            ),
            DimensionValue(
                value="深圳", current=50000, baseline=80000,
                change=-30000, change_percent=-37.5,
                contribution=-30000, contribution_percent=20.0,
            ),
        ]
        dd = _make_drill_down("城市", city_values)
        result = analyzer.analyze(drill_downs=[dd], total_change=-150000)

        # 上海 80000 + 深圳 30000 = 110000 / 150000 = 73.3%，不够
        # 加上北京 20000 = 130000 / 150000 = 86.7%，超过 80%
        assert "城市:上海" in result.key_drivers
        assert "城市:深圳" in result.key_drivers
        assert "城市:北京" in result.key_drivers

    def test_key_drivers_format(self, analyzer: AttributionAnalyzer) -> None:
        """key_drivers 格式为 "维度名:维度值"。"""
        dv = DimensionValue(
            value="电子产品", current=400, baseline=500,
            change=-100, change_percent=-20.0,
            contribution=-100, contribution_percent=100.0,
        )
        dd = _make_drill_down("品类", [dv])
        result = analyzer.analyze(drill_downs=[dd], total_change=-100)
        assert result.key_drivers == ["品类:电子产品"]


# ==================================================================
# 多维度归因
# ==================================================================


class TestMultiDimensionAttribution:
    """多维度归因分析测试。"""

    @pytest.fixture()
    def analyzer(self) -> AttributionAnalyzer:
        """归因分析器。"""
        return AttributionAnalyzer()

    def test_cross_dimension_drivers(self, analyzer: AttributionAnalyzer) -> None:
        """跨维度驱动因素。"""
        city_dv = DimensionValue(
            value="上海", current=500000, baseline=580000,
            change=-80000, change_percent=-13.79,
            contribution=-80000, contribution_percent=53.33,
        )
        category_dv = DimensionValue(
            value="电子产品", current=400000, baseline=500000,
            change=-100000, change_percent=-20.0,
            contribution=-100000, contribution_percent=66.67,
        )
        city_dd = _make_drill_down("城市", [city_dv])
        category_dd = _make_drill_down("品类", [category_dv])
        result = analyzer.analyze(drill_downs=[city_dd, category_dd], total_change=-150000)

        # 应包含两个维度的贡献
        assert len(result.dimensions) == 2
        assert len(result.key_drivers) >= 1

    def test_total_change_positive(self, analyzer: AttributionAnalyzer) -> None:
        """正向总变化。"""
        dv = DimensionValue(
            value="华东", current=1000, baseline=800,
            change=200, change_percent=25.0,
            contribution=200, contribution_percent=100.0,
        )
        dd = _make_drill_down("地区", [dv])
        result = analyzer.analyze(drill_downs=[dd], total_change=200)
        assert result.total_change == 200
        assert all(d["contribution"] > 0 for d in result.dimensions)

    def test_zero_total_change(self, analyzer: AttributionAnalyzer) -> None:
        """总变化为零。"""
        dv = DimensionValue(
            value="A", current=100, baseline=100,
            change=0, change_percent=0.0,
            contribution=0, contribution_percent=0.0,
        )
        dd = _make_drill_down("维度", [dv])
        result = analyzer.analyze(drill_downs=[dd], total_change=0)
        assert result.total_change == 0
        assert result.key_drivers == []

    def test_multiple_values_across_dimensions(self, analyzer: AttributionAnalyzer) -> None:
        """多个维度多个值混合归因。"""
        dv1 = DimensionValue(
            value="上海", current=500, baseline=600,
            change=-100, change_percent=-16.67,
            contribution=-100, contribution_percent=50.0,
        )
        dv2 = DimensionValue(
            value="北京", current=400, baseline=400,
            change=0, change_percent=0.0,
            contribution=0, contribution_percent=0.0,
        )
        dv3 = DimensionValue(
            value="电子产品", current=300, baseline=500,
            change=-200, change_percent=-40.0,
            contribution=-200, contribution_percent=100.0,
        )
        dd_city = _make_drill_down("城市", [dv1, dv2])
        dd_cat = _make_drill_down("品类", [dv3])
        result = analyzer.analyze(drill_downs=[dd_city, dd_cat], total_change=-200)
        # 总维度数: 3
        assert len(result.dimensions) == 3
        # 电子产品贡献最大，应排第一
        assert result.dimensions[0]["value"] == "电子产品"

    def test_extract_key_drivers_custom_threshold(self) -> None:
        """自定义 80% 阈值的 key drivers 提取。"""
        analyzer = AttributionAnalyzer()
        dimensions = [
            {"dimension": "D", "value": "A", "contribution": -60},
            {"dimension": "D", "value": "B", "contribution": -20},
            {"dimension": "D", "value": "C", "contribution": -10},
            {"dimension": "D", "value": "D", "contribution": -10},
        ]
        # 60 + 20 = 80 / 100 = 80%，恰好达到阈值，取 A 和 B
        drivers = analyzer._extract_key_drivers(dimensions, threshold_percent=0.8)
        assert drivers == ["D:A", "D:B"]
