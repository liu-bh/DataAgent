"""E2E 测试配置。"""
import httpx
import pytest

# 各服务地址
AGENT_URL = "http://localhost:8000"
SEMANTIC_URL = "http://localhost:8001"
SQLGEN_URL = "http://localhost:8002"
QUERYEXEC_URL = "http://localhost:8003"
AUTH_URL = "http://localhost:8004"
GUARDRAIL_URL = "http://localhost:8005"
SESSION_URL = "http://localhost:8006"


@pytest.fixture
async def agent_client():
    async with httpx.AsyncClient(base_url=AGENT_URL, timeout=10.0) as client:
        yield client


@pytest.fixture
async def auth_client():
    async with httpx.AsyncClient(base_url=AUTH_URL, timeout=10.0) as client:
        yield client


@pytest.fixture
async def semantic_client():
    async with httpx.AsyncClient(base_url=SEMANTIC_URL, timeout=10.0) as client:
        yield client


@pytest.fixture
async def test_token(auth_client):
    """获取测试用 token（无数据库时返回 None）。"""
    try:
        resp = await auth_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "admin123"},
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
    except Exception:
        pass
    return "test-token"  # 无数据库时使用 mock token
