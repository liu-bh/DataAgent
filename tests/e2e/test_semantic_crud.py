"""语义模型 CRUD E2E 测试。"""
import httpx
import pytest

SEMANTIC_URL = "http://localhost:8001"


@pytest.fixture
async def semantic_client():
    async with httpx.AsyncClient(base_url=SEMANTIC_URL, timeout=10.0) as client:
        try:
            resp = await client.get("/health")
            if resp.status_code != 200:
                pytest.skip("semantic-service 未启动")
        except (httpx.ConnectError, httpx.ConnectTimeout):
            pytest.skip("semantic-service 未启动")
        yield client


@pytest.mark.e2e
async def test_list_semantic_models(semantic_client):
    """获取语义模型列表。"""
    resp = await semantic_client.get("/api/v1/semantic-models")
    assert resp.status_code == 200


@pytest.mark.e2e
async def test_list_data_sources(semantic_client):
    """获取数据源列表。"""
    resp = await semantic_client.get("/api/v1/data-sources")
    assert resp.status_code == 200


@pytest.mark.e2e
async def test_search(semantic_client):
    """搜索接口。"""
    resp = await semantic_client.get("/api/v1/search", params={"q": "test"})
    assert resp.status_code == 200
