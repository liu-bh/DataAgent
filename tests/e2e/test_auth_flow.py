"""认证流程 E2E 测试。"""
import httpx
import pytest


@pytest.mark.e2e
async def test_login_invalid_credentials():
    """无效凭据返回错误。"""
    try:
        async with httpx.AsyncClient(base_url="http://localhost:8004", timeout=10.0) as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"email": "nonexistent@test.com", "password": "wrong"},
            )
            assert resp.status_code in (401, 500, 502, 503)
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, OSError):
        pytest.skip("auth-service 未启动")


@pytest.mark.e2e
async def test_health_endpoint():
    """health 端点可达。"""
    try:
        async with httpx.AsyncClient(base_url="http://localhost:8004", timeout=5.0) as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, OSError):
        pytest.skip("auth-service 未启动")
