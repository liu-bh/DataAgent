"""服务健康检查 E2E 测试。"""
import httpx
import pytest

SERVICES = [
    ("agent-service", "http://localhost:8000"),
    ("semantic-service", "http://localhost:8001"),
    ("sqlgen-service", "http://localhost:8002"),
    ("queryexec-service", "http://localhost:8003"),
    ("auth-service", "http://localhost:8004"),
    ("guardrail-service", "http://localhost:8005"),
    ("session-service", "http://localhost:8006"),
]


@pytest.mark.e2e
@pytest.mark.parametrize("name,url", SERVICES)
async def test_service_health(name, url):
    """各服务 /health 端点可达。"""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{url}/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("status") == "ok"
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.PoolTimeout, OSError):
        pytest.skip(f"{name} 未启动")
