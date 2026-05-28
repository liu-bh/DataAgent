"""DAG 调度器单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from datapilot_dag.executor.base import BaseTaskExecutor
from datapilot_dag.executor.registry import ExecutorRegistry
from datapilot_dag.executor.result import DAGResult, TaskResult, TaskStatus
from datapilot_dag.executor.scheduler import DAGScheduler

from tests.unit.test_executor._mocks import FakeDAGraph, MockDAGNode


class _MockExecutor(BaseTaskExecutor):
    """测试用 mock 执行器。"""

    def __init__(self, result: object = None, fail_count: int = 0) -> None:
        self._result = result or {"mock": True}
        self._fail_count = fail_count
        self._call_count = 0
        self._cancelled: set[str] = set()

    async def execute(self, node_id: str, config: dict, context: dict) -> object:
        self._call_count += 1
        if self._call_count <= self._fail_count:
            raise RuntimeError(f"模拟失败（第 {self._call_count} 次调用）")
        return self._result

    async def cancel(self, node_id: str) -> bool:
        self._cancelled.add(node_id)
        return True


class _SlowExecutor(BaseTaskExecutor):
    """模拟超时的慢执行器。"""

    async def execute(self, node_id: str, config: dict, context: dict) -> object:
        import asyncio
        await asyncio.sleep(100)
        return "never"

    async def cancel(self, node_id: str) -> bool:
        return True


class TestDAGScheduler:
    """DAGScheduler 调度器测试。"""

    def _make_scheduler(
        self,
        executors: dict[str, BaseTaskExecutor] | None = None,
        max_retry: int = 3,
        task_timeout: float = 30.0,
        max_depth: int = 5,
    ) -> DAGScheduler:
        """创建测试用调度器。"""
        registry = ExecutorRegistry()
        if executors:
            for task_type, executor in executors.items():
                registry.register(task_type, executor)
        return DAGScheduler(
            registry=registry,
            max_retry=max_retry,
            task_timeout=task_timeout,
            max_depth=max_depth,
        )

    @pytest.mark.asyncio
    async def test_execute_simple_dag(self, simple_dag: FakeDAGraph) -> None:
        """执行简单线性 DAG。"""
        executor = _MockExecutor(result={"value": 42})
        scheduler = self._make_scheduler(
            executors={"sql": executor, "llm": executor},
        )

        result = await scheduler.execute(simple_dag)

        assert result.status == TaskStatus.COMPLETED.value
        assert result.dag_id == "test-dag-1"
        assert len(result.task_results) == 3
        assert all(
            r.status == TaskStatus.COMPLETED.value
            for r in result.task_results.values()
        )

    @pytest.mark.asyncio
    async def test_execute_parallel_dag(self, parallel_dag: FakeDAGraph) -> None:
        """执行并行 DAG。"""
        executor = _MockExecutor(result={"ok": True})
        scheduler = self._make_scheduler(
            executors={"sql": executor, "llm": executor},
        )

        result = await scheduler.execute(parallel_dag)

        assert result.status == TaskStatus.COMPLETED.value
        assert len(result.task_results) == 4
        # 验证执行顺序：A 在 B、C 之前
        order = result.execution_order
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")

    @pytest.mark.asyncio
    async def test_execute_empty_dag(self) -> None:
        """执行空 DAG。"""
        scheduler = self._make_scheduler()
        dag = FakeDAGraph(dag_id="empty-dag", nodes={})

        result = await scheduler.execute(dag)

        assert result.status == TaskStatus.COMPLETED.value
        assert len(result.task_results) == 0

    @pytest.mark.asyncio
    async def test_retry_on_failure(self) -> None:
        """失败后重试。"""
        # 前 2 次失败，第 3 次成功
        executor = _MockExecutor(result={"recovered": True}, fail_count=2)
        scheduler = self._make_scheduler(
            executors={"sql": executor},
            max_retry=3,
        )

        dag = FakeDAGraph(
            dag_id="retry-dag",
            nodes={
                "A": MockDAGNode(node_id="A", task_type="sql", config={"sql": "SELECT 1"}),
            },
        )

        result = await scheduler.execute(dag)

        assert result.status == TaskStatus.COMPLETED.value
        task_result = result.task_results["A"]
        assert task_result.status == TaskStatus.COMPLETED.value
        assert task_result.retries == 2  # 重试了 2 次后成功

    @pytest.mark.asyncio
    async def test_exhaust_retries_fails(self) -> None:
        """重试次数用尽后标记为失败。"""
        executor = _MockExecutor(result=None, fail_count=99)
        scheduler = self._make_scheduler(
            executors={"sql": executor},
            max_retry=2,
        )

        dag = FakeDAGraph(
            dag_id="fail-dag",
            nodes={
                "A": MockDAGNode(node_id="A", task_type="sql", config={"sql": "SELECT 1"}),
            },
        )

        result = await scheduler.execute(dag)

        assert result.status == TaskStatus.FAILED.value
        task_result = result.task_results["A"]
        assert task_result.status == TaskStatus.FAILED.value
        assert task_result.retries == 3  # 1 次初始 + 2 次重试

    @pytest.mark.asyncio
    async def test_timeout_control(self) -> None:
        """任务超时控制。"""
        scheduler = self._make_scheduler(
            executors={"sql": _SlowExecutor()},
            max_retry=0,
            task_timeout=0.1,
        )

        dag = FakeDAGraph(
            dag_id="timeout-dag",
            nodes={
                "A": MockDAGNode(node_id="A", task_type="sql", config={"sql": "SELECT 1"}),
            },
        )

        result = await scheduler.execute(dag)

        assert result.status == TaskStatus.FAILED.value
        task_result = result.task_results["A"]
        assert task_result.status == TaskStatus.FAILED.value
        assert "超时" in task_result.error

    @pytest.mark.asyncio
    async def test_conditional_skip(self, conditional_dag: FakeDAGraph) -> None:
        """条件不满足时跳过节点。"""
        executor = _MockExecutor(result={"ok": True})
        scheduler = self._make_scheduler(
            executors={"sql": executor, "llm": executor},
        )

        # context 中 need_llm != true，B 会被跳过
        result = await scheduler.execute(conditional_dag, context={"need_llm": False})

        assert result.status == TaskStatus.COMPLETED.value
        # A 正常执行，B 被跳过
        assert result.task_results["A"].status == TaskStatus.COMPLETED.value
        assert result.task_results["B"].status == TaskStatus.SKIPPED.value

    @pytest.mark.asyncio
    async def test_conditional_pass(self, conditional_dag: FakeDAGraph) -> None:
        """条件满足时执行节点。"""
        executor = _MockExecutor(result={"ok": True})
        scheduler = self._make_scheduler(
            executors={"sql": executor, "llm": executor},
        )

        # context 中 need_llm == true，B 不会被跳过
        result = await scheduler.execute(conditional_dag, context={"need_llm": True})

        assert result.status == TaskStatus.COMPLETED.value
        assert result.task_results["A"].status == TaskStatus.COMPLETED.value
        assert result.task_results["B"].status == TaskStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_unknown_task_type_fails(self) -> None:
        """未注册的任务类型导致失败。"""
        scheduler = self._make_scheduler()

        dag = FakeDAGraph(
            dag_id="unknown-dag",
            nodes={
                "A": MockDAGNode(node_id="A", task_type="unknown", config={}),
            },
        )

        result = await scheduler.execute(dag)

        assert result.status == TaskStatus.FAILED.value
        task_result = result.task_results["A"]
        assert task_result.status == TaskStatus.FAILED.value
        assert "unknown" in task_result.error

    @pytest.mark.asyncio
    async def test_context_injection(self) -> None:
        """上游节点结果注入到 context 中。"""
        call_log: list[dict] = []

        class _ContextAwareExecutor(BaseTaskExecutor):
            async def execute(self, node_id: str, config: dict, context: dict) -> object:
                call_log.append({"node_id": node_id, "context_keys": list(context.keys())})
                return {"node": node_id}

            async def cancel(self, node_id: str) -> bool:
                return True

        scheduler = self._make_scheduler(
            executors={"sql": _ContextAwareExecutor(), "llm": _ContextAwareExecutor()},
        )

        dag = FakeDAGraph(
            dag_id="context-dag",
            nodes={
                "A": MockDAGNode(node_id="A", task_type="sql", config={}),
                "B": MockDAGNode(
                    node_id="B",
                    task_type="llm",
                    config={},
                    dependencies=["A"],
                ),
            },
        )

        result = await scheduler.execute(dag, context={"initial": "value"})

        assert result.status == TaskStatus.COMPLETED.value
        # B 执行时 context 中应包含 A 的结果
        b_context = [c for c in call_log if c["node_id"] == "B"][0]
        assert "__result_A" in b_context["context_keys"]
        # A 执行时 context 中应有 initial
        a_context = [c for c in call_log if c["node_id"] == "A"][0]
        assert "initial" in a_context["context_keys"]

    @pytest.mark.asyncio
    async def test_max_depth_exceeded(self) -> None:
        """DAG 深度超过限制时失败。"""
        scheduler = self._make_scheduler(max_depth=2)

        # 创建 3 层 DAG
        nodes = {
            "A": MockDAGNode(node_id="A", task_type="sql", config={}),
            "B": MockDAGNode(node_id="B", task_type="sql", config={}, dependencies=["A"]),
            "C": MockDAGNode(node_id="C", task_type="sql", config={}, dependencies=["B"]),
        }
        dag = FakeDAGraph(dag_id="deep-dag", nodes=nodes)

        result = await scheduler.execute(dag)

        assert result.status == TaskStatus.FAILED.value
        assert "最大限制" in result.error

    def test_evaluate_condition_always(self) -> None:
        """条件表达式 'always' 始终为 True。"""
        scheduler = self._make_scheduler()
        assert scheduler._evaluate_condition("always", {}, {}) is True

    def test_evaluate_condition_never(self) -> None:
        """条件表达式 'never' 始终为 False。"""
        scheduler = self._make_scheduler()
        assert scheduler._evaluate_condition("never", {}, {}) is False

    def test_evaluate_condition_context_key(self) -> None:
        """评估 context.key 表达式。"""
        scheduler = self._make_scheduler()
        assert scheduler._evaluate_condition("context.need_llm", {"need_llm": True}, {}) is True
        assert scheduler._evaluate_condition("context.need_llm", {"need_llm": False}, {}) is False
        assert scheduler._evaluate_condition("context.missing_key", {}, {}) is False

    def test_evaluate_condition_result_status(self) -> None:
        """评估 result.node_id.status 表达式。"""
        scheduler = self._make_scheduler()
        results = {
            "A": TaskResult(node_id="A", status="completed"),
            "B": TaskResult(node_id="B", status="failed"),
        }
        assert scheduler._evaluate_condition("result.A.status", {}, results) is True
        assert scheduler._evaluate_condition("result.B.status", {}, results) is False

    def test_evaluate_condition_result_status_value(self) -> None:
        """评估 result.node_id.status == value 表达式。"""
        scheduler = self._make_scheduler()
        results = {
            "A": TaskResult(node_id="A", status="failed"),
        }
        assert scheduler._evaluate_condition("result.A.status.failed", {}, results) is True
        assert scheduler._evaluate_condition("result.A.status.completed", {}, results) is False

    def test_should_skip_no_condition(self) -> None:
        """无条件表达式时不跳过。"""
        scheduler = self._make_scheduler()
        node = MockDAGNode(node_id="A", task_type="sql", config={})
        assert scheduler._should_skip(node, {}, {}) is False

    def test_should_skip_empty_condition(self) -> None:
        """空条件字符串时不跳过。"""
        scheduler = self._make_scheduler()
        node = MockDAGNode(node_id="A", task_type="sql", config={}, condition="")
        assert scheduler._should_skip(node, {}, {}) is False

    def test_register_defaults_integration(self) -> None:
        """使用默认注册表创建调度器。"""
        scheduler = DAGScheduler()
        assert scheduler._registry.has("sql")
        assert scheduler._registry.has("llm")
        assert scheduler._registry.has("python")

    @pytest.mark.asyncio
    async def test_execute_with_initial_context(self, simple_dag: FakeDAGraph) -> None:
        """传入初始 context。"""
        executor = _MockExecutor(result={"ok": True})
        scheduler = self._make_scheduler(executors={"sql": executor, "llm": executor})

        result = await scheduler.execute(simple_dag, context={"user_id": "u1", "tenant_id": "t1"})

        assert result.status == TaskStatus.COMPLETED.value
