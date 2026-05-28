"""DAG 执行计划 — 拓扑层级、并行度估算、关键路径。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datapilot_dag.models import DAGraph


@dataclass
class ExecutionPlan:
    """DAG 执行计划。

    包含拓扑排序后的并行层级、并行度估算和关键路径。
    """

    dag_id: str
    levels: list[list[str]]  # 拓扑排序后的并行层级
    total_nodes: int
    estimated_parallelism: float  # 平均并行度
    critical_path: list[str]  # 关键路径（最长路径）

    @classmethod
    def from_dag(cls, dag: DAGraph) -> ExecutionPlan:
        """从 DAG 生成执行计划。

        Args:
            dag: 有向无环图。

        Returns:
            执行计划实例。

        Raises:
            ValueError: DAG 中存在循环时抛出。
        """
        levels = dag.topological_sort()
        total_nodes = len(dag.nodes)

        # 平均并行度 = 总节点数 / 总层数
        num_levels = len(levels)
        estimated_parallelism = total_nodes / num_levels if num_levels > 0 else 0.0

        # 计算关键路径（最长路径，基于边数）
        critical_path = cls._find_critical_path(dag)

        return cls(
            dag_id=dag.dag_id,
            levels=levels,
            total_nodes=total_nodes,
            estimated_parallelism=round(estimated_parallelism, 2),
            critical_path=critical_path,
        )

    @staticmethod
    def _find_critical_path(dag: DAGraph) -> list[str]:
        """通过 BFS 逆拓扑计算最长路径（关键路径）。

        使用动态规划方式：从根节点到每个节点的最长距离。
        """
        if not dag.nodes:
            return []

        levels = dag.topological_sort()

        # 按拓扑顺序逐层计算每个节点的最长距离
        # dist[node_id] = 从根节点到该节点的最长边数
        dist: dict[str, int] = {}
        # prev[node_id] = 关键路径上前驱节点
        prev: dict[str, str] = {}

        # 初始化根节点
        root_nodes = dag.get_root_nodes()
        for nid in root_nodes:
            dist[nid] = 0

        # 逐层处理
        node_order: list[str] = []
        for level in levels:
            node_order.extend(level)

        for node_id in node_order:
            if node_id not in dist:
                # 不应发生，拓扑排序保证了所有节点都有入度来源
                continue
            for dep_id in dag.get_dependents(node_id):
                new_dist = dist[node_id] + 1
                if dep_id not in dist or new_dist > dist[dep_id]:
                    dist[dep_id] = new_dist
                    prev[dep_id] = node_id

        # 找到距离最大的叶节点
        leaf_nodes = dag.get_leaf_nodes()
        if not leaf_nodes:
            # 环形图理论上不会走到这里（topological_sort 会抛异常）
            return []

        max_leaf = max(leaf_nodes, key=lambda nid: dist.get(nid, -1))
        dist.get(max_leaf, -1)

        # 回溯关键路径
        path: list[str] = []
        current = max_leaf
        while current is not None:
            path.append(current)
            current = prev.get(current)

        path.reverse()
        return path
