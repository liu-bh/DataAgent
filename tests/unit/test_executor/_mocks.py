"""执行器模块测试公共 mock 类。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MockDAGNode:
    """模拟 DAGNode。"""

    node_id: str
    task_type: str = "sql"
    config: dict = field(default_factory=dict)
    dependencies: list = field(default_factory=list)
    condition: str = ""


class FakeDAGraph:
    """模拟 DAGraph。"""

    def __init__(self, dag_id: str, nodes: dict = None) -> None:
        self.dag_id = dag_id
        self.nodes: dict[str, MockDAGNode] = nodes or {}

    def topological_levels(self) -> list:
        """返回拓扑排序的层级列表。"""
        if not self.nodes:
            return []

        remaining = set(self.nodes.keys())
        levels: list[list[str]] = []

        while remaining:
            level = [
                nid for nid in remaining
                if all(dep not in remaining for dep in self.nodes[nid].dependencies)
            ]
            if not level:
                level = list(remaining)
            levels.append(sorted(level))
            remaining -= set(level)

        return levels
