"""DAG 核心数据模型：节点、边、图。"""

from __future__ import annotations

import copy
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TaskType(StrEnum):
    """DAG 任务类型。"""

    SQL = "sql"
    PYTHON = "python"
    SEARCH = "search"
    ACTION = "action"
    LLM = "llm"
    COMPUTE = "compute"


class TaskStatus(StrEnum):
    """任务执行状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class DAGNode:
    """DAG 节点。"""

    node_id: str
    task_type: TaskType
    config: dict[str, Any] = field(default_factory=dict)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    max_retry: int = 3
    timeout_seconds: float = 30.0


@dataclass
class DAGEdge:
    """DAG 边（依赖关系）。"""

    source_id: str
    target_id: str
    condition: str = ""  # 可选条件表达式


@dataclass
class DAGraph:
    """有向无环图（DAG）。

    用于描述多步任务的依赖关系和执行顺序。
    """

    nodes: dict[str, DAGNode] = field(default_factory=dict)
    edges: list[DAGEdge] = field(default_factory=list)
    dag_id: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def generate_id() -> str:
        """生成唯一 DAG ID。"""
        import uuid
        return f"dag-{uuid.uuid4().hex[:12]}"

    # ------------------------------------------------------------------
    # 节点操作
    # ------------------------------------------------------------------

    def add_node(self, node: DAGNode) -> None:
        """添加节点。如果 node_id 已存在则覆盖。"""
        self.nodes[node.node_id] = node

    def remove_node(self, node_id: str) -> None:
        """移除节点及其关联的所有边。"""
        self.nodes.pop(node_id, None)
        self.edges = [
            e for e in self.edges if e.source_id != node_id and e.target_id != node_id
        ]

    # ------------------------------------------------------------------
    # 边操作
    # ------------------------------------------------------------------

    def add_edge(self, edge: DAGEdge) -> None:
        """添加边。不检查循环，调用方可在构建完成后调用 validate()。"""
        self.edges.append(edge)

    def remove_edge(self, source_id: str, target_id: str) -> None:
        """移除指定边。"""
        self.edges = [
            e for e in self.edges
            if not (e.source_id == source_id and e.target_id == target_id)
        ]

    # ------------------------------------------------------------------
    # 图查询
    # ------------------------------------------------------------------

    def get_dependencies(self, node_id: str) -> list[str]:
        """获取节点的所有直接依赖（前置节点）。"""
        return [e.source_id for e in self.edges if e.target_id == node_id]

    def get_dependents(self, node_id: str) -> list[str]:
        """获取依赖该节点的所有后续节点。"""
        return [e.target_id for e in self.edges if e.source_id == node_id]

    def get_root_nodes(self) -> list[str]:
        """获取根节点（无入边的节点）。"""
        targets = {e.target_id for e in self.edges}
        return [nid for nid in self.nodes if nid not in targets]

    def get_leaf_nodes(self) -> list[str]:
        """获取叶节点（无出边的节点）。"""
        sources = {e.source_id for e in self.edges}
        return [nid for nid in self.nodes if nid not in sources]

    # ------------------------------------------------------------------
    # 图算法
    # ------------------------------------------------------------------

    def detect_cycle(self) -> bool:
        """检测是否存在循环依赖（DFS 三色法）。

        Returns:
            True 表示存在循环。
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {nid: WHITE for nid in self.nodes}

        def _dfs(node_id: str) -> bool:
            color[node_id] = GRAY
            for dep_id in self.get_dependents(node_id):
                if dep_id not in color:
                    continue
                if color[dep_id] == GRAY:
                    return True
                if color[dep_id] == WHITE and _dfs(dep_id):
                    return True
            color[node_id] = BLACK
            return False

        for nid in self.nodes:
            if color[nid] == WHITE:
                if _dfs(nid):
                    return True
        return False

    def topological_sort(self) -> list[list[str]]:
        """拓扑排序，返回并行分组。

        同一分组内的节点无依赖关系，可并行执行。
        使用 Kahn's algorithm（BFS 入度法）。
        如果存在循环，抛出 ValueError。

        Returns:
            嵌套列表，外层为层级，内层为同层可并行节点 ID。
        """
        # 计算入度
        in_degree: dict[str, int] = {nid: 0 for nid in self.nodes}
        # 邻接表：source -> list[target]
        adj: dict[str, list[str]] = {nid: [] for nid in self.nodes}
        for edge in self.edges:
            if edge.target_id not in in_degree:
                raise ValueError(f"边引用了不存在的节点: {edge.target_id}")
            if edge.source_id not in in_degree:
                raise ValueError(f"边引用了不存在的节点: {edge.source_id}")
            in_degree[edge.target_id] += 1
            adj[edge.source_id].append(edge.target_id)

        # 入度为 0 的节点作为初始层
        queue: deque[str] = deque()
        for nid in self.nodes:
            if in_degree[nid] == 0:
                queue.append(nid)

        levels: list[list[str]] = []
        while queue:
            # 当前层所有节点同时出队
            current_level: list[str] = []
            for _ in range(len(queue)):
                node_id = queue.popleft()
                current_level.append(node_id)
                for dep_id in adj[node_id]:
                    in_degree[dep_id] -= 1
                    if in_degree[dep_id] == 0:
                        queue.append(dep_id)
            levels.append(sorted(current_level))

        if sum(len(level) for level in levels) != len(self.nodes):
            raise ValueError("DAG 中存在循环依赖，无法完成拓扑排序")

        return levels

    def validate(self) -> list[str]:
        """验证 DAG 完整性，返回错误列表。

        检查项：
        - 孤立节点（无入边无出边）
        - 悬挂边（引用不存在的节点）
        - 循环依赖
        - 节点 ID 唯一性（dataclass 字典已保证）
        """
        errors: list[str] = []
        node_ids = set(self.nodes.keys())

        # 检查悬挂边：引用不存在的节点
        for edge in self.edges:
            if edge.source_id not in node_ids:
                errors.append(f"悬挂边: 源节点 '{edge.source_id}' 不存在")
            if edge.target_id not in node_ids:
                errors.append(f"悬挂边: 目标节点 '{edge.target_id}' 不存在")

        # 检查孤立节点（排除单节点图的情况）
        if len(self.nodes) > 1:
            nodes_with_edges: set[str] = set()
            for edge in self.edges:
                if edge.source_id in node_ids:
                    nodes_with_edges.add(edge.source_id)
                if edge.target_id in node_ids:
                    nodes_with_edges.add(edge.target_id)
            for nid in self.nodes:
                if nid not in nodes_with_edges:
                    errors.append(f"孤立节点: '{nid}' 无入边也无出边")

        # 检查循环依赖
        if self.detect_cycle():
            errors.append("存在循环依赖")

        return errors

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def clone(self) -> DAGraph:
        """深拷贝 DAG。"""
        return copy.deepcopy(self)
