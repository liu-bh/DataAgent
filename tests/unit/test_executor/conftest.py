"""执行器模块测试公共 fixtures。"""

from dataclasses import dataclass, field
from typing import Any

import pytest


# ---------- Track A 的 DAGNode / DAGraph mock ----------
# 当 Track A 的 models.py 不存在时，用这些 mock 替代


@dataclass
class MockDAGNode:
    """模拟 DAGNode。"""

    node_id: str
    task_type: str = "sql"
    config: dict = field(default_factory=dict)
    dependencies: list = field(default_factory=list)
    condition: str = ""


class MockDAGraph:
    """模拟 DAGraph。"""

    def __init__(self, dag_id: str, nodes: dict = None) -> None:
        self.dag_id = dag_id
        self.nodes: dict[str, MockDAGNode] = nodes or {}

    def topological_levels(self) -> list:
        """返回拓扑排序的层级列表。"""
        if not self.nodes:
            return []

        # 简单拓扑排序：按依赖关系分层
        remaining = set(self.nodes.keys())
        levels: list[list[str]] = []

        while remaining:
            # 找出没有未处理依赖的节点
            level = [
                nid for nid in remaining
                if all(dep not in remaining for dep in self.nodes[nid].dependencies)
            ]
            if not level:
                # 存在循环依赖，将剩余节点全部放入当前层
                level = list(remaining)
            levels.append(sorted(level))
            remaining -= set(level)

        return levels


@pytest.fixture
def mock_dag_graph() -> type[MockDAGraph]:
    """提供 MockDAGraph 类。"""
    return MockDAGraph


@pytest.fixture
def mock_dag_node() -> type[MockDAGNode]:
    """提供 MockDAGNode 类。"""
    return MockDAGNode


@pytest.fixture
def simple_dag(mock_dag_node: type[MockDAGNode], mock_dag_graph: type[MockDAGraph]) -> MockDAGraph:
    """创建简单的线性 DAG：A -> B -> C。"""
    node_a = mock_dag_node(node_id="A", task_type="sql", config={"sql": "SELECT 1"})
    node_b = mock_dag_node(
        node_id="B",
        task_type="llm",
        config={"prompt": "解释结果", "scene": "explanation"},
        dependencies=["A"],
    )
    node_c = mock_dag_node(
        node_id="C",
        task_type="sql",
        config={"sql": "SELECT 2"},
        dependencies=["B"],
    )
    return mock_dag_graph(
        dag_id="test-dag-1",
        nodes={"A": node_a, "B": node_b, "C": node_c},
    )


@pytest.fixture
def parallel_dag(mock_dag_node: type[MockDAGNode], mock_dag_graph: type[MockDAGraph]) -> MockDAGraph:
    """创建并行 DAG：A -> [B, C] -> D。"""
    node_a = mock_dag_node(node_id="A", task_type="sql", config={"sql": "SELECT 1"})
    node_b = mock_dag_node(
        node_id="B",
        task_type="llm",
        config={"prompt": "分析", "scene": "nl2sql"},
        dependencies=["A"],
    )
    node_c = mock_dag_node(
        node_id="C",
        task_type="sql",
        config={"sql": "SELECT 3"},
        dependencies=["A"],
    )
    node_d = mock_dag_node(
        node_id="D",
        task_type="llm",
        config={"prompt": "总结", "scene": "explanation"},
        dependencies=["B", "C"],
    )
    return mock_dag_graph(
        dag_id="test-dag-parallel",
        nodes={"A": node_a, "B": node_b, "C": node_c, "D": node_d},
    )


@pytest.fixture
def conditional_dag(
    mock_dag_node: type[MockDAGNode],
    mock_dag_graph: type[MockDAGraph],
) -> MockDAGGraph:
    """创建条件分支 DAG：A -> B (条件) -> C。"""
    node_a = mock_dag_node(node_id="A", task_type="sql", config={"sql": "SELECT 1"})
    node_b = mock_dag_node(
        node_id="B",
        task_type="llm",
        config={"prompt": "条件任务", "scene": "intent"},
        dependencies=["A"],
        condition="context.need_llm == true",
    )
    node_c = mock_dag_node(
        node_id="C",
        task_type="sql",
        config={"sql": "SELECT 2"},
        dependencies=["B"],
    )
    return mock_dag_graph(
        dag_id="test-dag-conditional",
        nodes={"A": node_a, "B": node_b, "C": node_c},
    )
