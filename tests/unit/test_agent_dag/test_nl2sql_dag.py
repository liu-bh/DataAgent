"""NL2SQL DAG 构建单元测试。"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# 测试: NL2SQL 主流程 DAG 构建
# ---------------------------------------------------------------------------


class TestNL2SQLDAGBuilder:
    """NL2SQLDAGBuilder 测试。"""

    def setup_method(self) -> None:
        """每个测试前初始化 builder。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        self.Builder = NL2SQLDAGBuilder
        self.builder = NL2SQLDAGBuilder()

    def test_build_creates_dag_with_correct_nodes(self) -> None:
        """build() 应创建包含所有 8 个 NL2SQL 节点的 DAG。"""
        B = self.Builder
        dag = self.builder.build(
            question="上个月销售额是多少？",
            dialect="mysql",
            tenant_id="tenant-001",
            session_id="session-001",
        )

        expected_nodes = [
            B.NODE_INTENT_ROUTE,
            B.NODE_INTENT_PARSE,
            B.NODE_SCHEMA_LINK,
            B.NODE_PROMPT_BUILD,
            B.NODE_SQL_GENERATE,
            B.NODE_SQL_VALIDATE,
            B.NODE_SQL_CORRECT,
            B.NODE_SQL_EXPLAIN,
        ]

        for node_name in expected_nodes:
            assert node_name in dag.nodes, f"缺少节点: {node_name}"

    def test_build_creates_dag_with_context(self) -> None:
        """build() 应在 DAG context 中保存参数。"""
        dag = self.builder.build(
            question="测试问题",
            dialect="postgres",
            tenant_id="t1",
            session_id="s1",
        )

        assert dag.context["question"] == "测试问题"
        assert dag.context["dialect"] == "postgres"
        assert dag.context["tenant_id"] == "t1"
        assert dag.context["session_id"] == "s1"

    def test_build_creates_edges_between_levels(self) -> None:
        """build() 应在节点间创建正确的有向边。"""
        B = self.Builder
        dag = self.builder.build(question="测试")

        edges = dag.edges
        edge_pairs = [(e.source_id, e.target_id) for e in edges]

        assert (B.NODE_INTENT_ROUTE, B.NODE_INTENT_PARSE) in edge_pairs
        assert (B.NODE_INTENT_PARSE, B.NODE_SCHEMA_LINK) in edge_pairs
        assert (B.NODE_SCHEMA_LINK, B.NODE_PROMPT_BUILD) in edge_pairs
        assert (B.NODE_PROMPT_BUILD, B.NODE_SQL_GENERATE) in edge_pairs
        assert (B.NODE_SQL_GENERATE, B.NODE_SQL_VALIDATE) in edge_pairs
        assert (B.NODE_SQL_CORRECT, B.NODE_SQL_EXPLAIN) in edge_pairs

    def test_build_creates_conditional_edge_for_correction(self) -> None:
        """build() 应为 SQL 纠错创建条件边。"""
        B = self.Builder
        dag = self.builder.build(question="测试")

        conditional_edges = [e for e in dag.edges if e.condition]

        assert any(
            e.source_id == B.NODE_SQL_VALIDATE
            and e.target_id == B.NODE_SQL_CORRECT
            and e.condition == B.COND_VALIDATE_FAILED
            for e in conditional_edges
        )

    def test_build_creates_conditional_edge_for_explain(self) -> None:
        """build() 应为 SQL 解释创建条件边（校验通过时直接跳到解释）。"""
        B = self.Builder
        dag = self.builder.build(question="测试")

        conditional_edges = [e for e in dag.edges if e.condition]

        assert any(
            e.source_id == B.NODE_SQL_VALIDATE
            and e.target_id == B.NODE_SQL_EXPLAIN
            and e.condition == B.COND_VALIDATE_PASSED
            for e in conditional_edges
        )

    def test_build_sets_correct_node_types(self) -> None:
        """build() 应为节点设置正确的类型。"""
        from datapilot_dag import TaskType

        B = self.Builder
        dag = self.builder.build(question="测试")

        llm_nodes = [
            B.NODE_INTENT_ROUTE,
            B.NODE_INTENT_PARSE,
            B.NODE_SQL_GENERATE,
            B.NODE_SQL_CORRECT,
            B.NODE_SQL_EXPLAIN,
        ]

        compute_nodes = [
            B.NODE_SCHEMA_LINK,
            B.NODE_PROMPT_BUILD,
            B.NODE_SQL_VALIDATE,
        ]

        for node_name in llm_nodes:
            assert dag.nodes[node_name].task_type == TaskType.LLM, (
                f"{node_name} 应为 LLM 类型"
            )

        for node_name in compute_nodes:
            assert dag.nodes[node_name].task_type == TaskType.COMPUTE, (
                f"{node_name} 应为计算类型"
            )

    def test_build_with_default_parameters(self) -> None:
        """build() 使用默认参数时应正常工作。"""
        dag = self.builder.build(question="默认参数测试")

        assert len(dag.nodes) == 8
        assert dag.context["dialect"] == "mysql"
        assert dag.context["tenant_id"] == ""
        assert dag.context["session_id"] == ""


# ---------------------------------------------------------------------------
# 测试: 闲聊 DAG 构建
# ---------------------------------------------------------------------------


class TestChitchatDAG:
    """闲聊场景 DAG 构建测试。"""

    def test_chitchat_dag_single_node(self) -> None:
        """闲聊 DAG 应仅包含一个节点。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        dag = NL2SQLDAGBuilder._build_chitchat_dag("你好")

        assert len(dag.nodes) == 1
        assert "chitchat" in dag.nodes

    def test_chitchat_dag_context(self) -> None:
        """闲聊 DAG 的 context 应包含 intent=chitchat。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        dag = NL2SQLDAGBuilder._build_chitchat_dag("hello")

        assert dag.context["intent"] == "chitchat"
        assert dag.context["question"] == "hello"

    def test_chitchat_dag_no_edges(self) -> None:
        """闲聊 DAG 不应有任何边。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        dag = NL2SQLDAGBuilder._build_chitchat_dag("测试闲聊")

        assert len(dag.edges) == 0


# ---------------------------------------------------------------------------
# 测试: 超出范围 DAG 构建
# ---------------------------------------------------------------------------


class TestOutOfScopeDAG:
    """超出范围场景 DAG 构建测试。"""

    def test_out_of_scope_dag_single_node(self) -> None:
        """超出范围 DAG 应仅包含一个节点。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        dag = NL2SQLDAGBuilder._build_out_of_scope_dag("帮我写一首诗")

        assert len(dag.nodes) == 1
        assert "out_of_scope" in dag.nodes

    def test_out_of_scope_dag_context(self) -> None:
        """超出范围 DAG 的 context 应包含 intent=out_of_scope。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        dag = NL2SQLDAGBuilder._build_out_of_scope_dag("写代码")

        assert dag.context["intent"] == "out_of_scope"
        assert dag.context["question"] == "写代码"

    def test_out_of_scope_dag_no_edges(self) -> None:
        """超出范围 DAG 不应有任何边。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        dag = NL2SQLDAGBuilder._build_out_of_scope_dag("测试")

        assert len(dag.edges) == 0


# ---------------------------------------------------------------------------
# 测试: 节点执行函数（占位 stub）
# ---------------------------------------------------------------------------


class TestNodeFunctions:
    """节点执行函数测试。"""

    @pytest.mark.asyncio
    async def test_intent_route_func_returns_dict(self) -> None:
        """意图路由函数应返回包含 intent 和 confidence 的字典。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        result = await NL2SQLDAGBuilder._intent_route_func(question="测试")
        assert isinstance(result, dict)
        assert "intent" in result
        assert "confidence" in result

    @pytest.mark.asyncio
    async def test_intent_parse_func_returns_dict(self) -> None:
        """意图解析函数应返回包含解析结果的字典。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        result = await NL2SQLDAGBuilder._intent_parse_func(question="测试问题")
        assert isinstance(result, dict)
        assert "raw_question" in result
        assert "intent_type" in result

    @pytest.mark.asyncio
    async def test_schema_link_func_returns_dict(self) -> None:
        """Schema Linking 函数应返回包含链接结果的字典。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        result = await NL2SQLDAGBuilder._schema_link_func(question="测试", tenant_id="t1")
        assert isinstance(result, dict)
        assert "linked_tables" in result

    @pytest.mark.asyncio
    async def test_sql_generate_func_returns_dict(self) -> None:
        """SQL 生成函数应返回包含 SQL 的字典。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        result = await NL2SQLDAGBuilder._sql_generate_func(dialect="mysql")
        assert isinstance(result, dict)
        assert "sql" in result
        assert "dialect" in result

    @pytest.mark.asyncio
    async def test_sql_validate_func_returns_dict(self) -> None:
        """SQL 校验函数应返回包含校验结果的字典。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        result = await NL2SQLDAGBuilder._sql_validate_func()
        assert isinstance(result, dict)
        assert "is_valid" in result
        assert "errors" in result

    @pytest.mark.asyncio
    async def test_sql_correct_func_returns_dict(self) -> None:
        """SQL 纠错函数应返回包含纠错结果的字典。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        result = await NL2SQLDAGBuilder._sql_correct_func(dialect="mysql")
        assert isinstance(result, dict)
        assert "corrected_sql" in result

    @pytest.mark.asyncio
    async def test_sql_explain_func_returns_dict(self) -> None:
        """SQL 解释函数应返回包含解释的字典。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        result = await NL2SQLDAGBuilder._sql_explain_func()
        assert isinstance(result, dict)
        assert "explanation" in result

    @pytest.mark.asyncio
    async def test_chitchat_func_returns_response(self) -> None:
        """闲聊函数应返回包含回复的字典。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        result = await NL2SQLDAGBuilder._chitchat_func(question="你好")
        assert isinstance(result, dict)
        assert "response" in result
        assert "intent" in result
        assert result["intent"] == "chitchat"

    @pytest.mark.asyncio
    async def test_out_of_scope_func_returns_response(self) -> None:
        """超出范围函数应返回包含回复的字典。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        result = await NL2SQLDAGBuilder._out_of_scope_func(question="帮我写诗")
        assert isinstance(result, dict)
        assert "response" in result
        assert "intent" in result
        assert result["intent"] == "out_of_scope"
