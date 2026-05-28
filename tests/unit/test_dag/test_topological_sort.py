"""测试拓扑排序（正常、循环、多层级）。"""

from __future__ import annotations

import pytest

from datapilot_dag.models import DAGEdge, DAGNode, DAGraph, TaskType


class TestTopologicalSort:
    """拓扑排序测试。"""

    def test_linear_chain(self) -> None:
        """线性链 a -> b -> c 应产生 3 层。"""
        dag = DAGraph(dag_id="linear")
        for nid in ("a", "b", "c"):
            dag.add_node(DAGNode(nid, TaskType.PYTHON))
        dag.add_edge(DAGEdge("a", "b"))
        dag.add_edge(DAGEdge("b", "c"))

        levels = dag.topological_sort()
        assert len(levels) == 3
        assert levels == [["a"], ["b"], ["c"]]

    def test_parallel_nodes(self) -> None:
        """并行节点 a -> (b, c) 应产生 2 层。"""
        dag = DAGraph(dag_id="parallel")
        for nid in ("a", "b", "c"):
            dag.add_node(DAGNode(nid, TaskType.PYTHON))
        dag.add_edge(DAGEdge("a", "b"))
        dag.add_edge(DAGEdge("a", "c"))

        levels = dag.topological_sort()
        assert len(levels) == 2
        assert levels[0] == ["a"]
        assert sorted(levels[1]) == ["b", "c"]

    def test_diamond_shape(self) -> None:
        """菱形依赖 a -> (b, c) -> d。"""
        dag = DAGraph(dag_id="diamond")
        for nid in ("a", "b", "c", "d"):
            dag.add_node(DAGNode(nid, TaskType.PYTHON))
        dag.add_edge(DAGEdge("a", "b"))
        dag.add_edge(DAGEdge("a", "c"))
        dag.add_edge(DAGEdge("b", "d"))
        dag.add_edge(DAGEdge("c", "d"))

        levels = dag.topological_sort()
        assert len(levels) == 3
        assert levels[0] == ["a"]
        assert sorted(levels[1]) == ["b", "c"]
        assert levels[2] == ["d"]

    def test_complex_dag(self) -> None:
        """复杂 DAG: 多层并行和串行混合。

        结构:
            a -> b -> d
            a -> c -> d
            b -> e
            c -> e
            d -> f
            e -> f
        """
        dag = DAGraph(dag_id="complex")
        for nid in ("a", "b", "c", "d", "e", "f"):
            dag.add_node(DAGNode(nid, TaskType.PYTHON))
        dag.add_edge(DAGEdge("a", "b"))
        dag.add_edge(DAGEdge("a", "c"))
        dag.add_edge(DAGEdge("b", "d"))
        dag.add_edge(DAGEdge("c", "d"))
        dag.add_edge(DAGEdge("b", "e"))
        dag.add_edge(DAGEdge("c", "e"))
        dag.add_edge(DAGEdge("d", "f"))
        dag.add_edge(DAGEdge("e", "f"))

        levels = dag.topological_sort()
        assert len(levels) == 4
        assert levels[0] == ["a"]
        assert sorted(levels[1]) == ["b", "c"]
        assert sorted(levels[2]) == ["d", "e"]
        assert levels[3] == ["f"]

    def test_single_node(self) -> None:
        """单节点 DAG。"""
        dag = DAGraph(dag_id="single")
        dag.add_node(DAGNode("a", TaskType.SQL))

        levels = dag.topological_sort()
        assert levels == [["a"]]

    def test_empty_dag(self) -> None:
        """空 DAG。"""
        dag = DAGraph(dag_id="empty")
        levels = dag.topological_sort()
        assert levels == []

    def test_cycle_raises_value_error(self) -> None:
        """存在循环时抛出 ValueError。"""
        dag = DAGraph(dag_id="cycle")
        for nid in ("a", "b", "c"):
            dag.add_node(DAGNode(nid, TaskType.PYTHON))
        dag.add_edge(DAGEdge("a", "b"))
        dag.add_edge(DAGEdge("b", "c"))
        dag.add_edge(DAGEdge("c", "a"))  # 循环

        with pytest.raises(ValueError, match="循环依赖"):
            dag.topological_sort()

    def test_dangling_edge_raises_value_error(self) -> None:
        """边引用不存在的节点时抛出 ValueError。"""
        dag = DAGraph(dag_id="dangling")
        dag.add_node(DAGNode("a", TaskType.PYTHON))
        dag.add_edge(DAGEdge("a", "nonexistent"))  # 不存在的目标

        with pytest.raises(ValueError, match="不存在的节点"):
            dag.topological_sort()

    def test_self_loop_raises_value_error(self) -> None:
        """自环抛出 ValueError。"""
        dag = DAGraph(dag_id="self_loop")
        dag.add_node(DAGNode("a", TaskType.PYTHON))
        dag.add_edge(DAGEdge("a", "a"))

        with pytest.raises(ValueError, match="循环依赖"):
            dag.topological_sort()
