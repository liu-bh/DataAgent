"""测试序列化/反序列化。"""

from __future__ import annotations

from datapilot_dag.models import DAGEdge, DAGNode, DAGraph, TaskType
from datapilot_dag.serialization import DAGSerializer


def _make_test_dag() -> DAGraph:
    """创建测试用 DAG。"""
    dag = DAGraph(dag_id="serial_test")
    dag.add_node(DAGNode(
        "parse_intent",
        TaskType.LLM,
        config={"model": "deepseek-v3", "temperature": 0.7},
        inputs=["question"],
        outputs=["intent"],
        metadata={"version": 2},
        max_retry=5,
        timeout_seconds=60.0,
    ))
    dag.add_node(DAGNode(
        "gen_sql",
        TaskType.LLM,
        config={"model": "qwen-plus"},
        inputs=["intent", "schema"],
        outputs=["sql"],
    ))
    dag.add_node(DAGNode(
        "run_sql",
        TaskType.SQL,
        config={"dialect": "mysql"},
        inputs=["sql"],
        outputs=["result"],
    ))
    dag.add_edge(DAGEdge("parse_intent", "gen_sql"))
    dag.add_edge(DAGEdge("gen_sql", "run_sql"))
    dag.add_edge(DAGEdge("parse_intent", "run_sql", condition="skip_llm"))
    return dag


class TestSerialization:
    """DAG 序列化/反序列化测试。"""

    def test_to_json(self) -> None:
        """序列化为字典。"""
        dag = _make_test_dag()
        data = DAGSerializer.to_json(dag)

        assert data["dag_id"] == "serial_test"
        assert len(data["nodes"]) == 3
        assert len(data["edges"]) == 3

        # 验证节点字段
        node = data["nodes"]["parse_intent"]
        assert node["task_type"] == "llm"
        assert node["config"]["model"] == "deepseek-v3"
        assert node["config"]["temperature"] == 0.7
        assert node["inputs"] == ["question"]
        assert node["outputs"] == ["intent"]
        assert node["metadata"]["version"] == 2
        assert node["max_retry"] == 5
        assert node["timeout_seconds"] == 60.0

        # 验证边
        assert data["edges"][0]["source_id"] == "parse_intent"
        assert data["edges"][0]["target_id"] == "gen_sql"
        assert data["edges"][2]["condition"] == "skip_llm"

    def test_to_json_string(self) -> None:
        """序列化为 JSON 字符串。"""
        dag = _make_test_dag()
        json_str = DAGSerializer.to_json_string(dag)
        assert isinstance(json_str, str)
        assert "serial_test" in json_str
        assert "parse_intent" in json_str
        # 验证是合法 JSON
        import json
        parsed = json.loads(json_str)
        assert parsed["dag_id"] == "serial_test"

    def test_round_trip(self) -> None:
        """序列化 -> 反序列化 往返一致性。"""
        original = _make_test_dag()
        json_data = DAGSerializer.to_json(original)
        restored = DAGSerializer.from_json(json_data)

        assert restored.dag_id == original.dag_id
        assert len(restored.nodes) == len(original.nodes)
        assert len(restored.edges) == len(original.edges)

        # 验证节点属性完整恢复
        for nid, orig_node in original.nodes.items():
            rest_node = restored.nodes[nid]
            assert rest_node.node_id == orig_node.node_id
            assert rest_node.task_type == orig_node.task_type
            assert rest_node.config == orig_node.config
            assert rest_node.inputs == orig_node.inputs
            assert rest_node.outputs == orig_node.outputs
            assert rest_node.metadata == orig_node.metadata
            assert rest_node.max_retry == orig_node.max_retry
            assert rest_node.timeout_seconds == orig_node.timeout_seconds

        # 验证边属性完整恢复
        for orig_edge, rest_edge in zip(original.edges, restored.edges):
            assert rest_edge.source_id == orig_edge.source_id
            assert rest_edge.target_id == orig_edge.target_id
            assert rest_edge.condition == orig_edge.condition

    def test_from_json_string(self) -> None:
        """从 JSON 字符串反序列化。"""
        dag = _make_test_dag()
        json_str = DAGSerializer.to_json_string(dag)
        restored = DAGSerializer.from_json_string(json_str)

        assert restored.dag_id == dag.dag_id
        assert len(restored.nodes) == len(dag.nodes)

    def test_empty_dag_serialization(self) -> None:
        """空 DAG 序列化/反序列化。"""
        dag = DAGraph(dag_id="empty")
        json_data = DAGSerializer.to_json(dag)
        assert json_data["nodes"] == {}
        assert json_data["edges"] == []

        restored = DAGSerializer.from_json(json_data)
        assert restored.dag_id == "empty"
        assert len(restored.nodes) == 0
        assert len(restored.edges) == 0
