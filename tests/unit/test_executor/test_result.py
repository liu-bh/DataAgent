"""执行结果数据模型单元测试。"""

from __future__ import annotations

from datapilot_dag.executor.result import DAGResult, TaskResult, TaskStatus


class TestTaskStatus:
    """TaskStatus 枚举测试。"""

    def test_all_statuses_defined(self) -> None:
        """所有状态值都已定义。"""
        expected = {"pending", "running", "completed", "failed", "skipped", "cancelled"}
        actual = {s.value for s in TaskStatus}
        assert actual == expected

    def test_status_is_str_enum(self) -> None:
        """TaskStatus 是 StrEnum，可以直接比较字符串。"""
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.PENDING == "pending"


class TestTaskResult:
    """TaskResult 数据模型测试。"""

    def test_create_minimal(self) -> None:
        """最小参数创建。"""
        result = TaskResult(node_id="A", status=TaskStatus.COMPLETED.value)
        assert result.node_id == "A"
        assert result.status == "completed"
        assert result.output is None
        assert result.error == ""
        assert result.execution_time_ms == 0.0
        assert result.retries == 0

    def test_create_full(self) -> None:
        """完整参数创建。"""
        result = TaskResult(
            node_id="B",
            status="failed",
            output=None,
            error="连接超时",
            execution_time_ms=1500.5,
            retries=3,
            started_at=1000.0,
            completed_at=2500.5,
        )
        assert result.node_id == "B"
        assert result.status == "failed"
        assert result.error == "连接超时"
        assert result.execution_time_ms == 1500.5
        assert result.retries == 3
        assert result.started_at == 1000.0
        assert result.completed_at == 2500.5

    def test_create_with_output(self) -> None:
        """带输出结果创建。"""
        output = {"columns": ["name"], "rows": [{"name": "test"}]}
        result = TaskResult(
            node_id="A",
            status="completed",
            output=output,
        )
        assert result.output == output
        assert result.output["columns"] == ["name"]


class TestDAGResult:
    """DAGResult 数据模型测试。"""

    def test_create_minimal(self) -> None:
        """最小参数创建。"""
        result = DAGResult(
            dag_id="test-dag",
            status="completed",
        )
        assert result.dag_id == "test-dag"
        assert result.status == "completed"
        assert result.task_results == {}
        assert result.total_time_ms == 0.0
        assert result.error == ""
        assert result.execution_order == []

    def test_create_with_results(self) -> None:
        """带任务结果创建。"""
        task_a = TaskResult(node_id="A", status="completed", execution_time_ms=100.0)
        task_b = TaskResult(node_id="B", status="failed", error="超时", retries=2)

        result = DAGResult(
            dag_id="dag-1",
            status="failed",
            task_results={"A": task_a, "B": task_b},
            total_time_ms=5000.0,
            error="节点 B 超时",
            execution_order=["A", "B"],
        )
        assert result.dag_id == "dag-1"
        assert result.status == "failed"
        assert len(result.task_results) == 2
        assert result.task_results["A"].status == "completed"
        assert result.task_results["B"].error == "超时"
        assert result.total_time_ms == 5000.0
        assert result.execution_order == ["A", "B"]

    def test_task_results_mutable(self) -> None:
        """task_results 字典可以修改。"""
        result = DAGResult(dag_id="dag-1", status="running")
        result.task_results["A"] = TaskResult(node_id="A", status="completed")
        assert "A" in result.task_results
