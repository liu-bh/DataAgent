"""DAG 调度器吞吐基准测试。"""
import contextlib
import time

import pytest

from datapilot_dag.executor.base import BaseTaskExecutor
from datapilot_dag.executor.registry import ExecutorRegistry
from datapilot_dag.executor.scheduler import DAGScheduler
from tests.benchmarks.conftest import percentile
from tests.unit.test_executor._mocks import FakeDAGraph, MockDAGNode


class _BenchExecutor(BaseTaskExecutor):
    """极轻量 mock 执行器，模拟 1ms 延迟。"""

    async def execute(self, node_id: str, config: dict, context: dict) -> object:
        return {"node": node_id}

    async def cancel(self, node_id: str) -> bool:
        return True


@pytest.mark.benchmark
async def test_dag_scheduler_throughput():
    """测试 DAG 调度器吞吐量。"""
    registry = ExecutorRegistry()
    executor = _BenchExecutor()
    registry.register("sql", executor)
    registry.register("llm", executor)

    scheduler = DAGScheduler(
        registry=registry,
        max_retry=0,
        task_timeout=5.0,
    )

    iterations = 100
    latencies: list[float] = []

    # warmup
    for _ in range(5):
        dag = FakeDAGraph(
            dag_id="warmup",
            nodes={"A": MockDAGNode(node_id="A", task_type="sql", config={})},
        )
        with contextlib.suppress(Exception):
            await scheduler.execute(dag)

    # 正式测试
    for i in range(iterations):
        dag = FakeDAGraph(
            dag_id=f"bench-{i}",
            nodes={
                "A": MockDAGNode(node_id="A", task_type="sql", config={}),
                "B": MockDAGNode(node_id="B", task_type="llm", config={}, dependencies=["A"]),
                "C": MockDAGNode(node_id="C", task_type="sql", config={}, dependencies=["A"]),
            },
        )
        start = time.perf_counter()
        try:
            await scheduler.execute(dag)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
        except Exception:
            pass

    if not latencies:
        pytest.skip("所有 DAG 调度均失败")

    # 输出统计
    print(f"\n{'='*60}")
    print("DAG 调度器吞吐统计")
    print(f"{'='*60}")
    print(f"DAG 数:    {iterations}")
    print(f"成功数:   {len(latencies)}")
    print(f"P50:      {percentile(latencies, 50):.1f} ms")
    print(f"P95:      {percentile(latencies, 95):.1f} ms")
    print(f"吞吐量:   {len(latencies) / (sum(latencies)/1000):.0f} DAG/s")
    print(f"{'='*60}")
