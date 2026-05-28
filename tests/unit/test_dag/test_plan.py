"""测试执行计划生成。"""

from __future__ import annotations

import pytest

from datapilot_dag.models import DAGEdge, DAGNode, DAGraph, TaskType
from datapilot_dag.plan import ExecutionPlan


class TestExecutionPlan:
    """ExecutionPlan 测试。"""

    def test_linear_plan(self) -> None:
        """线性链 a -> b -> c 的执行计划。"""
        dag = DAGraph(dag_id="linear")
        for nid in ("a", "b", "c"):
            dag.add_node(DAGNode(nid, TaskType.PYTHON))
        dag.add_edge(DAGEdge("a", "b"))
        dag.add_edge(DAGEdge("b", "c"))

        plan = ExecutionPlan.from_dag(dag)

        assert plan.dag_id == "linear"
        assert plan.total_nodes == 3
        assert plan.levels == [["a"], ["b"], ["c"]]
        assert plan.estimated_parallelism == 1.0
        assert plan.critical_path == ["a", "b", "c"]

    def test_parallel_plan(self) -> None:
        """并行 DAG a -> (b, c) 的执行计划。"""
        dag = DAGraph(dag_id="parallel")
        for nid in ("a", "b", "c"):
            dag.add_node(DAGNode(nid, TaskType.PYTHON))
        dag.add_edge(DAGEdge("a", "b"))
        dag.add_edge(DAGEdge("a", "c"))

        plan = ExecutionPlan.from_dag(dag)

        assert plan.total_nodes == 3
        assert len(plan.levels) == 2
        assert plan.estimated_parallelism == 1.5  # 3 nodes / 2 levels
        assert plan.critical_path == ["a", "b"] or plan.critical_path == ["a", "c"]

    def test_diamond_plan(self) -> None:
        """菱形 DAG a -> (b, c) -> d 的执行计划。"""
        dag = DAGraph(dag_id="diamond")
        for nid in ("a", "b", "c", "d"):
            dag.add_node(DAGNode(nid, TaskType.PYTHON))
        dag.add_edge(DAGEdge("a", "b"))
        dag.add_edge(DAGEdge("a", "c"))
        dag.add_edge(DAGEdge("b", "d"))
        dag.add_edge(DAGEdge("c", "d"))

        plan = ExecutionPlan.from_dag(dag)

        assert plan.total_nodes == 4
        assert len(plan.levels) == 3
        assert plan.estimated_parallelism == pytest.approx(1.33, abs=0.01)
        # 关键路径应为 3 条边长（a -> b/c -> d，取决于排序）
        assert len(plan.critical_path) == 3

    def test_empty_plan(self) -> None:
        """空 DAG 的执行计划。"""
        dag = DAGraph(dag_id="empty")

        plan = ExecutionPlan.from_dag(dag)

        assert plan.total_nodes == 0
        assert plan.levels == []
        assert plan.estimated_parallelism == 0.0
        assert plan.critical_path == []

    def test_single_node_plan(self) -> None:
        """单节点 DAG 的执行计划。"""
        dag = DAGraph(dag_id="single")
        dag.add_node(DAGNode("a", TaskType.SQL))

        plan = ExecutionPlan.from_dag(dag)

        assert plan.total_nodes == 1
        assert plan.levels == [["a"]]
        assert plan.estimated_parallelism == 1.0
        assert plan.critical_path == ["a"]

    def test_plan_with_cycle_raises(self) -> None:
        """有循环时生成计划抛出 ValueError。"""
        dag = DAGraph(dag_id="cycle")
        for nid in ("a", "b"):
            dag.add_node(DAGNode(nid, TaskType.PYTHON))
        dag.add_edge(DAGEdge("a", "b"))
        dag.add_edge(DAGEdge("b", "a"))

        with pytest.raises(ValueError, match="循环依赖"):
            ExecutionPlan.from_dag(dag)

    def test_complex_dag_plan(self) -> None:
        """复杂 DAG 执行计划：多层级并行。

        结构:
            a -> (b, c)
            b -> (d, e)
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
        dag.add_edge(DAGEdge("b", "e"))
        dag.add_edge(DAGEdge("c", "e"))
        dag.add_edge(DAGEdge("d", "f"))
        dag.add_edge(DAGEdge("e", "f"))

        plan = ExecutionPlan.from_dag(dag)

        assert plan.total_nodes == 6
        assert len(plan.levels) == 4
        assert plan.levels[0] == ["a"]
        assert sorted(plan.levels[1]) == ["b", "c"]
        assert sorted(plan.levels[2]) == ["d", "e"]
        assert plan.levels[3] == ["f"]
        # 关键路径: a -> b -> d -> f 或 a -> c -> e -> f (长度 4)
        assert len(plan.critical_path) == 4
