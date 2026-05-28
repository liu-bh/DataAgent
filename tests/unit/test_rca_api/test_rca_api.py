"""RCA 根因分析 API 单元测试。"""

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


@pytest.fixture
def analyze_request_body() -> dict:
    """标准 RCA 分析请求体。"""
    return {
        "question": "为什么上月销售额下降了？",
        "metric_name": "销售额",
        "current_data": {"value": 850000},
        "baseline_data": {"value": 1000000},
        "dimensions": [{"name": "城市"}, {"name": "品类"}],
    }


# ---------------------------------------------------------------------------
# 测试: POST /api/v1/rca/analyze — 执行 RCA 分析
# ---------------------------------------------------------------------------


class TestAnalyzeRCAEndpoint:
    """POST /api/v1/rca/analyze 测试。"""

    @pytest.mark.asyncio
    async def test_analyze_success(self, app_client: AsyncClient, analyze_request_body: dict) -> None:
        """正常请求应返回分析结果。"""
        response = await app_client.post("/api/v1/rca/analyze", json=analyze_request_body)

        assert response.status_code == 200
        data = response.json()
        assert "analysis_id" in data
        assert data["analysis_id"].startswith("rca-")
        assert "report" in data
        assert "execution_time_ms" in data
        assert data["execution_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_analyze_report_contains_anomaly(self, app_client: AsyncClient, analyze_request_body: dict) -> None:
        """分析报告应包含异常检测结果。"""
        response = await app_client.post("/api/v1/rca/analyze", json=analyze_request_body)

        assert response.status_code == 200
        data = response.json()
        report = data["report"]
        assert "anomaly" in report
        anomaly = report["anomaly"]
        assert "metric_name" in anomaly
        assert "current_value" in anomaly
        assert "baseline_value" in anomaly
        assert "change_percent" in anomaly
        assert "is_anomaly" in anomaly

    @pytest.mark.asyncio
    async def test_analyze_change_percent_calculation(self, app_client: AsyncClient) -> None:
        """变化百分比计算应正确（850k vs 1000k = -15%）。"""
        response = await app_client.post(
            "/api/v1/rca/analyze",
            json={
                "question": "测试变化百分比",
                "metric_name": "测试指标",
                "current_data": {"value": 850000},
                "baseline_data": {"value": 1000000},
            },
        )

        assert response.status_code == 200
        data = response.json()
        change_percent = data["report"]["anomaly"]["change_percent"]
        assert abs(change_percent - (-15.0)) < 0.01

    @pytest.mark.asyncio
    async def test_anomaly_type_for_decline(self, app_client: AsyncClient) -> None:
        """下降趋势应标记为 drop 类型。"""
        response = await app_client.post(
            "/api/v1/rca/analyze",
            json={
                "question": "下降测试",
                "metric_name": "收入",
                "current_data": {"value": 800},
                "baseline_data": {"value": 1000},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["report"]["anomaly"]["anomaly_type"] == "drop"

    @pytest.mark.asyncio
    async def test_anomaly_type_for_increase(self, app_client: AsyncClient) -> None:
        """上升趋势应标记为 spike 类型。"""
        response = await app_client.post(
            "/api/v1/rca/analyze",
            json={
                "question": "上升测试",
                "metric_name": "收入",
                "current_data": {"value": 1200},
                "baseline_data": {"value": 1000},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["report"]["anomaly"]["anomaly_type"] == "spike"

    @pytest.mark.asyncio
    async def test_analyze_with_dimensions(self, app_client: AsyncClient, analyze_request_body: dict) -> None:
        """提供维度时应生成下钻结果。"""
        response = await app_client.post("/api/v1/rca/analyze", json=analyze_request_body)

        assert response.status_code == 200
        data = response.json()
        report = data["report"]
        assert "drill_downs" in report
        assert len(report["drill_downs"]) > 0

    @pytest.mark.asyncio
    async def test_analyze_without_dimensions(self, app_client: AsyncClient) -> None:
        """不提供维度时应正常返回。"""
        response = await app_client.post(
            "/api/v1/rca/analyze",
            json={
                "question": "无维度测试",
                "metric_name": "GMV",
                "current_data": {"value": 5000},
                "baseline_data": {"value": 6000},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["report"]["drill_downs"] == []

    @pytest.mark.asyncio
    async def test_analyze_contains_attribution(self, app_client: AsyncClient, analyze_request_body: dict) -> None:
        """分析报告应包含归因分析结果。"""
        response = await app_client.post("/api/v1/rca/analyze", json=analyze_request_body)

        assert response.status_code == 200
        data = response.json()
        report = data["report"]
        assert "attribution" in report
        attribution = report["attribution"]
        assert "total_change" in attribution
        assert "dimensions" in attribution

    @pytest.mark.asyncio
    async def test_analyze_missing_question(self, app_client: AsyncClient) -> None:
        """缺少 question 应返回 422。"""
        response = await app_client.post(
            "/api/v1/rca/analyze",
            json={
                "metric_name": "销售额",
                "current_data": {"value": 8500},
                "baseline_data": {"value": 10000},
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_analyze_missing_metric_name(self, app_client: AsyncClient) -> None:
        """缺少 metric_name 应返回 422。"""
        response = await app_client.post(
            "/api/v1/rca/analyze",
            json={
                "question": "为什么下降？",
                "current_data": {"value": 8500},
                "baseline_data": {"value": 10000},
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_analyze_empty_question(self, app_client: AsyncClient) -> None:
        """空 question 应返回 422。"""
        response = await app_client.post(
            "/api/v1/rca/analyze",
            json={
                "question": "",
                "metric_name": "销售额",
                "current_data": {"value": 8500},
                "baseline_data": {"value": 10000},
            },
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 测试: GET /api/v1/rca/{analysis_id}/result — 获取分析结果
# ---------------------------------------------------------------------------


class TestGetRCAResultEndpoint:
    """GET /api/v1/rca/{analysis_id}/result 测试。"""

    @pytest.mark.asyncio
    async def test_get_existing_result(self, app_client: AsyncClient, analyze_request_body: dict) -> None:
        """查询已存在的分析结果应返回报告。"""
        # 先执行分析
        analyze_response = await app_client.post("/api/v1/rca/analyze", json=analyze_request_body)
        analysis_id = analyze_response.json()["analysis_id"]

        # 查询结果
        result_response = await app_client.get(f"/api/v1/rca/{analysis_id}/result")

        assert result_response.status_code == 200
        data = result_response.json()
        assert data["analysis_id"] == analysis_id
        assert "anomaly" in data

    @pytest.mark.asyncio
    async def test_get_nonexistent_result(self, app_client: AsyncClient) -> None:
        """查询不存在的分析结果应返回 404。"""
        response = await app_client.get("/api/v1/rca/nonexistent-id/result")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 测试: GET /api/v1/rca/history — 获取分析历史
# ---------------------------------------------------------------------------


class TestRCAHistoryEndpoint:
    """GET /api/v1/rca/history 测试。"""

    @pytest.mark.asyncio
    async def test_history_empty(self, app_client: AsyncClient) -> None:
        """无分析记录时应返回空列表。"""
        response = await app_client.get("/api/v1/rca/history")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_history_returns_records(self, app_client: AsyncClient, analyze_request_body: dict) -> None:
        """执行分析后历史记录应包含该记录。"""
        await app_client.post("/api/v1/rca/analyze", json=analyze_request_body)
        await app_client.post("/api/v1/rca/analyze", json=analyze_request_body)

        response = await app_client.get("/api/v1/rca/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

    @pytest.mark.asyncio
    async def test_history_item_structure(self, app_client: AsyncClient, analyze_request_body: dict) -> None:
        """历史记录条目应包含必要字段。"""
        await app_client.post("/api/v1/rca/analyze", json=analyze_request_body)

        response = await app_client.get("/api/v1/rca/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

        item = data[0]
        assert "analysis_id" in item
        assert "question" in item
        assert "metric_name" in item
        assert "anomaly_detected" in item
        assert "change_percent" in item
