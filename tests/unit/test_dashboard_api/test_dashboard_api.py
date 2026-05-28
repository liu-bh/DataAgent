"""Dashboard API 和 Chart API 单元测试。"""

from __future__ import annotations

import pytest

from fastapi.testclient import TestClient

from datapilot_agent.api.routes.dashboard import router as dashboard_router
from datapilot_agent.api.routes.chart import router as chart_router
from datapilot_agent.dashboard.store import DashboardStore


class _TestClientMixin:
    """创建 FastAPI TestClient 的混入。"""

    @pytest.fixture()
    def client(self) -> TestClient:
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(dashboard_router)
        app.include_router(chart_router)
        # 重置 store
        from datapilot_agent.api.routes.dashboard import _store
        _store.clear()
        return TestClient(app)


class TestDashboardAPI(_TestClientMixin):
    """Dashboard CRUD API 测试。"""

    def test_create_dashboard(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/dashboard/create",
            json={
                "title": "销售仪表板",
                "description": "展示销售数据",
                "chart_specs": [
                    {"title": "销售额柱状图", "chart_type": "bar"},
                ],
                "columns": 2,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "销售仪表板"
        assert "dashboard_id" in data
        assert len(data["panels"]) == 1

    def test_list_dashboards_empty(self, client: TestClient) -> None:
        response = client.get("/api/v1/dashboard/list")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_list_dashboards(self, client: TestClient) -> None:
        # 创建两个
        client.post("/api/v1/dashboard/create", json={"title": "A"})
        client.post("/api/v1/dashboard/create", json={"title": "B"})
        response = client.get("/api/v1/dashboard/list")
        data = response.json()
        assert data["total"] == 2

    def test_get_dashboard(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/v1/dashboard/create",
            json={"title": "测试仪表板"},
        )
        dashboard_id = create_resp.json()["dashboard_id"]

        response = client.get(f"/api/v1/dashboard/{dashboard_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "测试仪表板"

    def test_get_dashboard_not_found(self, client: TestClient) -> None:
        response = client.get("/api/v1/dashboard/nonexistent-id")
        assert response.status_code == 404

    def test_update_dashboard(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/v1/dashboard/create",
            json={"title": "旧标题", "description": "旧描述"},
        )
        dashboard_id = create_resp.json()["dashboard_id"]

        response = client.put(
            f"/api/v1/dashboard/{dashboard_id}",
            json={"title": "新标题"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "新标题"

    def test_delete_dashboard(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/v1/dashboard/create",
            json={"title": "待删除"},
        )
        dashboard_id = create_resp.json()["dashboard_id"]

        response = client.delete(f"/api/v1/dashboard/{dashboard_id}")
        assert response.status_code == 200
        assert response.json()["success"] is True

        # 确认已删除
        response = client.get(f"/api/v1/dashboard/{dashboard_id}")
        assert response.status_code == 404


class TestChartAPI(_TestClientMixin):
    """Chart API 测试。"""

    def test_recommend_chart(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/chart/recommend",
            json={
                "columns": [
                    {"name": "date", "type": "date"},
                    {"name": "sales", "type": "integer"},
                ],
                "rows": [
                    {"date": "2025-01-01", "sales": 100},
                    {"date": "2025-02-01", "sales": 200},
                    {"date": "2025-03-01", "sales": 150},
                ],
                "user_question": "展示销售趋势",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["recommended_types"]) > 0
        assert data["x_field"] == "date"

    def test_recommend_chart_empty(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/chart/recommend",
            json={"columns": [], "rows": []},
        )
        assert response.status_code == 200

    def test_render_chart_bar(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/chart/render",
            json={
                "chart_type": "bar",
                "columns": [
                    {"name": "city", "type": "varchar"},
                    {"name": "sales", "type": "integer"},
                ],
                "rows": [
                    {"city": "北京", "sales": 100},
                    {"city": "上海", "sales": 200},
                ],
                "x_field": "city",
                "y_fields": ["sales"],
                "title": "销售额柱状图",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["chart_type"] == "bar"
        assert "echarts_option" in data
        assert "series" in data["echarts_option"]

    def test_render_chart_pie(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/chart/render",
            json={
                "chart_type": "pie",
                "columns": [
                    {"name": "category", "type": "varchar"},
                    {"name": "count", "type": "integer"},
                ],
                "rows": [
                    {"category": "A", "count": 30},
                    {"category": "B", "count": 50},
                    {"category": "C", "count": 20},
                ],
                "x_field": "category",
                "y_fields": ["count"],
                "title": "分类占比",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["echarts_option"]["series"][0]["type"] == "pie"

    def test_render_chart_unsupported_type(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/chart/render",
            json={
                "chart_type": "invalid_type",
                "columns": [{"name": "a", "type": "varchar"}],
                "rows": [{"a": "x"}],
            },
        )
        assert response.status_code == 400
