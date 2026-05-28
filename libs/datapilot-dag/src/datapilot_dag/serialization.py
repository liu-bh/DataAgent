"""DAG 序列化与反序列化。"""

from __future__ import annotations

import json
from typing import Any

from datapilot_dag.models import DAGEdge, DAGNode, DAGraph, TaskType


class DAGSerializer:
    """DAG 序列化/反序列化工具。"""

    @staticmethod
    def to_json(dag: DAGraph) -> dict[str, Any]:
        """将 DAG 序列化为 JSON 兼容字典。"""
        return {
            "dag_id": dag.dag_id,
            "nodes": {
                node_id: {
                    "node_id": node.node_id,
                    "task_type": node.task_type.value,
                    "config": node.config,
                    "inputs": node.inputs,
                    "outputs": node.outputs,
                    "metadata": node.metadata,
                    "max_retry": node.max_retry,
                    "timeout_seconds": node.timeout_seconds,
                }
                for node_id, node in dag.nodes.items()
            },
            "edges": [
                {
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "condition": edge.condition,
                }
                for edge in dag.edges
            ],
        }

    @staticmethod
    def to_json_string(dag: DAGraph, indent: int = 2) -> str:
        """将 DAG 序列化为 JSON 字符串。"""
        return json.dumps(DAGSerializer.to_json(dag), ensure_ascii=False, indent=indent)

    @staticmethod
    def from_json(data: dict[str, Any]) -> DAGraph:
        """从 JSON 兼容字典反序列化 DAG。"""
        dag = DAGraph(dag_id=data.get("dag_id", ""))

        # 反序列化节点
        nodes_data = data.get("nodes", {})
        for node_id, node_data in nodes_data.items():
            node = DAGNode(
                node_id=node_data["node_id"],
                task_type=TaskType(node_data["task_type"]),
                config=node_data.get("config", {}),
                inputs=node_data.get("inputs", []),
                outputs=node_data.get("outputs", []),
                metadata=node_data.get("metadata", {}),
                max_retry=node_data.get("max_retry", 3),
                timeout_seconds=node_data.get("timeout_seconds", 30.0),
            )
            dag.add_node(node)

        # 反序列化边
        edges_data = data.get("edges", [])
        for edge_data in edges_data:
            edge = DAGEdge(
                source_id=edge_data["source_id"],
                target_id=edge_data["target_id"],
                condition=edge_data.get("condition", ""),
            )
            dag.add_edge(edge)

        return dag

    @staticmethod
    def from_json_string(json_str: str) -> DAGraph:
        """从 JSON 字符串反序列化 DAG。"""
        data = json.loads(json_str)
        return DAGSerializer.from_json(data)
