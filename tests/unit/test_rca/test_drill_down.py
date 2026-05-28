"""维度下钻分析器单元测试。"""
from __future__ import annotations

import pytest

from datapilot_agent.rca.drill_down import DimensionDrillDown
from datapilot_agent.rca.models import DimensionValue, DrillDownResult


# ==================================================================
# 基本下钻
# ==================================================================


class TestDimensionDrillDownBasic:
    """维度下钻基本功能测试。"""

    @pytest.fixture()
    def drill_down(self) -> DimensionDrillDown:
        """下钻分析器。"""
        return DimensionDrillDown()

    @pytest.mark.asyncio()
    async def test_drill_city_dimension(self, drill_down: DimensionDrillDown) -> None:
        """按城市维度下钻。"""
        result = await drill_down.drill(
            dimension_name="城市",
            dimension_values={"上海": 500000, "北京": 200000, "广州": 100000, "深圳": 50000},
            baseline_values={"上海": 580000, "北京": 220000, "广州": 120000, "深圳": 80000},
            total_change=-150000,
        )
        assert result.dimension_name == "城市"
        assert len(result.values) == 4
        assert len(result.top_contributors) == 4

    @pytest.mark.asyncio()
    async def test_drill_values_sorted_by_contribution(self, drill_down: DimensionDrillDown) -> None:
        """结果按 |contribution| 降序排列。"""
        result = await drill_down.drill(
            dimension_name="城市",
            dimension_values={"上海": 500000, "北京": 200000, "广州": 100000, "深圳": 50000},
            baseline_values={"上海": 580000, "北京": 220000, "广州": 120000, "深圳": 80000},
            total_change=-150000,
        )
        contributions = [abs(v.contribution) for v in result.values]
        assert contributions == sorted(contributions, reverse=True)


# ==================================================================
# 贡献度计算
# ==================================================================


class TestContributionCalculation:
    """贡献度计算测试。"""

    @pytest.fixture()
    def drill_down(self) -> DimensionDrillDown:
        """下钻分析器。"""
        return DimensionDrillDown()

    def test_calculate_contribution_normal(self, drill_down: DimensionDrillDown) -> None:
        """正常贡献度计算。"""
        contribution, percent = drill_down._calculate_contribution(500000, 580000, -150000)
        assert contribution == -80000
        # contribution / abs(total_change) * 100 = -80000 / 150000 * 100 = -53.33
        assert percent == pytest.approx(-53.33, abs=0.01)

    def test_calculate_contribution_zero_total(self, drill_down: DimensionDrillDown) -> None:
        """总变化为零时贡献百分比为零。"""
        contribution, percent = drill_down._calculate_contribution(500000, 580000, 0)
        assert contribution == -80000
        assert percent == 0.0

    def test_calculate_contribution_positive(self, drill_down: DimensionDrillDown) -> None:
        """正向贡献。"""
        contribution, percent = drill_down._calculate_contribution(300000, 200000, 150000)
        assert contribution == 100000
        assert percent == pytest.approx(66.67, abs=0.01)

    @pytest.mark.asyncio()
    async def test_shanghai_is_top_contributor(self, drill_down: DimensionDrillDown) -> None:
        """上海是最大贡献者。"""
        result = await drill_down.drill(
            dimension_name="城市",
            dimension_values={"上海": 500000, "北京": 200000},
            baseline_values={"上海": 580000, "北京": 220000},
            total_change=-100000,
        )
        # 上海 |contribution| = 80000 > 北京 |contribution| = 20000
        assert result.top_contributors[0].value == "上海"


# ==================================================================
# 维度值变化量
# ==================================================================


class TestDimensionValueChange:
    """维度值变化量计算测试。"""

    @pytest.fixture()
    def drill_down(self) -> DimensionDrillDown:
        """下钻分析器。"""
        return DimensionDrillDown()

    @pytest.mark.asyncio()
    async def test_change_calculation(self, drill_down: DimensionDrillDown) -> None:
        """变化量计算正确。"""
        result = await drill_down.drill(
            dimension_name="品类",
            dimension_values={"电子产品": 400000, "服装": 250000, "食品": 200000},
            baseline_values={"电子产品": 500000, "服装": 280000, "食品": 220000},
            total_change=-150000,
        )
        # 电子产品: 400000 - 500000 = -100000
        elec = next(v for v in result.values if v.value == "电子产品")
        assert elec.change == -100000
        assert elec.change_percent == pytest.approx(-20.0, abs=0.01)

    @pytest.mark.asyncio()
    async def test_change_percent_zero_baseline(self, drill_down: DimensionDrillDown) -> None:
        """基线为零时变化百分比。"""
        result = await drill_down.drill(
            dimension_name="渠道",
            dimension_values={"新渠道": 1000},
            baseline_values={"新渠道": 0},
            total_change=1000,
        )
        assert result.values[0].change_percent == 100.0

    @pytest.mark.asyncio()
    async def test_change_percent_both_zero(self, drill_down: DimensionDrillDown) -> None:
        """当前和基线都为零。"""
        result = await drill_down.drill(
            dimension_name="渠道",
            dimension_values={"渠道A": 0},
            baseline_values={"渠道A": 0},
            total_change=0,
        )
        assert result.values[0].change == 0.0
        assert result.values[0].change_percent == 0.0


# ==================================================================
# 边界情况
# ==================================================================


class TestDrillDownEdgeCases:
    """维度下钻边界情况测试。"""

    @pytest.fixture()
    def drill_down(self) -> DimensionDrillDown:
        """下钻分析器。"""
        return DimensionDrillDown()

    @pytest.mark.asyncio()
    async def test_empty_dimension(self, drill_down: DimensionDrillDown) -> None:
        """空维度数据。"""
        result = await drill_down.drill(
            dimension_name="空维度",
            dimension_values={},
            baseline_values={},
            total_change=-100,
        )
        assert result.dimension_name == "空维度"
        assert result.values == []
        assert result.top_contributors == []

    @pytest.mark.asyncio()
    async def test_mismatched_keys(self, drill_down: DimensionDrillDown) -> None:
        """维度键不一致时合并。"""
        result = await drill_down.drill(
            dimension_name="城市",
            dimension_values={"上海": 500000, "北京": 200000},
            baseline_values={"上海": 580000, "深圳": 80000},
            total_change=-160000,
        )
        assert len(result.values) == 3
        values_dict = {v.value: v for v in result.values}
        assert "上海" in values_dict
        assert "北京" in values_dict
        assert "深圳" in values_dict
        # 深圳当前值应为 0（缺失时默认 0）
        assert values_dict["深圳"].current == 0.0

    @pytest.mark.asyncio()
    async def test_single_value(self, drill_down: DimensionDrillDown) -> None:
        """单个维度值。"""
        result = await drill_down.drill(
            dimension_name="地区",
            dimension_values={"全国": 1000000},
            baseline_values={"全国": 1000000},
            total_change=0,
        )
        assert len(result.values) == 1
        assert result.values[0].change == 0.0
        assert result.values[0].contribution == 0.0

    @pytest.mark.asyncio()
    async def test_all_positive_changes(self, drill_down: DimensionDrillDown) -> None:
        """所有维度值都增长。"""
        result = await drill_down.drill(
            dimension_name="品类",
            dimension_values={"A": 600, "B": 300},
            baseline_values={"A": 500, "B": 200},
            total_change=200,
        )
        assert all(v.change > 0 for v in result.values)
        assert all(v.contribution > 0 for v in result.values)

    @pytest.mark.asyncio()
    async def test_contribution_percent_sum(self, drill_down: DimensionDrillDown) -> None:
        """贡献百分比之和应等于 100%（或 -100%）。"""
        result = await drill_down.drill(
            dimension_name="品类",
            dimension_values={"A": 400, "B": 350},
            baseline_values={"A": 500, "B": 300},
            total_change=-50,
        )
        total_pct = sum(v.contribution_percent for v in result.values)
        assert total_pct == pytest.approx(-100.0, abs=0.01)

    @pytest.mark.asyncio()
    async def test_top_contributors_same_as_values(self, drill_down: DimensionDrillDown) -> None:
        """top_contributors 应与 values 内容相同（当前实现为同一列表）。"""
        result = await drill_down.drill(
            dimension_name="城市",
            dimension_values={"上海": 500, "北京": 200},
            baseline_values={"上海": 600, "北京": 250},
            total_change=-150,
        )
        assert len(result.top_contributors) == len(result.values)
        for tc, v in zip(result.top_contributors, result.values):
            assert tc.value == v.value
            assert tc.contribution == v.contribution
