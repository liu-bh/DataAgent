"""测试 validate — 孤立节点、悬挂边、循环。"""

from __future__ import annotations

from datapilot_dag.models import DAGEdge, DAGNode, DAGraph, TaskType


class TestValidation:
    """DAG 验证测试。"""

    def test_valid_dag_no_errors(self) -> None:
        """合法 DAG 无错误。"""
        dag = DAGraph(dag_id="valid")
        dag.add_node(DAGNode("a", TaskType.PYTHON))
        dag.add_node(DAGNode("b", TaskType.SQL))
        dag.add_edge(DAGEdge("a", "b"))

        errors = dag.validate()
        assert errors == []

    def test_single_node_no_errors(self) -> None:
        """单节点 DAG 无错误（不算孤立节点）。"""
        dag = DAGraph(dag_id="single")
        dag.add_node(DAGNode("a", TaskType.PYTHON))

        errors = dag.validate()
        assert errors == []

    def test_isolated_nodes(self) -> None:
        """多节点 DAG 中有孤立节点。"""
        dag = DAGraph(dag_id="isolated")
        dag.add_node(DAGNode("a", TaskType.PYTHON))
        dag.add_node(DAGNode("b", TaskType.SQL))
        dag.add_edge(DAGEdge("a", "b"))
        dag.add_node(DAGNode("c", TaskType.LLM))  # 孤立节点

        errors = dag.validate()
        isolated_errors = [e for e in errors if "孤立" in e]
        assert len(isolated_errors) == 1
        assert "c" in isolated_errors[0]

    def test_multiple_isolated_nodes(self) -> None:
        """多个孤立节点。"""
        dag = DAGraph(dag_id="multi_isolated")
        dag.add_node(DAGNode("a", TaskType.PYTHON))
        dag.add_node(DAGNode("b", TaskType.SQL))
        dag.add_edge(DAGEdge("a", "b"))
        dag.add_node(DAGNode("c", TaskType.LLM))
        dag.add_node(DAGNode("d", TaskType.SEARCH))

        errors = dag.validate()
        isolated_errors = [e for e in errors if "孤立" in e]
        assert len(isolated_errors) == 2

    def test_dangling_edge_source(self) -> None:
        """悬挂边：源节点不存在。"""
        dag = DAGraph(dag_id="dangling_src")
        dag.add_node(DAGNode("b", TaskType.SQL))
        dag.add_edge(DAGEdge("nonexistent", "b"))

        errors = dag.validate()
        dangling_errors = [e for e in errors if "悬挂" in e]
        assert len(dangling_errors) == 1
        assert "nonexistent" in dangling_errors[0]

    def test_dangling_edge_target(self) -> None:
        """悬挂边：目标节点不存在。"""
        dag = DAGraph(dag_id="dangling_tgt")
        dag.add_node(DAGNode("a", TaskType.PYTHON))
        dag.add_edge(DAGEdge("a", "nonexistent"))

        errors = dag.validate()
        dangling_errors = [e for e in errors if "悬挂" in e]
        assert len(dangling_errors) == 1
        assert "nonexistent" in dangling_errors[0]

    def test_dangling_edge_both(self) -> None:
        """悬挂边：源和目标都不存在。"""
        dag = DAGraph(dag_id="dangling_both")
        dag.add_edge(DAGEdge("x", "y"))

        errors = dag.validate()
        dangling_errors = [e for e in errors if "悬挂" in e]
        assert len(dangling_errors) == 2

    def test_cycle_detection(self) -> None:
        """循环依赖检测。"""
        dag = DAGraph(dag_id="cycle")
        dag.add_node(DAGNode("a", TaskType.PYTHON))
        dag.add_node(DAGNode("b", TaskType.SQL))
        dag.add_node(DAGNode("c", TaskType.LLM))
        dag.add_edge(DAGEdge("a", "b"))
        dag.add_edge(DAGEdge("b", "c"))
        dag.add_edge(DAGEdge("c", "a"))

        errors = dag.validate()
        cycle_errors = [e for e in errors if "循环" in e]
        assert len(cycle_errors) == 1

    def test_combined_errors(self) -> None:
        """同时存在多种错误。"""
        dag = DAGraph(dag_id="combined")
        dag.add_node(DAGNode("a", TaskType.PYTHON))
        dag.add_node(DAGNode("b", TaskType.SQL))
        dag.add_node(DAGNode("c", TaskType.LLM))
        dag.add_edge(DAGEdge("a", "b"))
        dag.add_edge(DAGEdge("b", "c"))
        dag.add_edge(DAGEdge("c", "a"))  # 循环
        dag.add_edge(DAGEdge("a", "ghost"))  # 悬挂边

        errors = dag.validate()
        assert len(errors) >= 2  # 至少循环和悬挂边

    def test_empty_dag_no_errors(self) -> None:
        """空 DAG 无错误。"""
        dag = DAGraph(dag_id="empty")
        errors = dag.validate()
        assert errors == []

    def test_detect_cycle_returns_false_for_valid(self) -> None:
        """合法 DAG detect_cycle 返回 False。"""
        dag = DAGraph()
        dag.add_node(DAGNode("a", TaskType.PYTHON))
        dag.add_node(DAGNode("b", TaskType.SQL))
        dag.add_edge(DAGEdge("a", "b"))
        assert dag.detect_cycle() is False

    def test_detect_cycle_returns_true(self) -> None:
        """有循环时 detect_cycle 返回 True。"""
        dag = DAGraph()
        dag.add_node(DAGNode("a", TaskType.PYTHON))
        dag.add_node(DAGNode("b", TaskType.SQL))
        dag.add_edge(DAGEdge("a", "b"))
        dag.add_edge(DAGEdge("b", "a"))
        assert dag.detect_cycle() is True
