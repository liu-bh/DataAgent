"""NL2SQL DAG 构建单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 确保项目源码路径可被导入
project_root = Path(__file__).resolve().parent.parent.parent.parent / "services" / "agent-service" / "src"
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

libs_root = Path(__file__).resolve().parent.parent.parent.parent / "libs"
for lib_dir in libs_root.iterdir():
    if lib_dir.is_dir():
        lib_src = lib_dir / "src"
        if lib_src.exists() and str(lib_src) not in sys.path:
            sys.path.insert(0, str(lib_src))


# ---------------------------------------------------------------------------
# Mock datapilot_dag 模块（Track A/B 尚未完成）
# ---------------------------------------------------------------------------

# 创建 mock DAGraph 和 DAGNode 类
_mock_dagraph_cls = MagicMock()
_mock_dagnode_cls = MagicMock()


def _setup_dag_mock() -> None:
    """配置 datapilot_dag 模块的 mock。"""
    import types

    # 确保 datapilot_dag 模块存在
    if "datapilot_dag" not in sys.modules:
        dag_module = types.ModuleType("datapilot_dag")
        sys.modules["datapilot_dag"] = dag_module

    dag_module = sys.modules["datapilot_dag"]

    # mock DAGNode
    if not hasattr(dag_module, "DAGNode"):
        _mock_dagnode_cls.reset_mock()
        # 让 DAGNode 保存参数
        def _dagnode_init(self: MagicMock, name: str, node_type: str, func: object, params: dict | None = None) -> None:
            self.name = name
            self.node_type = node_type
            self.func = func
            self.params = params or {}

        _mock_dagnode_cls.__init__ = _dagnode_init
        dag_module.DAGNode = _mock_dagnode_cls

    # mock DAGraph
    if not hasattr(dag_module, "DAGraph"):
        _mock_dagraph_cls.reset_mock()

        def _dagraph_init(self: MagicMock, dag_id: str) -> None:
            self.dag_id = dag_id
            self.nodes: dict[str, MagicMock] = {}
            self.context: dict = {}
            self._edges: list[tuple[str, str, str | None]] = []

        def _dagraph_generate_id() -> str:
            return "mock-dag-id-001"

        def _dagraph_add_node(self: MagicMock, node: MagicMock) -> None:
            self.nodes[node.name] = node

        def _dagraph_add_edge(self: MagicMock, from_node: str, to_node: str, condition: str | None = None) -> None:
            self._edges.append((from_node, to_node, condition))

        _mock_dagraph_cls.__init__ = _dagraph_init
        _mock_dagraph_cls.generate_id = staticmethod(_dagraph_generate_id)
        _mock_dagraph_cls.add_node = _dagraph_add_node
        _mock_dagraph_cls.add_edge = _dagraph_add_edge
        dag_module.DAGraph = _mock_dagraph_cls


_setup_dag_mock()


# ---------------------------------------------------------------------------
# 测试: NL2SQL 主流程 DAG 构建
# ---------------------------------------------------------------------------


class TestNL2SQLDAGBuilder:
    """NL2SQLDAGBuilder 测试。"""

    def setup_method(self) -> None:
        """每个测试前重置 mock。"""
        _mock_dagraph_cls.reset_mock()
        _mock_dagnode_cls.reset_mock()
        _setup_dag_mock()

        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        self.builder = NL2SQLDAGBuilder()

    def test_build_creates_dag_with_correct_nodes(self) -> None:
        """build() 应创建包含所有 8 个 NL2SQL 节点的 DAG。"""
        dag = self.builder.build(
            question="上个月销售额是多少？",
            dialect="mysql",
            tenant_id="tenant-001",
            session_id="session-001",
        )

        expected_nodes = [
            NL2SQLDAGBuilder.NODE_INTENT_ROUTE,
            NL2SQLDAGBuilder.NODE_INTENT_PARSE,
            NL2SQLDAGBuilder.NODE_SCHEMA_LINK,
            NL2SQLDAGBuilder.NODE_PROMPT_BUILD,
            NL2SQLDAGBuilder.NODE_SQL_GENERATE,
            NL2SQLDAGBuilder.NODE_SQL_VALIDATE,
            NL2SQLDAGBuilder.NODE_SQL_CORRECT,
            NL2SQLDAGBuilder.NODE_SQL_EXPLAIN,
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
        dag = self.builder.build(question="测试")

        edges = dag._edges
        edge_pairs = [(e[0], e[1]) for e in edges]

        # 检查顺序依赖边
        assert (NL2SQLDAGBuilder.NODE_INTENT_ROUTE, NL2SQLDAGBuilder.NODE_INTENT_PARSE) in edge_pairs
        assert (NL2SQLDAGBuilder.NODE_INTENT_PARSE, NL2SQLDAGBuilder.NODE_SCHEMA_LINK) in edge_pairs
        assert (NL2SQLDAGBuilder.NODE_SCHEMA_LINK, NL2SQLDAGBuilder.NODE_PROMPT_BUILD) in edge_pairs
        assert (NL2SQLDAGBuilder.NODE_PROMPT_BUILD, NL2SQLDAGBuilder.NODE_SQL_GENERATE) in edge_pairs
        assert (NL2SQLDAGBuilder.NODE_SQL_GENERATE, NL2SQLDAGBuilder.NODE_SQL_VALIDATE) in edge_pairs
        assert (NL2SQLDAGBuilder.NODE_SQL_CORRECT, NL2SQLDAGBuilder.NODE_SQL_EXPLAIN) in edge_pairs

    def test_build_creates_conditional_edge_for_correction(self) -> None:
        """build() 应为 SQL 纠错创建条件边。"""
        dag = self.builder.build(question="测试")

        conditional_edges = [e for e in dag._edges if e[2] is not None]

        # sql_validate -> sql_correct 带条件 validate_failed
        assert any(
            e[0] == NL2SQLDAGBuilder.NODE_SQL_VALIDATE
            and e[1] == NL2SQLDAGBuilder.NODE_SQL_CORRECT
            and e[2] == NL2SQLDAGBuilder.COND_VALIDATE_FAILED
            for e in conditional_edges
        )

    def test_build_creates_conditional_edge_for_explain(self) -> None:
        """build() 应为 SQL 解释创建条件边（校验通过时直接跳到解释）。"""
        dag = self.builder.build(question="测试")

        conditional_edges = [e for e in dag._edges if e[2] is not None]

        # sql_validate -> sql_explain 带条件 validate_passed
        assert any(
            e[0] == NL2SQLDAGBuilder.NODE_SQL_VALIDATE
            and e[1] == NL2SQLDAGBuilder.NODE_SQL_EXPLAIN
            and e[2] == NL2SQLDAGBuilder.COND_VALIDATE_PASSED
            for e in conditional_edges
        )

    def test_build_sets_correct_node_types(self) -> None:
        """build() 应为节点设置正确的类型。"""
        dag = self.builder.build(question="测试")

        llm_nodes = [
            NL2SQLDAGBuilder.NODE_INTENT_ROUTE,
            NL2SQLDAGBuilder.NODE_INTENT_PARSE,
            NL2SQLDAGBuilder.NODE_SQL_GENERATE,
            NL2SQLDAGBuilder.NODE_SQL_CORRECT,
            NL2SQLDAGBuilder.NODE_SQL_EXPLAIN,
        ]

        compute_nodes = [
            NL2SQLDAGBuilder.NODE_SCHEMA_LINK,
            NL2SQLDAGBuilder.NODE_PROMPT_BUILD,
            NL2SQLDAGBuilder.NODE_SQL_VALIDATE,
        ]

        for node_name in llm_nodes:
            assert dag.nodes[node_name].node_type == NL2SQLDAGBuilder.NODE_TYPE_LLM, (
                f"{node_name} 应为 LLM 类型"
            )

        for node_name in compute_nodes:
            assert dag.nodes[node_name].node_type == NL2SQLDAGBuilder.NODE_TYPE_COMPUTE, (
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

        _mock_dagraph_cls.reset_mock()
        _setup_dag_mock()

        dag = NL2SQLDAGBuilder._build_chitchat_dag("你好")

        assert len(dag.nodes) == 1
        assert "chitchat" in dag.nodes

    def test_chitchat_dag_context(self) -> None:
        """闲聊 DAG 的 context 应包含 intent=chitchat。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        _mock_dagraph_cls.reset_mock()
        _setup_dag_mock()

        dag = NL2SQLDAGBuilder._build_chitchat_dag("hello")

        assert dag.context["intent"] == "chitchat"
        assert dag.context["question"] == "hello"

    def test_chitchat_dag_no_edges(self) -> None:
        """闲聊 DAG 不应有任何边。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        _mock_dagraph_cls.reset_mock()
        _setup_dag_mock()

        dag = NL2SQLDAGBuilder._build_chitchat_dag("测试闲聊")

        assert len(dag._edges) == 0


# ---------------------------------------------------------------------------
# 测试: 超出范围 DAG 构建
# ---------------------------------------------------------------------------


class TestOutOfScopeDAG:
    """超出范围场景 DAG 构建测试。"""

    def test_out_of_scope_dag_single_node(self) -> None:
        """超出范围 DAG 应仅包含一个节点。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        _mock_dagraph_cls.reset_mock()
        _setup_dag_mock()

        dag = NL2SQLDAGBuilder._build_out_of_scope_dag("帮我写一首诗")

        assert len(dag.nodes) == 1
        assert "out_of_scope" in dag.nodes

    def test_out_of_scope_dag_context(self) -> None:
        """超出范围 DAG 的 context 应包含 intent=out_of_scope。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        _mock_dagraph_cls.reset_mock()
        _setup_dag_mock()

        dag = NL2SQLDAGBuilder._build_out_of_scope_dag("写代码")

        assert dag.context["intent"] == "out_of_scope"
        assert dag.context["question"] == "写代码"

    def test_out_of_scope_dag_no_edges(self) -> None:
        """超出范围 DAG 不应有任何边。"""
        from datapilot_agent.dag.nl2sql_dag import NL2SQLDAGBuilder

        _mock_dagraph_cls.reset_mock()
        _setup_dag_mock()

        dag = NL2SQLDAGBuilder._build_out_of_scope_dag("测试")

        assert len(dag._edges) == 0


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
