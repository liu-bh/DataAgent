"""测试 DAGBuilder 流式构建、from_json、from_nl2sql。"""

from __future__ import annotations

import pytest

from datapilot_dag.builder import DAGBuilder
from datapilot_dag.models import TaskType


class TestDAGBuilder:
    """DAGBuilder 测试。"""

    def test_fluent_api(self) -> None:
        """链式调用构建 DAG。"""
        dag = (
            DAGBuilder(dag_id="fluent")
            .add_node("a", TaskType.PYTHON)
            .add_node("b", TaskType.LLM)
            .add_node("c", TaskType.SQL)
            .add_edge("a", "b")
            .add_edge("b", "c")
            .build()
        )
        assert dag.dag_id == "fluent"
        assert len(dag.nodes) == 3
        assert len(dag.edges) == 2

    def test_build_with_validation_error(self) -> None:
        """构建时验证失败抛出 ValueError。"""
        with pytest.raises(ValueError, match="DAG 验证失败"):
            # 两个孤立节点（多于一个节点且无边连接）
            DAGBuilder(dag_id="bad")
            .add_node("a", TaskType.SQL)
            .add_node("b", TaskType.LLM)
            .build()

    def test_single_node_dag(self) -> None:
        """单节点 DAG 应通过验证（不算孤立节点）。"""
        dag = DAGBuilder(dag_id="single").add_node("a", TaskType.PYTHON).build()
        assert len(dag.nodes) == 1
        assert len(dag.edges) == 0

    def test_from_json(self) -> None:
        """从 JSON 反序列化 DAG。"""
        data = {
            "dag_id": "json_test",
            "nodes": {
                "a": {
                    "node_id": "a",
                    "task_type": "python",
                    "config": {"fn": "test"},
                    "inputs": [],
                    "outputs": ["result"],
                },
                "b": {
                    "node_id": "b",
                    "task_type": "sql",
                    "config": {},
                    "inputs": ["result"],
                    "outputs": [],
                },
            },
            "edges": [
                {"source_id": "a", "target_id": "b"},
            ],
        }
        dag = DAGBuilder.from_json(data)
        assert dag.dag_id == "json_test"
        assert len(dag.nodes) == 2
        assert dag.nodes["a"].task_type == TaskType.PYTHON
        assert dag.nodes["a"].config["fn"] == "test"
        assert dag.nodes["a"].outputs == ["result"]
        assert len(dag.edges) == 1

    def test_from_nl2sql(self) -> None:
        """构建 NL2SQL 标准 DAG。"""
        dag = DAGBuilder.from_nl2sql("查询最近7天的订单金额", dialect="mysql")

        assert dag.dag_id == "nl2sql"
        # 8 个标准节点
        assert len(dag.nodes) == 8
        expected_nodes = [
            "intent_route",
            "intent_parse",
            "schema_link",
            "prompt_build",
            "sql_generate",
            "sql_validate",
            "sql_correct",
            "sql_explain",
        ]
        for node_id in expected_nodes:
            assert node_id in dag.nodes, f"缺少节点: {node_id}"

        # 验证关键依赖
        assert "intent_route" in dag.get_dependencies("intent_parse")
        assert "intent_parse" in dag.get_dependencies("schema_link")
        assert "schema_link" in dag.get_dependencies("prompt_build")
        assert "prompt_build" in dag.get_dependencies("sql_generate")
        assert "sql_generate" in dag.get_dependencies("sql_validate")
        assert "sql_validate" in dag.get_dependencies("sql_correct")

        # sql_explain 依赖 sql_generate 和 sql_correct
        explain_deps = dag.get_dependencies("sql_explain")
        assert "sql_generate" in explain_deps
        assert "sql_correct" in explain_deps

        # 验证条件边
        correct_edge = next(
            (e for e in dag.edges if e.target_id == "sql_correct"), None
        )
        assert correct_edge is not None
        assert correct_edge.condition == "validate_failed"

        # 验证没有循环
        errors = dag.validate()
        cycle_errors = [e for e in errors if "循环" in e]
        assert len(cycle_errors) == 0

    def test_from_nl2sql_question_stored(self) -> None:
        """验证 NL2SQL DAG 中 question 被存储在节点 config 中。"""
        dag = DAGBuilder.from_nl2sql("今天的销售额是多少", dialect="postgres")
        assert dag.nodes["intent_route"].config["input"] == "今天的销售额是多少"
        assert dag.nodes["prompt_build"].config["dialect"] == "postgres"
