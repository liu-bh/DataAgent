"""datapilot_queryexec.api.routes.health 单元测试。

覆盖健康检查 API 的列表和手动检查端点。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from datapilot_queryexec.api.routes.health import router, set_monitor
from datapilot_queryexec.monitor.health import DataSourceMonitor

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def monitor() -> DataSourceMonitor:
    """创建监控器实例。"""
    mon = DataSourceMonitor(check_interval_seconds=30)
    mon.register(
        datasource_id="ds-1",
        name="测试Postgres",
        dialect="postgres",
        host="localhost",
        port=5432,
    )
    mon.register(
        datasource_id="ds-2",
        name="测试MySQL",
        dialect="mysql",
        host="10.0.0.1",
        port=3306,
    )
    return mon


@pytest.fixture(autouse=True)
def _setup_monitor(monitor: DataSourceMonitor) -> None:
    """自动注入监控器实例。"""
    set_monitor(monitor)


@pytest.fixture()
def client() -> TestClient:
    """创建测试客户端。"""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# 列表健康状态测试
# ---------------------------------------------------------------------------


class TestListDatasourceHealth:
    """GET /api/v1/datasources/health 测试。"""

    def test_list_all(self, client: TestClient) -> None:
        """获取所有数据源健康状态。"""
        response = client.get("/api/v1/datasources/health")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        ids = {item["datasource_id"] for item in data}
        assert "ds-1" in ids
        assert "ds-2" in ids

    def test_list_empty(self) -> None:
        """无数据源时返回空列表。"""
        empty_monitor = DataSourceMonitor()
        set_monitor(empty_monitor)

        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        test_client = TestClient(app)

        response = test_client.get("/api/v1/datasources/health")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_response_format(self, client: TestClient) -> None:
        """验证响应字段格式。"""
        response = client.get("/api/v1/datasources/health")
        data = response.json()

        item = data[0]
        assert "datasource_id" in item
        assert "name" in item
        assert "dialect" in item
        assert "healthy" in item
        assert "circuit_state" in item
        assert "total_queries" in item


# ---------------------------------------------------------------------------
# 手动检查测试
# ---------------------------------------------------------------------------


class TestCheckDatasource:
    """POST /api/v1/datasources/{datasource_id}/check 测试。"""

    def test_check_success(self, client: TestClient) -> None:
        """手动检查成功。"""
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_writer.close = AsyncMock()

        with patch(
            "datapilot_queryexec.monitor.health.asyncio.open_connection",
            new_callable=AsyncMock,
            return_value=(mock_reader, mock_writer),
        ):
            response = client.post("/api/v1/datasources/ds-1/check")

        assert response.status_code == 200
        data = response.json()
        assert data["datasource_id"] == "ds-1"
        assert data["healthy"] is True
        assert data["last_check_at"] is not None

    def test_check_not_found(self, client: TestClient) -> None:
        """检查未注册的数据源返回 404。"""
        response = client.post("/api/v1/datasources/non-existent/check")

        assert response.status_code == 404
        assert "未注册" in response.json()["detail"]

    def test_check_failure(self, client: TestClient) -> None:
        """手动检查失败，返回不健康状态。"""
        with patch(
            "datapilot_queryexec.monitor.health.asyncio.open_connection",
            new_callable=AsyncMock,
            side_effect=ConnectionRefusedError("连接被拒绝"),
        ):
            response = client.post("/api/v1/datasources/ds-1/check")

        assert response.status_code == 200
        data = response.json()
        assert data["healthy"] is False
        assert data["consecutive_failures"] == 1
