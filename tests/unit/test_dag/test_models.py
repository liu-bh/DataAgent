"""测试 DAGNode / DAGEdge / DAGraph 创建和操作。"""

from __future__ import annotations

import pytest

from datapilot_dag.models import DAGEdge, DAGNode, DAGraph, TaskType


# ------------------------------------------------------------------
# DAGNode
# ------------------------------------------------------------------


class TestDAGNode:
    """DAGNode 测试。"""

    def test_create_minimal(self) -> None:
        """最小化创建节点。"""
        node = DAGNode(node_id="a", task_type=TaskType.SQL)
        assert node.node_id == "a"
        assert node.task_type == TaskType.SQL
        assert node.config == {}
        assert node.inputs == []
        assert node.outputs == []
        assert node.max_retry == 3
        assert node.timeout_seconds == 30.0

    def test_create_full(self) -> None:
        """完整参数创建节点。"""
        node = DAGNode(
            node_id="b",
            task_type=TaskType.LLM,
            config={"model": "deepseek-v3"},
            inputs=["question"],
            outputs=["answer"],
            metadata={"version": 1},
            max_retry=5,
            timeout_seconds=60.0,
        )
        assert node.config["model"] == "deepseek-v3"
        assert node.inputs == ["question"]
        assert node.outputs == ["answer"]
        assert node.max_retry == 5
        assert node.timeout_seconds == 60.0

    def test_task_type_values(self) -> None:
        """验证所有 TaskType 枚举值。"""
        assert TaskType.SQL == "sql"
        assert TaskType.PYTHON == "python"
        assert TaskType.SEARCH == "search"
        assert TaskType.ACTION == "action"
        assert TaskType.LLM == "llm"


# ------------------------------------------------------------------
# DAGEdge
# ------------------------------------------------------------------


class TestDAGEdge:
    """DAGEdge 测试。"""

    def test_create_default(self) -> None:
        """默认条件为空字符串。"""
        edge = DAGEdge(source_id="a", target_id="b")
        assert edge.condition == ""

    def test_create_with_condition(self) -> None:
        """带条件表达式的边。"""
        edge = DAGEdge(source_id="a", target_id="b", condition="validate_failed")
        assert edge.condition == "validate_failed"


# ------------------------------------------------------------------
# DAGraph — 节点和边操作
# ------------------------------------------------------------------


class TestDAGraph:
    """DAGraph 测试。"""

    def _make_simple_dag(self) -> DAGraph:
        """创建简单 DAG: a -> b -> c。"""
        dag = DAGraph(dag_id="test")
        dag.add_node(DAGNode("a", TaskType.PYTHON))
        dag.add_node(DAGNode("b", TaskType.LLM))
        dag.add_node(DAGNode("c", TaskType.SQL))
        dag.add_edge(DAGEdge("a", "b"))
        dag.add_edge(DAGEdge("b", "c"))
        return dag

    def test_add_and_get_nodes(self) -> None:
        """添加节点后可正常获取。"""
        dag = self._make_simple_dag()
        assert "a" in dag.nodes
        assert "b" in dag.nodes
        assert "c" in dag.nodes

    def test_add_node_overwrite(self) -> None:
        """重复添加同一节点 ID 会覆盖。"""
        dag = DAGraph()
        dag.add_node(DAGNode("x", TaskType.SQL))
        dag.add_node(DAGNode("x", TaskType.LLM))
        assert dag.nodes["x"].task_type == TaskType.LLM

    def test_remove_node(self) -> None:
        """移除节点同时移除关联边。"""
        dag = self._make_simple_dag()
        dag.remove_node("b")
        assert "b" not in dag.nodes
        # 边 a->b 和 b->c 都应被移除
        assert len(dag.edges) == 0

    def test_remove_node_nonexistent(self) -> None:
        """移除不存在的节点不报错。"""
        dag = DAGraph()
        dag.remove_node("nonexistent")  # 不应抛异常

    def test_add_and_remove_edge(self) -> None:
        """添加和移除边。"""
        dag = self._make_simple_dag()
        assert len(dag.edges) == 2
        dag.remove_edge("a", "b")
        assert len(dag.edges) == 1
        assert dag.edges[0].source_id == "b"

    def test_remove_edge_nonexistent(self) -> None:
        """移除不存在的边不报错。"""
        dag = DAGraph()
        dag.remove_edge("x", "y")  # 不应抛异常

    def test_get_dependencies(self) -> None:
        """获取直接依赖。"""
        dag = self._make_simple_dag()
        assert dag.get_dependencies("a") == []
        assert dag.get_dependencies("b") == ["a"]
        assert dag.get_dependencies("c") == ["b"]

    def test_get_dependents(self) -> None:
        """获取后续节点。"""
        dag = self._make_simple_dag()
        assert dag.get_dependents("a") == ["b"]
        assert dag.get_dependents("b") == ["c"]
        assert dag.get_dependents("c") == []

    def test_get_root_nodes(self) -> None:
        """获取根节点。"""
        dag = self._make_simple_dag()
        assert dag.get_root_nodes() == ["a"]

    def test_get_leaf_nodes(self) -> None:
        """获取叶节点。"""
        dag = self._make_simple_dag()
        assert dag.get_leaf_nodes() == ["c"]

    def test_clone(self) -> None:
        """深拷贝 DAG，修改不影响原 DAG。"""
        dag = self._make_simple_dag()
        cloned = dag.clone()
        cloned.remove_node("a")
        assert "a" in dag.nodes  # 原图不受影响
        assert "a" not in cloned.nodes
