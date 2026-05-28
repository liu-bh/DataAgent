"""Chart API 单元测试。"""

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
        sys.modules["datapilot_dag"] = types.ModuleType("datapilot_dag")

    dag_module = sys.modules["datapilot_dag"]
    if not hasattr(dag_module, "DAGNode"):
        def _dagnode_init(self, name: str, node_type: str, func: object, params: dict | None = None) -> None:
            self.name = name
            self.node_type = node_type
            self.func = func
            self.params = params or {}

        dag_module.DAGNode = type("DAGNode", (), {"__init__": _dagnode_init})

    if not hasattr(dag_module, "DAGraph"):
        def _dagraph_init(self, dag_id: str) -> None:
            self.dag_id = dag_id
            self.nodes: dict = {}
            self.context: dict = {}
            self._edges: list = []

        dag_module.DAGraph = type("DAGraph", (), {
            "__init__": _dagraph_init,
            "generate_id": staticmethod(lambda: "test-dag-id"),
            "add_node": lambda self, node: self.nodes.__setitem__(node.name, node),
            "add_edge": lambda self, from_n, to_n, condition=None: self._edges.append((from_n, to_n, condition)),
        })


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
def time_series_request() -> dict:
    """时间序列推荐请求。"""
    return {
        "columns": [
            {"name": "日期", "type": "date"},
            {"name": "销售额", "type": "integer"},
            {"name": "订单数", "type": "integer"},
        ],
        "rows": [
            {"日期": "2024-01", "销售额": 1000, "订单数": 50},
            {"日期": "2024-02", "销售额": 1200, "订单数": 60},
            {"日期": "2024-03", "销售额": 900, "订单数": 45},
        ],
        "user_question": "",
    }


@pytest.fixture
def categorical_request() -> dict:
    """分类数据推荐请求。"""
    return {
        "columns": [
            {"name": "城市", "type": "string"},
            {"name": "销售额", "type": "integer"},
        ],
        "rows": [
            {"城市": "北京", "销售额": 5000},
            {"城市": "上海", "销售额": 6000},
            {"城市": "深圳", "销售额": 4000},
        ],
        "user_question": "",
    }


@pytest.fixture
def pie_request() -> dict:
    """饼图推荐请求（少量分类数据）。"""
    return {
        "columns": [
            {"name": "产品", "type": "string"},
            {"name": "销量", "type": "integer"},
        ],
        "rows": [
            {"产品": "A", "销量": 300},
            {"产品": "B", "销量": 200},
            {"产品": "C", "销量": 150},
            {"产品": "D", "销量": 100},
            {"产品": "E", "销量": 80},
        ],
        "user_question": "各产品销量占比",
    }


# ---------------------------------------------------------------------------
# 测试: POST /api/v1/chart/recommend
# ---------------------------------------------------------------------------


class TestChartRecommendEndpoint:
    """POST /api/v1/chart/recommend 测试。"""

    @pytest.mark.asyncio
    async def test_recommend_time_series(self, app_client: AsyncClient, time_series_request: dict) -> None:
        """时间序列数据应推荐折线图。"""
        response = await app_client.post("/api/v1/chart/recommend", json=time_series_request)

        assert response.status_code == 200
        data = response.json()
        assert "recommended_types" in data
        assert "x_field" in data
        assert "y_fields" in data

        # 时间序列应推荐 line
        types_list = [r["type"] for r in data["recommended_types"]]
        assert "line" in types_list
        assert data["x_field"] == "日期"
        assert "销售额" in data["y_fields"]

    @pytest.mark.asyncio
    async def test_recommend_categorical(self, app_client: AsyncClient, categorical_request: dict) -> None:
        """分类数据应推荐柱状图。"""
        response = await app_client.post("/api/v1/chart/recommend", json=categorical_request)

        assert response.status_code == 200
        data = response.json()
        types_list = [r["type"] for r in data["recommended_types"]]
        assert "bar" in types_list
        assert data["x_field"] == "城市"

    @pytest.mark.asyncio
    async def test_recommend_pie_for_proportion(self, app_client: AsyncClient, pie_request: dict) -> None:
        """占比问题应推荐饼图。"""
        response = await app_client.post("/api/v1/chart/recommend", json=pie_request)

        assert response.status_code == 200
        data = response.json()
        types_list = [r["type"] for r in data["recommended_types"]]
        assert "pie" in types_list

    @pytest.mark.asyncio
    async def test_recommend_user_question_trend(self, app_client: AsyncClient) -> None:
        """用户问题包含「趋势」应提升折线图优先级。"""
        request = {
            "columns": [
                {"name": "月份", "type": "string"},
                {"name": "收入", "type": "integer"},
            ],
            "rows": [
                {"月份": "1月", "收入": 100},
                {"月份": "2月", "收入": 200},
            ],
            "user_question": "收入变化趋势如何",
        }
        response = await app_client.post("/api/v1/chart/recommend", json=request)

        assert response.status_code == 200
        data = response.json()
        types_list = [r["type"] for r in data["recommended_types"]]
        assert "line" in types_list

    @pytest.mark.asyncio
    async def test_recommend_confidence_present(self, app_client: AsyncClient, time_series_request: dict) -> None:
        """推荐结果应包含 confidence 字段。"""
        response = await app_client.post("/api/v1/chart/recommend", json=time_series_request)

        assert response.status_code == 200
        data = response.json()
        for rec in data["recommended_types"]:
            assert "confidence" in rec
            assert 0 <= rec["confidence"] <= 1
            assert "title" in rec
            assert "description" in rec

    @pytest.mark.asyncio
    async def test_recommend_empty_columns(self, app_client: AsyncClient) -> None:
        """空列应返回空推荐。"""
        response = await app_client.post("/api/v1/chart/recommend", json={
            "columns": [],
            "rows": [],
            "user_question": "测试",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["recommended_types"] == []

    @pytest.mark.asyncio
    async def test_recommend_missing_columns_field(self, app_client: AsyncClient) -> None:
        """缺少 columns 字段应返回 422。"""
        response = await app_client.post("/api/v1/chart/recommend", json={
            "rows": [],
        })

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_recommend_default_user_question(self, app_client: AsyncClient, categorical_request: dict) -> None:
        """user_question 默认为空时应正常返回。"""
        del categorical_request["user_question"]
        response = await app_client.post("/api/v1/chart/recommend", json=categorical_request)

        assert response.status_code == 200
        data = response.json()
        assert len(data["recommended_types"]) > 0


# ---------------------------------------------------------------------------
# 测试: POST /api/v1/chart/render
# ---------------------------------------------------------------------------


class TestChartRenderEndpoint:
    """POST /api/v1/chart/render 测试。"""

    @pytest.mark.asyncio
    async def test_render_bar_chart(self, app_client: AsyncClient) -> None:
        """渲染柱状图应返回 ECharts 配置。"""
        request = {
            "chart_type": "bar",
            "columns": [
                {"name": "城市", "type": "string"},
                {"name": "销售额", "type": "integer"},
            ],
            "rows": [
                {"城市": "北京", "销售额": 5000},
                {"城市": "上海", "销售额": 6000},
            ],
            "x_field": "城市",
            "y_fields": ["销售额"],
            "title": "城市销售额",
        }
        response = await app_client.post("/api/v1/chart/render", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["chart_type"] == "bar"
        assert data["title"] == "城市销售额"
        assert "echarts_option" in data
        option = data["echarts_option"]
        assert "xAxis" in option
        assert "yAxis" in option
        assert "series" in option
        assert len(option["series"]) == 1
        assert option["series"][0]["type"] == "bar"

    @pytest.mark.asyncio
    async def test_render_line_chart(self, app_client: AsyncClient) -> None:
        """渲染折线图应返回正确的 series 类型。"""
        request = {
            "chart_type": "line",
            "columns": [
                {"name": "月份", "type": "string"},
                {"name": "收入", "type": "integer"},
            ],
            "rows": [
                {"月份": "1月", "收入": 100},
                {"月份": "2月", "收入": 200},
            ],
            "x_field": "月份",
            "y_fields": ["收入"],
            "title": "月收入趋势",
        }
        response = await app_client.post("/api/v1/chart/render", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["echarts_option"]["series"][0]["type"] == "line"

    @pytest.mark.asyncio
    async def test_render_pie_chart(self, app_client: AsyncClient) -> None:
        """渲染饼图应使用饼图专用格式。"""
        request = {
            "chart_type": "pie",
            "columns": [
                {"name": "类别", "type": "string"},
                {"name": "数量", "type": "integer"},
            ],
            "rows": [
                {"类别": "A", "数量": 30},
                {"类别": "B", "数量": 70},
            ],
            "x_field": "类别",
            "y_fields": ["数量"],
            "title": "类别分布",
        }
        response = await app_client.post("/api/v1/chart/render", json=request)

        assert response.status_code == 200
        data = response.json()
        option = data["echarts_option"]
        assert option["series"][0]["type"] == "pie"
        assert "radius" in option["series"][0]

    @pytest.mark.asyncio
    async def test_render_unsupported_type(self, app_client: AsyncClient) -> None:
        """不支持的图表类型应返回 400。"""
        request = {
            "chart_type": "unknown_type",
            "columns": [{"name": "x", "type": "string"}],
            "rows": [{"x": "a"}],
            "x_field": "x",
            "y_fields": [],
            "title": "测试",
        }
        response = await app_client.post("/api/v1/chart/render", json=request)

        assert response.status_code == 400
        assert "不支持" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_render_empty_rows(self, app_client: AsyncClient) -> None:
        """空数据行应返回 400。"""
        request = {
            "chart_type": "bar",
            "columns": [{"name": "x", "type": "string"}],
            "rows": [],
            "x_field": "x",
            "y_fields": [],
            "title": "测试",
        }
        response = await app_client.post("/api/v1/chart/render", json=request)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_render_auto_infer_fields(self, app_client: AsyncClient) -> None:
        """未指定 x_field 和 y_fields 时应自动推断。"""
        request = {
            "chart_type": "bar",
            "columns": [
                {"name": "维度", "type": "string"},
                {"name": "指标", "type": "integer"},
            ],
            "rows": [
                {"维度": "A", "指标": 10},
                {"维度": "B", "指标": 20},
            ],
            "title": "自动推断",
        }
        response = await app_client.post("/api/v1/chart/render", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["echarts_option"]["xAxis"]["data"] == ["A", "B"]

    @pytest.mark.asyncio
    async def test_render_scatter_chart(self, app_client: AsyncClient) -> None:
        """渲染散点图应正常工作。"""
        request = {
            "chart_type": "scatter",
            "columns": [
                {"name": "x_val", "type": "integer"},
                {"name": "y_val", "type": "integer"},
            ],
            "rows": [
                {"x_val": 1, "y_val": 2},
                {"x_val": 3, "y_val": 4},
            ],
            "x_field": "x_val",
            "y_fields": ["y_val"],
            "title": "散点图",
        }
        response = await app_client.post("/api/v1/chart/render", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["echarts_option"]["series"][0]["type"] == "scatter"

    @pytest.mark.asyncio
    async def test_render_missing_chart_type(self, app_client: AsyncClient) -> None:
        """缺少 chart_type 应返回 422。"""
        response = await app_client.post("/api/v1/chart/render", json={
            "columns": [],
            "rows": [],
        })

        assert response.status_code == 422
