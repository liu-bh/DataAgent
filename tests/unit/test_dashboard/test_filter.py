"""Dashboard 过滤器测试。

覆盖 select、multi_select 过滤、过滤器验证、
空数据/空过滤边界情况。
"""

from __future__ import annotations

import pytest

from datapilot_chart.dashboard.filter import DashboardFilter
from datapilot_chart.dashboard.models import DashboardFilterDef


@pytest.fixture
def dashboard_filter() -> DashboardFilter:
    """创建过滤器实例。"""
    return DashboardFilter()


@pytest.fixture
def sample_data() -> list[dict]:
    """创建测试数据。"""
    return [
        {"region": "北京", "status": "active", "amount": 100},
        {"region": "上海", "status": "inactive", "amount": 200},
        {"region": "北京", "status": "active", "amount": 300},
        {"region": "广州", "status": "pending", "amount": 150},
        {"region": "上海", "status": "active", "amount": 250},
    ]


@pytest.fixture
def sample_filter_defs() -> list[DashboardFilterDef]:
    """创建测试过滤器定义。"""
    return [
        DashboardFilterDef(
            filter_id="region_filter",
            field="region",
            label="地区",
            filter_type="select",
            options=["北京", "上海", "广州"],
        ),
        DashboardFilterDef(
            filter_id="status_filter",
            field="status",
            label="状态",
            filter_type="multi_select",
            options=["active", "inactive", "pending"],
        ),
    ]


class TestApplySelectFilter:
    """select 过滤器应用测试。"""

    def test_filter_by_region(self, dashboard_filter: DashboardFilter, sample_data: list[dict], sample_filter_defs: list[DashboardFilterDef]) -> None:
        """按地区过滤。"""
        result = dashboard_filter.apply(sample_data, {"region_filter": "北京"}, sample_filter_defs)
        assert len(result) == 2
        assert all(r["region"] == "北京" for r in result)

    def test_filter_by_region_with_defs(self, dashboard_filter: DashboardFilter, sample_data: list[dict], sample_filter_defs: list[DashboardFilterDef]) -> None:
        """使用过滤器定义按地区过滤。"""
        result = dashboard_filter.apply(
            sample_data, {"region_filter": "上海"}, sample_filter_defs
        )
        assert len(result) == 2
        assert all(r["region"] == "上海" for r in result)

    def test_filter_no_match(self, dashboard_filter: DashboardFilter, sample_data: list[dict]) -> None:
        """过滤结果为空。"""
        result = dashboard_filter.apply(sample_data, {"region_filter": "深圳"})
        assert len(result) == 0


class TestApplyMultiSelectFilter:
    """multi_select 过滤器应用测试。"""

    def test_filter_by_multiple_statuses(self, dashboard_filter: DashboardFilter, sample_data: list[dict], sample_filter_defs: list[DashboardFilterDef]) -> None:
        """多选过滤。"""
        result = dashboard_filter.apply(
            sample_data,
            {"status_filter": ["active", "pending"]},
            sample_filter_defs,
        )
        assert len(result) == 4
        statuses = {r["status"] for r in result}
        assert statuses == {"active", "pending"}

    def test_filter_single_value_multi_select(self, dashboard_filter: DashboardFilter, sample_data: list[dict], sample_filter_defs: list[DashboardFilterDef]) -> None:
        """多选过滤器传入单个值。"""
        result = dashboard_filter.apply(
            sample_data,
            {"status_filter": "active"},
            sample_filter_defs,
        )
        assert len(result) == 3
        assert all(r["status"] == "active" for r in result)


class TestApplyCombinedFilters:
    """组合过滤器测试。"""

    def test_combined_filters(self, dashboard_filter: DashboardFilter, sample_data: list[dict], sample_filter_defs: list[DashboardFilterDef]) -> None:
        """同时应用多个过滤器。"""
        result = dashboard_filter.apply(
            sample_data,
            {
                "region_filter": "北京",
                "status_filter": ["active"],
            },
            sample_filter_defs,
        )
        assert len(result) == 2
        assert all(r["region"] == "北京" and r["status"] == "active" for r in result)


class TestFilterWithoutDefs:
    """不使用过滤器定义测试。"""

    def test_filter_by_field_name_directly(self, dashboard_filter: DashboardFilter, sample_data: list[dict]) -> None:
        """直接用字段名过滤。"""
        result = dashboard_filter.apply(sample_data, {"region": "广州"})
        assert len(result) == 1
        assert result[0]["region"] == "广州"


class TestEmptyData:
    """空数据边界测试。"""

    def test_empty_data(self, dashboard_filter: DashboardFilter) -> None:
        """空数据列表应返回空列表。"""
        result = dashboard_filter.apply([], {"region": "北京"})
        assert result == []

    def test_empty_filters(self, dashboard_filter: DashboardFilter, sample_data: list[dict]) -> None:
        """空过滤器应返回原始数据。"""
        result = dashboard_filter.apply(sample_data, {})
        assert result == sample_data

    def test_none_filter_value_skipped(self, dashboard_filter: DashboardFilter, sample_data: list[dict]) -> None:
        """None 过滤值应跳过。"""
        result = dashboard_filter.apply(sample_data, {"region": None})
        assert len(result) == 5


class TestValidateFilters:
    """过滤器验证测试。"""

    def test_valid_filters(self, dashboard_filter: DashboardFilter, sample_filter_defs: list[DashboardFilterDef]) -> None:
        """合法过滤器值应无问题。"""
        issues = dashboard_filter.validate(
            {"region_filter": "北京", "status_filter": ["active"]},
            sample_filter_defs,
        )
        assert issues == []

    def test_unknown_filter_id(self, dashboard_filter: DashboardFilter, sample_filter_defs: list[DashboardFilterDef]) -> None:
        """未知过滤器 ID 应报错。"""
        issues = dashboard_filter.validate(
            {"unknown_filter": "value"},
            sample_filter_defs,
        )
        assert any("未知" in i for i in issues)

    def test_multi_select_not_list(self, dashboard_filter: DashboardFilter, sample_filter_defs: list[DashboardFilterDef]) -> None:
        """multi_select 类型传非列表值应报错。"""
        issues = dashboard_filter.validate(
            {"status_filter": "active"},
            sample_filter_defs,
        )
        assert any("不是列表" in i for i in issues)

    def test_value_not_in_options(self, dashboard_filter: DashboardFilter, sample_filter_defs: list[DashboardFilterDef]) -> None:
        """过滤值不在可选项中应报错。"""
        issues = dashboard_filter.validate(
            {"region_filter": "成都"},
            sample_filter_defs,
        )
        assert any("不在可选项" in i for i in issues)

    def test_empty_validation(self, dashboard_filter: DashboardFilter, sample_filter_defs: list[DashboardFilterDef]) -> None:
        """空过滤器应验证通过。"""
        issues = dashboard_filter.validate({}, sample_filter_defs)
        assert issues == []
