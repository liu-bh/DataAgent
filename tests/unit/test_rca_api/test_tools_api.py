"""工具发现和执行 API 单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

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
# Mock datapilot_dag 模块（被 DAG API 路由依赖）
# ---------------------------------------------------------------------------


def _setup_dag_mock() -> None:
    """配置 datapilot_dag 模块的 mock。"""
    if "datapilot_dag" not in sys.modules:
        import types
        dag_module = types.ModuleType("datapilot_dag")
        sys.modules["datapilot_dag"] = dag_module

    dag_module = sys.modules["datapilot_dag"]

    if not hasattr(dag_module, "DAGNode"):
        def _dagnode_init(self, name: str, node_type: str, func: object, params: dict | None = None) -> None:
            self.name = name
            self.node_type = node_type
            self.func = func
            self.params = params or {}

        mock_node = type("DAGNode", (), {"__init__": _dagnode_init})
        dag_module.DAGNode = mock_node

    if not hasattr(dag_module, "DAGraph"):
        def _dagraph_init(self, dag_id: str) -> None:
            self.dag_id = dag_id
            self.nodes: dict = {}
            self.context: dict = {}
            self._edges: list = []

        mock_graph = type("DAGraph", (), {
            "__init__": _dagraph_init,
            "generate_id": staticmethod(lambda: "test-dag-id"),
            "add_node": lambda self, node: self.nodes.__setitem__(node.name, node),
            "add_edge": lambda self, from_n, to_n, condition=None: self._edges.append((from_n, to_n, condition)),
        })
        dag_module.DAGraph = mock_graph


_setup_dag_mock()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_client() -> AsyncClient:
    """创建测试用 FastAPI 客户端。"""
    from datapilot_agent import app

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    return client


# ---------------------------------------------------------------------------
# 测试: GET /api/v1/tools — 发现所有工具
# ---------------------------------------------------------------------------


class TestListToolsEndpoint:
    """GET /api/v1/tools 测试。"""

    @pytest.mark.asyncio
    async def test_list_tools_success(self, app_client: AsyncClient) -> None:
        """正常请求应返回工具列表。"""
        response = await app_client.get("/api/v1/tools")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3

    @pytest.mark.asyncio
    async def test_list_tools_has_required_fields(self, app_client: AsyncClient) -> None:
        """返回的工具应包含必要字段。"""
        response = await app_client.get("/api/v1/tools")
        data = response.json()

        for tool in data:
            assert "name" in tool
            assert "description" in tool
            assert "category" in tool
            assert "parameters" in tool
            assert "version" in tool

    @pytest.mark.asyncio
    async def test_list_tools_categories(self, app_client: AsyncClient) -> None:
        """应包含多个类别的工具。"""
        response = await app_client.get("/api/v1/tools")
        data = response.json()

        categories = {tool["category"] for tool in data}
        assert "sql" in categories
        assert "python" in categories
        assert "analysis" in categories

    @pytest.mark.asyncio
    async def test_list_tools_sql_query_params(self, app_client: AsyncClient) -> None:
        """sql_query 工具应包含 sql 和 dialect 参数。"""
        response = await app_client.get("/api/v1/tools")
        data = response.json()

        sql_tool = next((t for t in data if t["name"] == "sql_query"), None)
        assert sql_tool is not None
        param_names = {p["name"] for p in sql_tool["parameters"]}
        assert "sql" in param_names
        assert "dialect" in param_names


# ---------------------------------------------------------------------------
# 测试: GET /api/v1/tools/{name} — 获取工具详情
# ---------------------------------------------------------------------------


class TestGetToolEndpoint:
    """GET /api/v1/tools/{name} 测试。"""

    @pytest.mark.asyncio
    async def test_get_existing_tool(self, app_client: AsyncClient) -> None:
        """获取存在的工具应返回详情。"""
        response = await app_client.get("/api/v1/tools/sql_query")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "sql_query"
        assert data["category"] == "sql"

    @pytest.mark.asyncio
    async def test_get_nonexistent_tool(self, app_client: AsyncClient) -> None:
        """获取不存在的工具应返回 404。"""
        response = await app_client.get("/api/v1/tools/nonexistent_tool")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_rca_analyze_tool(self, app_client: AsyncClient) -> None:
        """获取 rca_analyze 工具应返回正确信息。"""
        response = await app_client.get("/api/v1/tools/rca_analyze")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "rca_analyze"
        assert data["category"] == "analysis"

    @pytest.mark.asyncio
    async def test_get_tool_version(self, app_client: AsyncClient) -> None:
        """工具版本应为 1.0.0。"""
        response = await app_client.get("/api/v1/tools/sql_query")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0.0"


# ---------------------------------------------------------------------------
# 测试: POST /api/v1/tools/execute — 执行工具
# ---------------------------------------------------------------------------


class TestExecuteToolEndpoint:
    """POST /api/v1/tools/execute 测试。"""

    @pytest.mark.asyncio
    async def test_execute_existing_tool(self, app_client: AsyncClient) -> None:
        """执行存在的工具应返回成功结果。"""
        response = await app_client.post(
            "/api/v1/tools/execute",
            json={
                "name": "sql_query",
                "arguments": {"sql": "SELECT 1", "dialect": "mysql"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["output"] is not None
        assert data["execution_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self, app_client: AsyncClient) -> None:
        """执行不存在的工具应返回 404。"""
        response = await app_client.post(
            "/api/v1/tools/execute",
            json={"name": "nonexistent", "arguments": {}},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_execute_missing_name(self, app_client: AsyncClient) -> None:
        """缺少 name 字段应返回 422。"""
        response = await app_client.post(
            "/api/v1/tools/execute",
            json={"arguments": {}},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_execute_empty_name(self, app_client: AsyncClient) -> None:
        """空 name 应返回 422。"""
        response = await app_client.post(
            "/api/v1/tools/execute",
            json={"name": "", "arguments": {}},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_execute_default_arguments(self, app_client: AsyncClient) -> None:
        """不传 arguments 应使用默认空字典。"""
        response = await app_client.post(
            "/api/v1/tools/execute",
            json={"name": "sql_query"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_execute_output_contains_tool_name(self, app_client: AsyncClient) -> None:
        """执行结果应包含工具名称。"""
        response = await app_client.post(
            "/api/v1/tools/execute",
            json={"name": "python_execute", "arguments": {"code": "print('hello')"}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["output"]["tool"] == "python_execute"

    @pytest.mark.asyncio
    async def test_execute_output_contains_arguments(self, app_client: AsyncClient) -> None:
        """执行结果应包含传入的参数。"""
        args = {"sql": "SELECT * FROM users"}
        response = await app_client.post(
            "/api/v1/tools/execute",
            json={"name": "sql_query", "arguments": args},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["output"]["arguments"] == args

    @pytest.mark.asyncio
    async def test_execute_rca_analyze_tool(self, app_client: AsyncClient) -> None:
        """执行 rca_analyze 工具应返回成功。"""
        response = await app_client.post(
            "/api/v1/tools/execute",
            json={
                "name": "rca_analyze",
                "arguments": {"question": "为什么销售额下降", "metric_name": "销售额"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
