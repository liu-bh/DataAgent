"""DAG Builder — 提供流式 API 构建 DAG。"""

from __future__ import annotations

from typing import Any

from datapilot_dag.models import DAGEdge, DAGNode, DAGraph, TaskType
from datapilot_dag.serialization import DAGSerializer


class DAGBuilder:
    """DAG 构建器，提供流式 API 构建 DAG。"""

    def __init__(self, dag_id: str = "") -> None:
        self._dag = DAGraph(dag_id=dag_id)

    def add_node(
        self,
        node_id: str,
        task_type: TaskType,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> DAGBuilder:
        """添加节点，返回 self 以支持链式调用。"""
        node = DAGNode(
            node_id=node_id,
            task_type=task_type,
            config=config or {},
            **kwargs,
        )
        self._dag.add_node(node)
        return self

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        condition: str = "",
    ) -> DAGBuilder:
        """添加边，返回 self 以支持链式调用。"""
        edge = DAGEdge(source_id=source_id, target_id=target_id, condition=condition)
        self._dag.add_edge(edge)
        return self

    def build(self) -> DAGraph:
        """构建 DAG，执行验证和拓扑排序。

        Returns:
            构建完成的 DAG 实例。

        Raises:
            ValueError: 验证失败时抛出，包含所有错误信息。
        """
        errors = self._dag.validate()
        if errors:
            raise ValueError(f"DAG 验证失败: {'; '.join(errors)}")
        return self._dag

    @staticmethod
    def from_json(data: dict[str, Any]) -> DAGraph:
        """从 JSON 反序列化 DAG。"""
        return DAGSerializer.from_json(data)

    @staticmethod
    def from_nl2sql(question: str, dialect: str = "mysql") -> DAGraph:
        """构建 NL2SQL 标准 DAG（8 步）。

        构建节点:
        1. intent_route (LLM) — 意图路由
        2. intent_parse (LLM) [依赖 1] — 意图解析
        3. schema_link (计算) [依赖 2] — Schema 关联
        4. prompt_build (计算) [依赖 3] — Prompt 构建
        5. sql_generate (LLM) [依赖 4] — SQL 生成
        6. sql_validate (计算) [依赖 5] — SQL 校验
        7. sql_correct (LLM, conditional) [依赖 6] — SQL 纠正（条件触发）
        8. sql_explain (LLM) [依赖 5 或 7] — SQL 解释

        Args:
            question: 用户自然语言问题。
            dialect: 目标 SQL 方言。

        Returns:
            构建完成的 NL2SQL DAG。
        """
        builder = DAGBuilder(dag_id="nl2sql")

        # 1. 意图路由
        builder.add_node(
            "intent_route",
            TaskType.LLM,
            config={
                "prompt_template": "intent_route",
                "model": "qwen-turbo",
                "input": question,
            },
            outputs=["intent_type"],
        )

        # 2. 意图解析
        builder.add_node(
            "intent_parse",
            TaskType.LLM,
            config={
                "prompt_template": "intent_parse",
                "model": "qwen-turbo",
            },
            inputs=["intent_type"],
            outputs=["parsed_intent"],
        )
        builder.add_edge("intent_route", "intent_parse")

        # 3. Schema 关联
        builder.add_node(
            "schema_link",
            TaskType.PYTHON,
            config={"function": "schema_linking", "top_k": 10},
            inputs=["parsed_intent"],
            outputs=["linked_schema"],
        )
        builder.add_edge("intent_parse", "schema_link")

        # 4. Prompt 构建
        builder.add_node(
            "prompt_build",
            TaskType.PYTHON,
            config={"function": "build_prompt", "dialect": dialect},
            inputs=["linked_schema", "parsed_intent"],
            outputs=["final_prompt"],
        )
        builder.add_edge("schema_link", "prompt_build")

        # 5. SQL 生成
        builder.add_node(
            "sql_generate",
            TaskType.LLM,
            config={
                "prompt_template": "sql_generate",
                "model": "deepseek-v3",
            },
            inputs=["final_prompt"],
            outputs=["generated_sql", "sql_confidence"],
        )
        builder.add_edge("prompt_build", "sql_generate")

        # 6. SQL 校验
        builder.add_node(
            "sql_validate",
            TaskType.PYTHON,
            config={"function": "validate_sql", "dialect": dialect},
            inputs=["generated_sql"],
            outputs=["validation_result"],
        )
        builder.add_edge("sql_generate", "sql_validate")

        # 7. SQL 纠正（条件触发）
        builder.add_node(
            "sql_correct",
            TaskType.LLM,
            config={
                "prompt_template": "sql_correct",
                "model": "deepseek-v3",
                "max_retry": 3,
            },
            inputs=["generated_sql", "validation_result"],
            outputs=["corrected_sql"],
        )
        builder.add_edge("sql_validate", "sql_correct", condition="validate_failed")

        # 8. SQL 解释（依赖 sql_generate 或 sql_correct）
        builder.add_node(
            "sql_explain",
            TaskType.LLM,
            config={
                "prompt_template": "sql_explain",
                "model": "qwen-turbo",
            },
            inputs=["corrected_sql", "generated_sql"],
            outputs=["sql_explanation"],
        )
        builder.add_edge("sql_generate", "sql_explain")
        builder.add_edge("sql_correct", "sql_explain", condition="corrected")

        return builder.build()
