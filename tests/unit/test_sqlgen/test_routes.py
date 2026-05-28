"""NL2SQL API 路由单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# 确保项目源码路径可被导入
project_root = Path(__file__).resolve().parent.parent.parent.parent / "services" / "sql-generator-service" / "src"
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

libs_root = Path(__file__).resolve().parent.parent.parent.parent / "libs"
for lib_dir in libs_root.iterdir():
    if lib_dir.is_dir():
        lib_src = lib_dir / "src"
        if lib_src.exists() and str(lib_src) not in sys.path:
            sys.path.insert(0, str(lib_src))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_pipeline() -> MagicMock:
    """创建 mock NL2SQLPipeline。"""
    pipeline = MagicMock()
    pipeline.generate = AsyncMock(return_value=MagicMock(
        sql="SELECT COUNT(*) AS cnt FROM orders",
        sql_dialect="mysql",
        explanation="统计订单数量",
        confidence=0.9,
        used_few_shots=["示例问题1"],
        latency_ms=150,
        intent="sql_query",
        text_response="",
        warnings=["SQL 未包含 LIMIT，已自动添加 LIMIT 1000"],
    ))
    return pipeline


@pytest.fixture
def app_client(mock_pipeline: MagicMock) -> AsyncClient:
    """创建测试用 FastAPI 客户端。"""
    from datapilot_sqlgen import app
    from datapilot_sqlgen.api.routes.sqlgen import set_pipeline

    set_pipeline(mock_pipeline)

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    return client


# ---------------------------------------------------------------------------
# Chat Message 路由测试
# ---------------------------------------------------------------------------


class TestChatMessageEndpoint:
    """POST /api/v1/chat/message 测试。"""

    @pytest.mark.asyncio
    async def test_sql_query_response(
        self,
        app_client: AsyncClient,
        mock_pipeline: MagicMock,
    ) -> None:
        """SQL 查询意图应返回 SQL 结果。"""
        response = await app_client.post(
            "/api/v1/chat/message",
            json={
                "session_id": "test-session-001",
                "content": "上个月销售额是多少？",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "sql_query"
        assert data["sql"] != ""
        assert data["confidence"] > 0
        assert data["trace_id"] != ""
        assert "session_id" in data

    @pytest.mark.asyncio
    async def test_chitchat_response(
        self,
        app_client: AsyncClient,
        mock_pipeline: MagicMock,
    ) -> None:
        """闲聊意图应返回文本回复。"""
        mock_pipeline.generate = AsyncMock(return_value=MagicMock(
            sql="",
            sql_dialect="",
            explanation="",
            confidence=0.9,
            used_few_shots=[],
            latency_ms=50,
            intent="chitchat",
            text_response="你好！我是 DataPilot 数据助手。",
            warnings=[],
        ))

        response = await app_client.post(
            "/api/v1/chat/message",
            json={
                "session_id": "test-session-001",
                "content": "你好",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "chitchat"
        assert data["sql"] == ""
        assert data["content"] != ""

    @pytest.mark.asyncio
    async def test_missing_session_id(self, app_client: AsyncClient) -> None:
        """缺少 session_id 应返回 422。"""
        response = await app_client.post(
            "/api/v1/chat/message",
            json={
                "content": "上个月销售额是多少？",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_content(self, app_client: AsyncClient) -> None:
        """缺少 content 应返回 422。"""
        response = await app_client.post(
            "/api/v1/chat/message",
            json={
                "session_id": "test-session-001",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_content(self, app_client: AsyncClient) -> None:
        """空 content 应返回 422。"""
        response = await app_client.post(
            "/api/v1/chat/message",
            json={
                "session_id": "test-session-001",
                "content": "",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_pipeline_error_handling(
        self,
        app_client: AsyncClient,
        mock_pipeline: MagicMock,
    ) -> None:
        """Pipeline 抛出异常时应返回友好错误信息。"""
        mock_pipeline.generate = AsyncMock(side_effect=RuntimeError("LLM 超时"))

        response = await app_client.post(
            "/api/v1/chat/message",
            json={
                "session_id": "test-session-001",
                "content": "上个月销售额",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "错误" in data["content"] or "稍后" in data["content"]

    @pytest.mark.asyncio
    async def test_pipeline_not_initialized(
        self,
    ) -> None:
        """Pipeline 未初始化时应返回服务不可用提示。"""
        from datapilot_sqlgen import app
        from datapilot_sqlgen.api.routes.sqlgen import set_pipeline

        set_pipeline(None)

        transport = ASGITransport(app=app)
        client = AsyncClient(transport=transport, base_url="http://test")

        response = await client.post(
            "/api/v1/chat/message",
            json={
                "session_id": "test-session-001",
                "content": "测试",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "不可用" in data["content"]


# ---------------------------------------------------------------------------
# Stream Chat Stub 测试
# ---------------------------------------------------------------------------


class TestStreamChatEndpoint:
    """POST /api/v1/chat/stream 测试。"""

    @pytest.mark.asyncio
    async def test_stream_stub_response(
        self,
        app_client: AsyncClient,
    ) -> None:
        """流式接口应返回 stub 提示。"""
        response = await app_client.post(
            "/api/v1/chat/stream",
            json={
                "session_id": "test-session-001",
                "content": "上个月销售额",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "Sprint 5" in data.get("message", "")
        assert data.get("trace_id", "") != ""


# ---------------------------------------------------------------------------
# Execute SQL Stub 测试
# ---------------------------------------------------------------------------


class TestExecuteSQLEndpoint:
    """POST /api/v1/chat/execute-sql 测试。"""

    @pytest.mark.asyncio
    async def test_execute_sql_stub(
        self,
        app_client: AsyncClient,
    ) -> None:
        """执行 SQL 接口应返回 stub 提示。"""
        response = await app_client.post(
            "/api/v1/chat/execute-sql",
            json={
                "session_id": "test-session-001",
                "original_sql": "SELECT COUNT(*) FROM orders",
                "edited_sql": "SELECT COUNT(*) FROM orders WHERE status = 'paid'",
                "datasource_id": "ds-001",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Sprint 4" in data.get("message", "")

    @pytest.mark.asyncio
    async def test_execute_sql_missing_fields(self, app_client: AsyncClient) -> None:
        """缺少必填字段应返回 422。"""
        response = await app_client.post(
            "/api/v1/chat/execute-sql",
            json={
                "session_id": "test-session-001",
            },
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Health Endpoint 测试
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """GET /health 测试。"""

    @pytest.mark.asyncio
    async def test_health_check(self, app_client: AsyncClient) -> None:
        """健康检查应返回 ok。"""
        response = await app_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "sqlgen"
