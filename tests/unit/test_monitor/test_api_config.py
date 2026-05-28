"""datapilot_queryexec.api.routes.config 单元测试。

覆盖数据源配置管理的 CRUD 接口。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from datapilot_queryexec.api.routes.config import _configs, router

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_configs() -> None:
    """每个测试前清空配置存储。"""
    _configs.clear()
    yield
    _configs.clear()


@pytest.fixture()
def client() -> TestClient:
    """创建测试客户端。"""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture()
def sample_config() -> dict:
    """创建样本配置数据。"""
    return {
        "name": "测试Postgres",
        "dialect": "postgres",
        "host": "localhost",
        "port": 5432,
        "database": "testdb",
        "username": "admin",
        "password": "secret123",
        "pool_size": 10,
    }


# ---------------------------------------------------------------------------
# 创建配置测试
# ---------------------------------------------------------------------------


class TestCreateConfig:
    """POST /api/v1/datasources/config 测试。"""

    def test_create_success(self, client: TestClient, sample_config: dict) -> None:
        """成功创建数据源配置。"""
        response = client.post("/api/v1/datasources/config", json=sample_config)

        assert response.status_code == 200
        data = response.json()
        assert "datasource_id" in data
        assert data["name"] == "测试Postgres"
        assert data["dialect"] == "postgres"
        # 密码应被遮蔽
        assert data["password"] == "******"

    def test_create_without_pool_size(self, client: TestClient, sample_config: dict) -> None:
        """不指定 pool_size 创建配置。"""
        config = dict(sample_config)
        del config["pool_size"]

        response = client.post("/api/v1/datasources/config", json=config)

        assert response.status_code == 200
        data = response.json()
        assert data["pool_size"] is None

    def test_create_generates_unique_id(self, client: TestClient, sample_config: dict) -> None:
        """每次创建生成不同的 ID。"""
        resp1 = client.post("/api/v1/datasources/config", json=sample_config)
        resp2 = client.post("/api/v1/datasources/config", json=sample_config)

        id1 = resp1.json()["datasource_id"]
        id2 = resp2.json()["datasource_id"]
        assert id1 != id2

    def test_create_invalid_port(self, client: TestClient, sample_config: dict) -> None:
        """端口超出范围返回校验错误。"""
        config = dict(sample_config)
        config["port"] = 99999

        response = client.post("/api/v1/datasources/config", json=config)

        assert response.status_code == 422

    def test_create_missing_required_field(self, client: TestClient, sample_config: dict) -> None:
        """缺少必填字段返回校验错误。"""
        config = dict(sample_config)
        del config["host"]

        response = client.post("/api/v1/datasources/config", json=config)

        assert response.status_code == 422

    def test_create_zero_port(self, client: TestClient, sample_config: dict) -> None:
        """端口为 0 返回校验错误。"""
        config = dict(sample_config)
        config["port"] = 0

        response = client.post("/api/v1/datasources/config", json=config)

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 列出配置测试
# ---------------------------------------------------------------------------


class TestListConfig:
    """GET /api/v1/datasources/config 测试。"""

    def test_list_empty(self, client: TestClient) -> None:
        """无配置时返回空列表。"""
        response = client.get("/api/v1/datasources/config")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_with_configs(self, client: TestClient, sample_config: dict) -> None:
        """列出多个配置。"""
        client.post("/api/v1/datasources/config", json=sample_config)
        config2 = dict(sample_config)
        config2["name"] = "MySQL数据源"
        config2["dialect"] = "mysql"
        client.post("/api/v1/datasources/config", json=config2)

        response = client.get("/api/v1/datasources/config")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # 确认密码被遮蔽
        for item in data:
            assert item["password"] == "******"


# ---------------------------------------------------------------------------
# 获取单个配置测试
# ---------------------------------------------------------------------------


class TestGetConfig:
    """GET /api/v1/datasources/config/{datasource_id} 测试。"""

    def test_get_success(self, client: TestClient, sample_config: dict) -> None:
        """成功获取单个配置。"""
        create_resp = client.post("/api/v1/datasources/config", json=sample_config)
        datasource_id = create_resp.json()["datasource_id"]

        response = client.get(f"/api/v1/datasources/config/{datasource_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["datasource_id"] == datasource_id
        assert data["name"] == "测试Postgres"
        assert data["password"] == "******"

    def test_get_not_found(self, client: TestClient) -> None:
        """获取不存在的配置返回 404。"""
        response = client.get("/api/v1/datasources/config/non-existent")

        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 删除配置测试
# ---------------------------------------------------------------------------


class TestDeleteConfig:
    """DELETE /api/v1/datasources/config/{datasource_id} 测试。"""

    def test_delete_success(self, client: TestClient, sample_config: dict) -> None:
        """成功删除配置。"""
        create_resp = client.post("/api/v1/datasources/config", json=sample_config)
        datasource_id = create_resp.json()["datasource_id"]

        response = client.delete(f"/api/v1/datasources/config/{datasource_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["datasource_id"] == datasource_id
        assert data["deleted"] is True

        # 确认已删除
        get_resp = client.get(f"/api/v1/datasources/config/{datasource_id}")
        assert get_resp.status_code == 404

    def test_delete_not_found(self, client: TestClient) -> None:
        """删除不存在的配置返回 404。"""
        response = client.delete("/api/v1/datasources/config/non-existent")

        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]

    def test_delete_twice(self, client: TestClient, sample_config: dict) -> None:
        """重复删除第二次返回 404。"""
        create_resp = client.post("/api/v1/datasources/config", json=sample_config)
        datasource_id = create_resp.json()["datasource_id"]

        client.delete(f"/api/v1/datasources/config/{datasource_id}")
        response = client.delete(f"/api/v1/datasources/config/{datasource_id}")

        assert response.status_code == 404
