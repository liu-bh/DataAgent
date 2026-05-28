"""DAG 执行记录存储单元测试。"""

from __future__ import annotations

import sys
import time
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


# ---------------------------------------------------------------------------
# 测试: DAGExecutionStore
# ---------------------------------------------------------------------------


class TestDAGExecutionStore:
    """DAGExecutionStore 单元测试。"""

    def setup_method(self) -> None:
        """每个测试前创建新的 store 实例。"""
        from datapilot_agent.dag.store import DAGExecutionStore

        self.store = DAGExecutionStore()

    def test_create_record(self) -> None:
        """create() 应创建一条 pending 状态的记录。"""
        record = self.store.create("dag-001", question="测试问题")

        assert record.dag_id == "dag-001"
        assert record.status == "pending"
        assert record.question == "测试问题"
        assert record.created_at > 0
        assert record.result is None

    def test_get_existing_record(self) -> None:
        """get() 应返回已存在的记录。"""
        self.store.create("dag-002", question="查询")
        record = self.store.get("dag-002")

        assert record is not None
        assert record.dag_id == "dag-002"
        assert record.question == "查询"

    def test_get_nonexistent_record(self) -> None:
        """get() 对不存在的 dag_id 应返回 None。"""
        record = self.store.get("nonexistent")
        assert record is None

    def test_update_record_status(self) -> None:
        """update() 应能更新记录状态。"""
        self.store.create("dag-003", question="测试")
        self.store.update("dag-003", status="running")

        record = self.store.get("dag-003")
        assert record is not None
        assert record.status == "running"

    def test_update_record_result(self) -> None:
        """update() 应能更新记录结果。"""
        self.store.create("dag-004")
        result_data = {"sql": "SELECT 1", "confidence": 0.9}
        self.store.update("dag-004", status="completed", result=result_data)

        record = self.store.get("dag-004")
        assert record is not None
        assert record.status == "completed"
        assert record.result == result_data

    def test_update_nonexistent_record_raises(self) -> None:
        """update() 对不存在的 dag_id 应抛出 KeyError。"""
        with pytest.raises(KeyError, match="不存在"):
            self.store.update("nonexistent", status="running")

    def test_update_completed_at(self) -> None:
        """update() 应能更新完成时间。"""
        self.store.create("dag-005")
        now = time.time()
        self.store.update("dag-005", status="completed", completed_at=now)

        record = self.store.get("dag-005")
        assert record is not None
        assert record.completed_at == now

    def test_list_records_ordered_by_created_at_desc(self) -> None:
        """list_records() 应按创建时间倒序返回记录。"""
        self.store.create("dag-010", question="第一个")
        time.sleep(0.01)  # 确保时间戳不同
        self.store.create("dag-011", question="第二个")
        time.sleep(0.01)
        self.store.create("dag-012", question="第三个")

        records = self.store.list_records()

        assert len(records) == 3
        assert records[0].dag_id == "dag-012"
        assert records[1].dag_id == "dag-011"
        assert records[2].dag_id == "dag-010"

    def test_list_records_respects_limit(self) -> None:
        """list_records() 应遵守 limit 参数。"""
        for i in range(10):
            self.store.create(f"dag-{i:03d}", question=f"问题{i}")

        records = self.store.list_records(limit=5)
        assert len(records) == 5

    def test_list_records_empty_store(self) -> None:
        """list_records() 在空存储时应返回空列表。"""
        records = self.store.list_records()
        assert records == []

    def test_cleanup_expired_records(self) -> None:
        """cleanup() 应清理超过最大保留时间的记录。"""
        self.store.create("old-dag", question="过期")
        # 手动将 created_at 设为很久以前
        self.store.update("old-dag", created_at=time.time() - 7200)

        self.store.create("new-dag", question="新的")

        removed_count = self.store.cleanup(max_age_seconds=3600)
        assert removed_count == 1
        assert self.store.get("old-dag") is None
        assert self.store.get("new-dag") is not None

    def test_cleanup_no_expired_records(self) -> None:
        """cleanup() 在没有过期记录时应返回 0。"""
        self.store.create("fresh-dag", question="新鲜的")

        removed_count = self.store.cleanup(max_age_seconds=3600)
        assert removed_count == 0

        record = self.store.get("fresh-dag")
        assert record is not None

    def test_size_property(self) -> None:
        """size 属性应反映存储中的记录数量。"""
        assert self.store.size == 0

        self.store.create("dag-a")
        assert self.store.size == 1

        self.store.create("dag-b")
        assert self.store.size == 2

        self.store.cleanup(max_age_seconds=0)
        assert self.store.size == 0

    def test_overwrite_existing_record_via_create(self) -> None:
        """create() 使用相同 dag_id 应覆盖已有记录。"""
        self.store.create("dag-dup", question="旧问题")
        self.store.update("dag-dup", status="completed")

        # 同一 dag_id 再次创建
        new_record = self.store.create("dag-dup", question="新问题")
        assert new_record.status == "pending"
        assert new_record.question == "新问题"
        assert self.store.size == 1
