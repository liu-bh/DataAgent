"""NL2SQL Pipeline DAG 构建。

将 NL2SQL 的 10 步 Pipeline 转换为 DAG 图，
支持并行调度和条件分支。

DAG 节点层次:
  Level 0: intent_route   (LLM)       — 意图路由
  Level 1: intent_parse   (LLM)       — 意图解析 [依赖 intent_route]
  Level 2: schema_link    (计算)      — Schema Linking [依赖 intent_parse]
  Level 3: prompt_build   (计算)      — Prompt 构建 [依赖 schema_link]
  Level 4: sql_generate   (LLM)       — SQL 生成 [依赖 prompt_build]
  Level 5: sql_validate   (计算)      — SQL 校验 [依赖 sql_generate]
  Level 6: sql_correct    (LLM, cond) — SQL 纠错 [依赖 sql_validate, 条件: validate_failed]
  Level 7: sql_explain    (LLM)       — SQL 解释 [依赖 sql_validate 或 sql_correct]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from datapilot_dag import DAGraph, DAGNode

logger = structlog.get_logger(__name__)


class NL2SQLDAGBuilder:
    """将 NL2SQL Pipeline 步骤构建为 DAG。

    使用方式::

        from datapilot_dag import DAGExecutor

        builder = NL2SQLDAGBuilder()
        dag = builder.build(question="上个月销售额是多少？", dialect="mysql")
        result = await DAGExecutor().run(dag)
    """

    # 节点类型常量
    NODE_TYPE_LLM = "llm"
    NODE_TYPE_COMPUTE = "compute"

    # NL2SQL 主流程节点名
    NODE_INTENT_ROUTE = "intent_route"
    NODE_INTENT_PARSE = "intent_parse"
    NODE_SCHEMA_LINK = "schema_link"
    NODE_PROMPT_BUILD = "prompt_build"
    NODE_SQL_GENERATE = "sql_generate"
    NODE_SQL_VALIDATE = "sql_validate"
    NODE_SQL_CORRECT = "sql_correct"
    NODE_SQL_EXPLAIN = "sql_explain"

    # 边缘分支条件
    COND_VALIDATE_PASSED = "validate_passed"
    COND_VALIDATE_FAILED = "validate_failed"

    # 意图路由输出值
    INTENT_SQL_QUERY = "sql_query"
    INTENT_CHITCHAT = "chitchat"
    INTENT_OUT_OF_SCOPE = "out_of_scope"

    def build(
        self,
        question: str,
        dialect: str = "mysql",
        tenant_id: str = "",
        session_id: str = "",
    ) -> DAGraph:
        """构建 NL2SQL DAG。

        对于 SQL 查询意图，构建完整的 8 节点 DAG；
        对于闲聊/超出范围意图，构建简化的单节点 DAG。

        Args:
            question: 用户自然语言问题。
            dialect: 目标 SQL 方言，默认 ``"mysql"``。
            tenant_id: 租户 ID。
            session_id: 会话 ID。

        Returns:
            构建完成的 DAGraph 实例。
        """
        from datapilot_dag import DAGraph

        dag = DAGraph(dag_id=DAGraph.generate_id())
        dag.context = {
            "question": question,
            "dialect": dialect,
            "tenant_id": tenant_id,
            "session_id": session_id,
        }

        logger.info(
            "开始构建 NL2SQL DAG",
            dag_id=dag.dag_id,
            question=question[:50],
            dialect=dialect,
        )

        # Level 0: 意图路由（始终首先执行）
        self._add_intent_route_node(dag, question)

        # 根据 intent_route 的输出决定后续 DAG 结构
        # 这里预注册所有 SQL 查询节点，但通过条件边控制执行路径
        self._add_sql_pipeline_nodes(dag, question, dialect, tenant_id, session_id)

        logger.info(
            "NL2SQL DAG 构建完成",
            dag_id=dag.dag_id,
            node_count=len(dag.nodes),
        )
        return dag

    def _add_intent_route_node(self, dag: DAGraph, question: str) -> None:
        """添加意图路由节点。"""
        from datapilot_dag import DAGNode

        node = DAGNode(
            name=self.NODE_INTENT_ROUTE,
            node_type=self.NODE_TYPE_LLM,
            func=self._intent_route_func,
            params={"question": question},
        )
        dag.add_node(node)

    def _add_sql_pipeline_nodes(
        self,
        dag: DAGraph,
        question: str,
        dialect: str,
        tenant_id: str,
        session_id: str,
    ) -> None:
        """添加 NL2SQL 主流程节点。"""
        from datapilot_dag import DAGNode

        # Level 1: 意图解析
        intent_parse = DAGNode(
            name=self.NODE_INTENT_PARSE,
            node_type=self.NODE_TYPE_LLM,
            func=self._intent_parse_func,
            params={"question": question},
        )
        dag.add_node(intent_parse)
        dag.add_edge(self.NODE_INTENT_ROUTE, self.NODE_INTENT_PARSE)

        # Level 2: Schema Linking
        schema_link = DAGNode(
            name=self.NODE_SCHEMA_LINK,
            node_type=self.NODE_TYPE_COMPUTE,
            func=self._schema_link_func,
            params={
                "question": question,
                "tenant_id": tenant_id,
            },
        )
        dag.add_node(schema_link)
        dag.add_edge(self.NODE_INTENT_PARSE, self.NODE_SCHEMA_LINK)

        # Level 3: Prompt 构建
        prompt_build = DAGNode(
            name=self.NODE_PROMPT_BUILD,
            node_type=self.NODE_TYPE_COMPUTE,
            func=self._prompt_build_func,
            params={"dialect": dialect},
        )
        dag.add_node(prompt_build)
        dag.add_edge(self.NODE_SCHEMA_LINK, self.NODE_PROMPT_BUILD)

        # Level 4: SQL 生成
        sql_generate = DAGNode(
            name=self.NODE_SQL_GENERATE,
            node_type=self.NODE_TYPE_LLM,
            func=self._sql_generate_func,
            params={"dialect": dialect},
        )
        dag.add_node(sql_generate)
        dag.add_edge(self.NODE_PROMPT_BUILD, self.NODE_SQL_GENERATE)

        # Level 5: SQL 校验
        sql_validate = DAGNode(
            name=self.NODE_SQL_VALIDATE,
            node_type=self.NODE_TYPE_COMPUTE,
            func=self._sql_validate_func,
        )
        dag.add_node(sql_validate)
        dag.add_edge(self.NODE_SQL_GENERATE, self.NODE_SQL_VALIDATE)

        # Level 6: SQL 纠错（条件分支，仅校验失败时执行）
        sql_correct = DAGNode(
            name=self.NODE_SQL_CORRECT,
            node_type=self.NODE_TYPE_LLM,
            func=self._sql_correct_func,
            params={"dialect": dialect},
        )
        dag.add_node(sql_correct)
        dag.add_edge(
            self.NODE_SQL_VALIDATE,
            self.NODE_SQL_CORRECT,
            condition=self.COND_VALIDATE_FAILED,
        )

        # Level 7: SQL 解释（依赖校验通过或纠错完成）
        sql_explain = DAGNode(
            name=self.NODE_SQL_EXPLAIN,
            node_type=self.NODE_TYPE_LLM,
            func=self._sql_explain_func,
        )
        dag.add_node(sql_explain)
        # 从 sql_validate 直接到 sql_explain（校验通过时）
        dag.add_edge(
            self.NODE_SQL_VALIDATE,
            self.NODE_SQL_EXPLAIN,
            condition=self.COND_VALIDATE_PASSED,
        )
        # 从 sql_correct 到 sql_explain（纠错后）
        dag.add_edge(self.NODE_SQL_CORRECT, self.NODE_SQL_EXPLAIN)

    # ------------------------------------------------------------------
    # 节点执行函数占位（实际实现由 executor 调用具体服务）
    # ------------------------------------------------------------------

    @staticmethod
    async def _intent_route_func(question: str, **_kwargs: object) -> dict:
        """意图路由节点执行函数。

        TODO: Sprint 7 接入真实 LLM 意图路由。
        """
        return {
            "intent": NL2SQLDAGBuilder.INTENT_SQL_QUERY,
            "confidence": 0.9,
        }

    @staticmethod
    async def _intent_parse_func(question: str, **_kwargs: object) -> dict:
        """意图解析节点执行函数。

        TODO: Sprint 7 接入真实 LLM 意图解析。
        """
        return {
            "raw_question": question,
            "intent_type": "sql_query",
            "filters": [],
            "metrics": [],
            "dimensions": [],
            "time_range": None,
        }

    @staticmethod
    async def _schema_link_func(question: str, tenant_id: str = "", **_kwargs: object) -> dict:
        """Schema Linking 节点执行函数。

        TODO: Sprint 7 接入 semantic-service。
        """
        return {
            "question": question,
            "tenant_id": tenant_id,
            "linked_tables": [],
            "linked_columns": [],
            "semantic_context": {},
        }

    @staticmethod
    async def _prompt_build_func(dialect: str = "mysql", **_kwargs: object) -> dict:
        """Prompt 构建节点执行函数。

        TODO: Sprint 7 接入 datapilot-prompt。
        """
        return {
            "dialect": dialect,
            "prompt_template": "",
            "few_shots": [],
        }

    @staticmethod
    async def _sql_generate_func(dialect: str = "mysql", **_kwargs: object) -> dict:
        """SQL 生成节点执行函数。

        TODO: Sprint 7 接入 LLM SQL 生成。
        """
        return {
            "sql": "",
            "dialect": dialect,
            "confidence": 0.0,
        }

    @staticmethod
    async def _sql_validate_func(**_kwargs: object) -> dict:
        """SQL 校验节点执行函数。

        TODO: Sprint 7 接入 guardrail-service。
        """
        return {
            "is_valid": True,
            "errors": [],
            "warnings": [],
        }

    @staticmethod
    async def _sql_correct_func(dialect: str = "mysql", **_kwargs: object) -> dict:
        """SQL 纠错节点执行函数（条件分支）。

        TODO: Sprint 7 接入 LLM 纠错。
        """
        return {
            "corrected_sql": "",
            "dialect": dialect,
        }

    @staticmethod
    async def _sql_explain_func(**_kwargs: object) -> dict:
        """SQL 解释节点执行函数。

        TODO: Sprint 7 接入 LLM 解释。
        """
        return {
            "explanation": "",
        }

    # ------------------------------------------------------------------
    # 简化 DAG（非 SQL 查询场景）
    # ------------------------------------------------------------------

    @staticmethod
    def _build_chitchat_dag(question: str) -> DAGraph:
        """构建闲聊场景 DAG（单节点）。

        Args:
            question: 用户自然语言问题。

        Returns:
            仅包含 chitchat 节点的 DAGraph。
        """
        from datapilot_dag import DAGNode, DAGraph

        dag = DAGraph(dag_id=DAGraph.generate_id())
        dag.context = {"question": question, "intent": "chitchat"}

        node = DAGNode(
            name="chitchat",
            node_type=NL2SQLDAGBuilder.NODE_TYPE_LLM,
            func=NL2SQLDAGBuilder._chitchat_func,
            params={"question": question},
        )
        dag.add_node(node)

        logger.info("闲聊 DAG 构建完成", dag_id=dag.dag_id)
        return dag

    @staticmethod
    async def _chitchat_func(question: str, **_kwargs: object) -> dict:
        """闲聊节点执行函数。

        TODO: Sprint 7 接入 LLM 闲聊。
        """
        return {
            "response": f"[Stub] 闲聊回复: {question}",
            "intent": "chitchat",
        }

    @staticmethod
    def _build_out_of_scope_dag(question: str) -> DAGraph:
        """构建超出范围 DAG（单节点）。

        Args:
            question: 用户自然语言问题。

        Returns:
            仅包含 out_of_scope 节点的 DAGraph。
        """
        from datapilot_dag import DAGNode, DAGraph

        dag = DAGraph(dag_id=DAGraph.generate_id())
        dag.context = {"question": question, "intent": "out_of_scope"}

        node = DAGNode(
            name="out_of_scope",
            node_type=NL2SQLDAGBuilder.NODE_TYPE_COMPUTE,
            func=NL2SQLDAGBuilder._out_of_scope_func,
            params={"question": question},
        )
        dag.add_node(node)

        logger.info("超出范围 DAG 构建完成", dag_id=dag.dag_id)
        return dag

    @staticmethod
    async def _out_of_scope_func(question: str, **_kwargs: object) -> dict:
        """超出范围节点执行函数。"""
        return {
            "response": "抱歉，您的问题超出了我的能力范围。我只能帮您查询和分析数据。",
            "intent": "out_of_scope",
        }
