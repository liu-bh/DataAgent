"""Python DAG 端到端集成测试。

测试 Python 任务在完整 DAG 流水线中的行为：
- 简单 Python 计算任务
- Python 任务接收上游数据
- Python 代码错误的处理
- 超时在 DAG 中的处理
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from datapilot_dag.executor.python_executor import PythonTaskExecutor
from datapilot_dag.executor.registry import ExecutorRegistry
from datapilot_dag.executor.result import TaskStatus
from datapilot_dag.executor.scheduler import DAGScheduler

# ---------------------------------------------------------------------------
# DAG Mock 工具
# ---------------------------------------------------------------------------


@dataclass
class DAGNode:
    """模拟 DAGNode（与 scheduler 的 _should_skip 兼容）。"""

    node_id: str
    task_type: str = "python"
    config: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    condition: str = ""


@dataclass
class DAGraph:
    """模拟 DAGraph（提供 topological_levels 接口）。"""

    dag_id: str
    nodes: dict[str, DAGNode] = field(default_factory=dict)

    def topological_levels(self) -> list[list[str]]:
        """返回拓扑排序的层级列表。"""
        if not self.nodes:
            return []

        remaining = set(self.nodes.keys())
        levels: list[list[str]] = []

        while remaining:
            level = [
                nid
                for nid in remaining
                if all(dep not in remaining for dep in self.nodes[nid].dependencies)
            ]
            if not level:
                level = list(remaining)
            levels.append(sorted(level))
            remaining -= set(level)

        return levels


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def python_executor() -> PythonTaskExecutor:
    """创建无沙箱的 PythonTaskExecutor。"""
    return PythonTaskExecutor()


@pytest.fixture
def python_registry(python_executor: PythonTaskExecutor) -> ExecutorRegistry:
    """创建注册了 Python 执行器的注册表。"""
    registry = ExecutorRegistry()
    registry.register("python", python_executor)
    return registry


@pytest.fixture
def python_scheduler(python_registry: ExecutorRegistry) -> DAGScheduler:
    """创建使用 Python 注册表的调度器。"""
    return DAGScheduler(
        registry=python_registry,
        max_retry=1,  # 集成测试减少重试次数
        task_timeout=5.0,
    )


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------


class TestPythonDAG:
    """Python DAG 端到端测试。"""

    @pytest.mark.asyncio
    async def test_simple_python_task(self, python_scheduler: DAGScheduler) -> None:
        """测试单个 Python 计算任务。"""
        dag = DAGraph(
            dag_id="test-simple-python",
            nodes={
                "calc": DAGNode(
                    node_id="calc",
                    task_type="python",
                    config={
                        "code": "result = 40 + 2\nprint(result)",
                    },
                ),
            },
        )

        result = await python_scheduler.execute(dag)

        assert result.status == TaskStatus.COMPLETED.value
        assert "calc" in result.task_results
        assert result.task_results["calc"].status == TaskStatus.COMPLETED.value

        output = result.task_results["calc"].output
        assert output["success"] is True
        assert "42" in output["stdout"]

    @pytest.mark.asyncio
    async def test_python_with_data_context(self, python_scheduler: DAGScheduler) -> None:
        """测试 Python 任务接收上游数据。

        DAG 结构：sql_node -> python_node
        sql_node 返回 mock 结果，python_node 从上下文中读取。
        """
        from datapilot_dag.executor.sql_executor import SQLTaskExecutor

        # 创建带 SQL 和 Python 执行器的注册表
        registry = ExecutorRegistry()
        registry.register("sql", SQLTaskExecutor(base_url="http://nonexistent:8003"))
        registry.register("python", PythonTaskExecutor())

        scheduler = DAGScheduler(
            registry=registry,
            max_retry=1,
            task_timeout=5.0,
        )

        dag = DAGraph(
            dag_id="test-python-with-context",
            nodes={
                "sql_query": DAGNode(
                    node_id="sql_query",
                    task_type="sql",
                    config={"sql": "SELECT 42 AS answer", "dialect": "postgres"},
                ),
                "python_process": DAGNode(
                    node_id="python_process",
                    task_type="python",
                    config={
                        "code": (
                            "upstream = context.get('__result_sql_query', {})\n"
                            "print('upstream_data_received:', type(upstream).__name__)\n"
                            "print('has_mock_key:', 'mock' in upstream if isinstance(upstream, dict) else False)"
                        ),
                    },
                    dependencies=["sql_query"],
                ),
            },
        )

        result = await scheduler.execute(dag)

        assert result.status == TaskStatus.COMPLETED.value
        assert result.task_results["sql_query"].status == TaskStatus.COMPLETED.value
        assert result.task_results["python_process"].status == TaskStatus.COMPLETED.value

        python_output = result.task_results["python_process"].output
        assert python_output["success"] is True
        assert "upstream_data_received:" in python_output["stdout"]
        assert "has_mock_key:" in python_output["stdout"]

    @pytest.mark.asyncio
    async def test_python_error_handling(self, python_scheduler: DAGScheduler) -> None:
        """测试 Python 代码错误的处理。

        DAG 中有一个运行时错误的 Python 任务。执行器返回 success=False，
        但不会抛出异常（节点状态为 COMPLETED，output 中 success=False）。
        """
        dag = DAGraph(
            dag_id="test-python-error",
            nodes={
                "broken": DAGNode(
                    node_id="broken",
                    task_type="python",
                    config={"code": "x = 1 / 0"},
                ),
            },
        )

        result = await python_scheduler.execute(dag)

        # Python 执行器内部捕获了错误并返回 success=False
        assert "broken" in result.task_results
        task_output = result.task_results["broken"].output
        assert task_output["success"] is False
        assert "ZeroDivisionError" in task_output["stderr"]

    @pytest.mark.asyncio
    async def test_python_dangerous_code_in_dag(self, python_scheduler: DAGScheduler) -> None:
        """测试 DAG 中的危险代码被拒绝。

        Python 执行器应拦截危险导入，节点状态应为 COMPLETED
        （执行器返回结果），但 output 中 success=False。
        """
        dag = DAGraph(
            dag_id="test-python-dangerous",
            nodes={
                "danger": DAGNode(
                    node_id="danger",
                    task_type="python",
                    config={"code": "import os\nos.system('echo hacked')"},
                ),
            },
        )

        result = await python_scheduler.execute(dag)

        assert "danger" in result.task_results
        task_output = result.task_results["danger"].output
        assert task_output["success"] is False
        assert "os" in task_output["stderr"]

    @pytest.mark.asyncio
    async def test_python_timeout_in_dag(self, python_scheduler: DAGScheduler) -> None:
        """测试超时在 DAG 中的处理。

        无限循环代码应在超时后被终止。
        """
        dag = DAGraph(
            dag_id="test-python-timeout",
            nodes={
                "infinite": DAGNode(
                    node_id="infinite",
                    task_type="python",
                    config={
                        "code": "while True:\n    x = 1",
                        "timeout": 1.0,
                    },
                ),
            },
        )

        result = await python_scheduler.execute(dag)

        assert "infinite" in result.task_results
        task_output = result.task_results["infinite"].output
        assert task_output["success"] is False
        assert "超时" in task_output["stderr"]

    @pytest.mark.asyncio
    async def test_multi_step_python_dag(self, python_scheduler: DAGScheduler) -> None:
        """测试多步骤 Python DAG：A -> B。

        A 计算结果，B 使用 A 的结果。
        """
        dag = DAGraph(
            dag_id="test-multi-python",
            nodes={
                "step_a": DAGNode(
                    node_id="step_a",
                    task_type="python",
                    config={"code": "result = 10 * 10\nprint(result)"},
                ),
                "step_b": DAGNode(
                    node_id="step_b",
                    task_type="python",
                    config={
                        "code": (
                            "upstream = context.get('__result_step_a', {})\n"
                            "if upstream.get('success'):\n"
                            "    print('UPSTREAM_OK')\n"
                            "else:\n"
                            "    print('UPSTREAM_FAIL')"
                        ),
                    },
                    dependencies=["step_a"],
                ),
            },
        )

        result = await python_scheduler.execute(dag)

        assert result.status == TaskStatus.COMPLETED.value
        assert result.task_results["step_a"].status == TaskStatus.COMPLETED.value
        assert result.task_results["step_b"].status == TaskStatus.COMPLETED.value

        # 验证 step_b 收到了 step_a 的结果
        step_b_output = result.task_results["step_b"].output
        assert step_b_output["success"] is True
        assert "UPSTREAM_OK" in step_b_output["stdout"]

    @pytest.mark.asyncio
    async def test_parallel_python_tasks(self, python_scheduler: DAGScheduler) -> None:
        """测试并行执行多个 Python 任务。

        DAG 结构：A -> [B, C]（B 和 C 并行）。
        """
        dag = DAGraph(
            dag_id="test-parallel-python",
            nodes={
                "root": DAGNode(
                    node_id="root",
                    task_type="python",
                    config={"code": "print('root')"},
                ),
                "branch_a": DAGNode(
                    node_id="branch_a",
                    task_type="python",
                    config={"code": "print('branch A')"},
                    dependencies=["root"],
                ),
                "branch_b": DAGNode(
                    node_id="branch_b",
                    task_type="python",
                    config={"code": "print('branch B')"},
                    dependencies=["root"],
                ),
            },
        )

        result = await python_scheduler.execute(dag)

        assert result.status == TaskStatus.COMPLETED.value
        assert result.task_results["root"].status == TaskStatus.COMPLETED.value
        assert result.task_results["branch_a"].status == TaskStatus.COMPLETED.value
        assert result.task_results["branch_b"].status == TaskStatus.COMPLETED.value

        assert "root" in result.task_results["root"].output["stdout"]
        assert "branch A" in result.task_results["branch_a"].output["stdout"]
        assert "branch B" in result.task_results["branch_b"].output["stdout"]

    @pytest.mark.asyncio
    async def test_execution_order_preserved(self, python_scheduler: DAGScheduler) -> None:
        """测试执行顺序记录。"""
        dag = DAGraph(
            dag_id="test-execution-order",
            nodes={
                "first": DAGNode(
                    node_id="first",
                    task_type="python",
                    config={"code": "print('first')"},
                ),
                "second": DAGNode(
                    node_id="second",
                    task_type="python",
                    config={"code": "print('second')"},
                    dependencies=["first"],
                ),
            },
        )

        result = await python_scheduler.execute(dag)

        # 验证执行顺序中包含所有节点
        assert "first" in result.execution_order
        assert "second" in result.execution_order
        # first 应该在 second 之前
        assert result.execution_order.index("first") < result.execution_order.index("second")
