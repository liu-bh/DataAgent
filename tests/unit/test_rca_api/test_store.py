"""RCA 分析记录存储单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 确保项目源码路径可被导入
project_root = Path(__file__).resolve().parent.parent.parent.parent / "services" / "agent-service" / "src"
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

libs_root = Path(__file__).resolve().parent.parent.parent.parent / "libs"
for lib_dir in libs_root.iterdir():
    if lib_dir.is_dir():
        lib_src = lib_dir / "src"
        if lib_src.exists() and str(lib_src) not in sys.path:
            sys.path.insert(0, str(lib_src))


from datapilot_agent.rca.models import (
    AnomalyResult,
    AttributionResult,
    DimensionValue,
    DrillDownResult,
    RCAReport,
)
from datapilot_agent.rca.store import RCAStore


# ---------------------------------------------------------------------------
# 测试辅助函数
# ---------------------------------------------------------------------------


def _make_report(
    analysis_id: str = "rca-test-001",
    question: str = "为什么销售额下降了？",
    metric_name: str = "销售额",
    change_percent: float = -15.0,
    execution_time_ms: float = 100.0,
) -> RCAReport:
    """创建测试用 RCA 报告。"""
    return RCAReport(
        analysis_id=analysis_id,
        question=question,
        anomaly=AnomalyResult(
            metric_name=metric_name,
            current_value=8500.0,
            baseline_value=10000.0,
            change_percent=change_percent,
            is_anomaly=True,
            anomaly_type="drop",
            confidence=0.9,
            direction="down",
        ),
        drill_downs=[
            DrillDownResult(
                dimension_name="城市",
                values=[
                    DimensionValue(
                        value="上海",
                        current=5000.0,
                        baseline=6000.0,
                        change=-1000.0,
                        change_percent=-16.7,
                        contribution=-1000.0,
                        contribution_percent=66.7,
                    )
                ],
                top_contributors=[
                    DimensionValue(
                        value="上海",
                        current=5000.0,
                        baseline=6000.0,
                        change=-1000.0,
                        change_percent=-16.7,
                        contribution=-1000.0,
                        contribution_percent=66.7,
                    )
                ],
            )
        ],
        attribution=AttributionResult(
            total_change=-1500.0,
            total_change_percent=-15.0,
            dimensions=[{"dimension": "城市", "contribution": -1000.0, "contribution_percent": 66.7}],
            key_drivers=["上海地区电子产品"],
        ),
        summary="上月销售额同比下降 15%",
        confidence=0.9,
        execution_time_ms=execution_time_ms,
    )


# ---------------------------------------------------------------------------
# 测试: RCAStore.save
# ---------------------------------------------------------------------------


class TestRCAStoreSave:
    """RCAStore.save 测试。"""

    def setup_method(self) -> None:
        """每个测试前创建新的 store。"""
        self.store = RCAStore()

    def test_save_returns_analysis_id(self) -> None:
        """save() 应返回 analysis_id。"""
        report = _make_report(analysis_id="rca-001")
        result = self.store.save(report)

        assert result == "rca-001"

    def test_save_stores_report(self) -> None:
        """save() 应正确存储报告。"""
        report = _make_report(analysis_id="rca-002")
        self.store.save(report)

        retrieved = self.store.get("rca-002")
        assert retrieved is not None
        assert retrieved.analysis_id == "rca-002"
        assert retrieved.question == "为什么销售额下降了？"

    def test_save_overwrite_existing(self) -> None:
        """使用相同 analysis_id 再次保存应覆盖。"""
        report1 = _make_report(analysis_id="rca-dup", question="旧问题")
        self.store.save(report1)

        report2 = _make_report(analysis_id="rca-dup", question="新问题")
        self.store.save(report2)

        retrieved = self.store.get("rca-dup")
        assert retrieved is not None
        assert retrieved.question == "新问题"
        assert self.store.size == 1


# ---------------------------------------------------------------------------
# 测试: RCAStore.get
# ---------------------------------------------------------------------------


class TestRCAStoreGet:
    """RCAStore.get 测试。"""

    def setup_method(self) -> None:
        """每个测试前创建新的 store。"""
        self.store = RCAStore()

    def test_get_existing_report(self) -> None:
        """get() 应返回已存在的报告。"""
        report = _make_report(analysis_id="rca-003")
        self.store.save(report)

        retrieved = self.store.get("rca-003")
        assert retrieved is not None
        assert retrieved.analysis_id == "rca-003"
        assert retrieved.anomaly.metric_name == "销售额"
        assert retrieved.anomaly.is_anomaly is True

    def test_get_nonexistent_report(self) -> None:
        """get() 对不存在的 analysis_id 应返回 None。"""
        result = self.store.get("nonexistent")
        assert result is None

    def test_get_preserves_all_fields(self) -> None:
        """get() 返回的报告应保留所有字段。"""
        report = _make_report(analysis_id="rca-004")
        self.store.save(report)

        retrieved = self.store.get("rca-004")
        assert retrieved is not None
        assert retrieved.anomaly.change_percent == -15.0
        assert retrieved.confidence == 0.9
        assert len(retrieved.drill_downs) == 1
        assert len(retrieved.attribution.key_drivers) == 1

    def test_get_preserves_direction_field(self) -> None:
        """get() 返回的报告应保留 direction 字段。"""
        report = _make_report(analysis_id="rca-005", change_percent=10.0)
        report.anomaly.direction = "up"
        self.store.save(report)

        retrieved = self.store.get("rca-005")
        assert retrieved is not None
        assert retrieved.anomaly.direction == "up"


# ---------------------------------------------------------------------------
# 测试: RCAStore.list_all
# ---------------------------------------------------------------------------


class TestRCAStoreListAll:
    """RCAStore.list_all 测试。"""

    def setup_method(self) -> None:
        """每个测试前创建新的 store。"""
        self.store = RCAStore()

    def test_list_all_empty_store(self) -> None:
        """空存储应返回空列表。"""
        result = self.store.list_all()
        assert result == []

    def test_list_all_returns_all_records(self) -> None:
        """应返回所有已保存的记录。"""
        for i in range(3):
            report = _make_report(analysis_id=f"rca-{i}")
            self.store.save(report)

        result = self.store.list_all()
        assert len(result) == 3

    def test_list_all_ordered_by_execution_time_desc(self) -> None:
        """应按执行时间倒序排列。"""
        report1 = _make_report(analysis_id="rca-old", execution_time_ms=50.0)
        self.store.save(report1)

        report2 = _make_report(analysis_id="rca-new", execution_time_ms=200.0)
        self.store.save(report2)

        result = self.store.list_all()
        assert len(result) == 2
        assert result[0].analysis_id == "rca-new"
        assert result[1].analysis_id == "rca-old"

    def test_list_all_respects_limit(self) -> None:
        """应遵守 limit 参数。"""
        for i in range(10):
            report = _make_report(analysis_id=f"rca-limit-{i}", execution_time_ms=float(i))
            self.store.save(report)

        result = self.store.list_all(limit=3)
        assert len(result) == 3

    def test_list_all_default_limit(self) -> None:
        """默认 limit 应为 50。"""
        for i in range(60):
            report = _make_report(analysis_id=f"rca-default-{i}", execution_time_ms=float(i))
            self.store.save(report)

        result = self.store.list_all()
        assert len(result) == 50


# ---------------------------------------------------------------------------
# 测试: RCAStore.delete
# ---------------------------------------------------------------------------


class TestRCAStoreDelete:
    """RCAStore.delete 测试。"""

    def setup_method(self) -> None:
        """每个测试前创建新的 store。"""
        self.store = RCAStore()

    def test_delete_existing_record(self) -> None:
        """删除存在的记录应返回 True。"""
        report = _make_report(analysis_id="rca-del")
        self.store.save(report)

        result = self.store.delete("rca-del")
        assert result is True
        assert self.store.get("rca-del") is None

    def test_delete_nonexistent_record(self) -> None:
        """删除不存在的记录应返回 False。"""
        result = self.store.delete("nonexistent")
        assert result is False

    def test_delete_reduces_size(self) -> None:
        """删除后存储大小应减少。"""
        for i in range(5):
            report = _make_report(analysis_id=f"rca-size-{i}")
            self.store.save(report)

        assert self.store.size == 5
        self.store.delete("rca-size-2")
        assert self.store.size == 4


# ---------------------------------------------------------------------------
# 测试: RCAStore.size
# ---------------------------------------------------------------------------


class TestRCAStoreSize:
    """RCAStore.size 测试。"""

    def test_size_initial_value(self) -> None:
        """新创建的 store size 应为 0。"""
        store = RCAStore()
        assert store.size == 0

    def test_size_after_save(self) -> None:
        """保存后 size 应增加。"""
        store = RCAStore()
        store.save(_make_report(analysis_id="rca-a"))
        assert store.size == 1
        store.save(_make_report(analysis_id="rca-b"))
        assert store.size == 2

    def test_size_after_delete(self) -> None:
        """删除后 size 应减少。"""
        store = RCAStore()
        store.save(_make_report(analysis_id="rca-x"))
        store.delete("rca-x")
        assert store.size == 0
