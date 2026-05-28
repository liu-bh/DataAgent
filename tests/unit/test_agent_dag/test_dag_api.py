"""DAG API 路由单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient


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
# 测试: POST /api/v1/dag/execute
# ---------------------------------------------------------------------------


class TestExecuteDAGEndpoint:
    """POST /api/v1/dag/execute 测试。"""

    @pytest.mark.asyncio
    async def test_execute_dag_success(self, app_client: AsyncClient) -> None:
        """正常请求应返回 DAG 执行结果。"""
        response = await app_client.post(
            "/api/v1/dag/execute",
            json={
                "question": "上个月销售额是多少？",
                "dialect": "mysql",
                "tenant_id": "tenant-001",
                "session_id": "session-001",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "dag_id" in data
        assert data["status"] == "completed"
        assert "task_results" in data
        assert "total_time_ms" in data
        assert data["total_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_execute_dag_default_parameters(self, app_client: AsyncClient) -> None:
        """使用默认参数应正常执行。"""
        response = await app_client.post(
            "/api/v1/dag/execute",
            json={"question": "测试查询"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_execute_dag_async_mode(self, app_client: AsyncClient) -> None:
        """异步执行模式应返回 submitted 状态。"""
        response = await app_client.post(
            "/api/v1/dag/execute",
            json={
                "question": "测试异步",
                "async_execution": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "submitted"
        assert data["dag_id"] != ""

    @pytest.mark.asyncio
    async def test_execute_dag_missing_question(self, app_client: AsyncClient) -> None:
        """缺少 question 字段应返回 422。"""
        response = await app_client.post(
            "/api/v1/dag/execute",
            json={"dialect": "mysql"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_execute_dag_empty_question(self, app_client: AsyncClient) -> None:
        """空 question 应返回 422。"""
        response = await app_client.post(
            "/api/v1/dag/execute",
            json={"question": ""},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_execute_dag_task_results_populated(self, app_client: AsyncClient) -> None:
        """同步执行应填充所有节点结果。"""
        response = await app_client.post(
            "/api/v1/dag/execute",
            json={"question": "订单量统计"},
        )

        assert response.status_code == 200
        data = response.json()
        task_results = data["task_results"]

        # 至少应包含第一个节点结果
        assert "intent_route" in task_results
        assert task_results["intent_route"]["status"] == "success"


# ---------------------------------------------------------------------------
# 测试: GET /api/v1/dag/{dag_id}/status
# ---------------------------------------------------------------------------


class TestGetDAGStatusEndpoint:
    """GET /api/v1/dag/{dag_id}/status 测试。"""

    @pytest.mark.asyncio
    async def test_get_status_existing_dag(self, app_client: AsyncClient) -> None:
        """查询已存在的 DAG 状态应返回正确信息。"""
        # 先执行一次创建记录
        exec_response = await app_client.post(
            "/api/v1/dag/execute",
            json={"question": "状态查询测试"},
        )
        dag_id = exec_response.json()["dag_id"]

        # 查询状态
        status_response = await app_client.get(f"/api/v1/dag/{dag_id}/status")

        assert status_response.status_code == 200
        data = status_response.json()
        assert data["dag_id"] == dag_id
        assert data["status"] in ("submitted", "completed")
        assert data["question"] == "状态查询测试"
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_get_status_nonexistent_dag(self, app_client: AsyncClient) -> None:
        """查询不存在的 DAG 应返回 404。"""
        response = await app_client.get("/api/v1/dag/nonexistent-id/status")

        assert response.status_code == 404
        data = response.json()
        assert "不存在" in data.get("detail", "")


# ---------------------------------------------------------------------------
# 测试: GET /api/v1/dag/history
# ---------------------------------------------------------------------------


class TestListDAGHistoryEndpoint:
    """GET /api/v1/dag/history 测试。"""

    @pytest.mark.asyncio
    async def test_history_empty(self, app_client: AsyncClient) -> None:
        """无执行记录时应返回空列表。"""
        response = await app_client.get("/api/v1/dag/history")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_history_returns_records(self, app_client: AsyncClient) -> None:
        """执行 DAG 后历史记录应包含该记录。"""
        # 执行两次
        await app_client.post(
            "/api/v1/dag/execute",
            json={"question": "历史记录测试1"},
        )
        await app_client.post(
            "/api/v1/dag/execute",
            json={"question": "历史记录测试2"},
        )

        response = await app_client.get("/api/v1/dag/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

        # 验证记录结构
        for record in data:
            assert "dag_id" in record
            assert "status" in record
            assert "question" in record

    @pytest.mark.asyncio
    async def test_history_respects_limit(self, app_client: AsyncClient) -> None:
        """历史记录应遵守 limit 参数。"""
        # 执行多次
        for i in range(5):
            await app_client.post(
                "/api/v1/dag/execute",
                json={"question": f"limit测试{i}"},
            )

        response = await app_client.get("/api/v1/dag/history?limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 2
