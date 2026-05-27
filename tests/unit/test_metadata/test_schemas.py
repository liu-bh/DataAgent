"""数据源 Pydantic Schema 单元测试。"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError


class TestDataConnectionConfig:
    """DataConnectionConfig Schema 测试。"""

    def test_valid_config(self) -> None:
        """测试有效配置。"""
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        config = DataConnectionConfig(
            type="mysql",
            host="localhost",
            port=3306,
            database="testdb",
            username="root",
            password="secret",
        )
        assert config.type == "mysql"
        assert config.host == "localhost"
        assert config.port == 3306
        assert config.database == "testdb"
        assert config.username == "root"
        assert config.password == "secret"

    def test_postgresql_config(self) -> None:
        """测试 PostgreSQL 配置。"""
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        config = DataConnectionConfig(
            type="postgresql",
            host="10.0.0.1",
            port=5432,
            database="analytics",
            username="admin",
            password="pwd123",
        )
        assert config.type == "postgresql"

    def test_missing_required_fields(self) -> None:
        """测试缺少必填字段时抛出 ValidationError。"""
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        with pytest.raises(ValidationError):
            DataConnectionConfig(
                type="mysql",
                host="localhost",
                # 缺少 port, database, username, password
            )

    def test_port_validation(self) -> None:
        """测试端口范围校验。"""
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        with pytest.raises(ValidationError):
            DataConnectionConfig(
                type="mysql",
                host="localhost",
                port=0,  # 无效端口
                database="db",
                username="user",
                password="pwd",
            )

        with pytest.raises(ValidationError):
            DataConnectionConfig(
                type="mysql",
                host="localhost",
                port=70000,  # 超出范围
                database="db",
                username="user",
                password="pwd",
            )


class TestDataSourceCreate:
    """DataSourceCreate Schema 测试。"""

    def test_valid_create(self) -> None:
        """测试有效创建请求。"""
        from datapilot_semantic.metadata.schemas import DataSourceCreate

        req = DataSourceCreate(
            name="测试MySQL",
            type="mysql",
            host="localhost",
            port=3306,
            database="testdb",
            username="root",
            password="secret123",
        )
        assert req.name == "测试MySQL"
        assert req.type == "mysql"
        assert req.pool_size == 5  # 默认值

    def test_invalid_type(self) -> None:
        """测试无效数据源类型。"""
        from datapilot_semantic.metadata.schemas import DataSourceCreate

        with pytest.raises(ValidationError):
            DataSourceCreate(
                name="test",
                type="oracle",  # 不支持的类型
                host="localhost",
                port=1521,
                database="db",
                username="user",
                password="pwd",
            )

    def test_custom_freshness(self) -> None:
        """测试自定义数据新鲜度。"""
        from datapilot_semantic.metadata.schemas import DataSourceCreate

        req = DataSourceCreate(
            name="test",
            type="postgresql",
            host="localhost",
            port=5432,
            database="db",
            username="user",
            password="pwd",
            freshness_level="custom",
            freshness_cron="0 */6 * * *",
        )
        assert req.freshness_level == "custom"
        assert req.freshness_cron == "0 */6 * * *"

    def test_optional_fields(self) -> None:
        """测试可选字段默认值。"""
        from datapilot_semantic.metadata.schemas import DataSourceCreate

        req = DataSourceCreate(
            name="test",
            type="clickhouse",
            host="localhost",
            port=8123,
            database="db",
            username="user",
            password="pwd",
        )
        assert req.freshness_level is None
        assert req.freshness_cron is None


class TestDataSourceUpdate:
    """DataSourceUpdate Schema 测试。"""

    def test_partial_update(self) -> None:
        """测试部分更新。"""
        from datapilot_semantic.metadata.schemas import DataSourceUpdate

        req = DataSourceUpdate(name="新名称")
        data = req.model_dump(exclude_unset=True)
        assert data == {"name": "新名称"}

    def test_empty_update(self) -> None:
        """测试空更新。"""
        from datapilot_semantic.metadata.schemas import DataSourceUpdate

        req = DataSourceUpdate()
        data = req.model_dump(exclude_unset=True)
        assert data == {}

    def test_status_validation(self) -> None:
        """测试状态字段校验。"""
        from datapilot_semantic.metadata.schemas import DataSourceUpdate

        with pytest.raises(ValidationError):
            DataSourceUpdate(status="unknown")

        req = DataSourceUpdate(status="disabled")
        assert req.status == "disabled"


class TestDataSourceResponse:
    """DataSourceResponse Schema 测试。"""

    def test_from_orm(self) -> None:
        """测试从 ORM 对象序列化。"""
        from datapilot_semantic.metadata.schemas import DataSourceResponse

        now = datetime.now(timezone.utc)
        mock_ds = MagicMock()
        mock_ds.id = uuid.uuid4()
        mock_ds.tenant_id = uuid.uuid4()
        mock_ds.name = "测试数据源"
        mock_ds.type = "mysql"
        mock_ds.host = "localhost"
        mock_ds.port = 3306
        mock_ds.database = "testdb"
        mock_ds.username = "root"
        mock_ds.pool_size = 5
        mock_ds.freshness_level = "daily"
        mock_ds.freshness_cron = None
        mock_ds.status = "active"
        mock_ds.last_health_check = now
        mock_ds.created_at = now
        mock_ds.updated_at = now

        resp = DataSourceResponse.model_validate(mock_ds, from_attributes=True)
        assert resp.name == "测试数据源"
        assert resp.type == "mysql"
        assert resp.status == "active"
        # 确认不包含密码字段
        assert not hasattr(resp, "password") or resp.model_dump().get("password") is None

    def test_no_password_field(self) -> None:
        """测试响应中不包含密码字段。"""
        from datapilot_semantic.metadata.schemas import DataSourceResponse

        schema_fields = DataSourceResponse.model_fields
        assert "password" not in schema_fields


class TestColumnSchema:
    """ColumnSchema 测试。"""

    def test_valid_column(self) -> None:
        """测试有效列定义。"""
        from datapilot_semantic.metadata.schemas import ColumnSchema

        col = ColumnSchema(
            name="id",
            type="INTEGER",
            is_primary_key=True,
            description="主键",
        )
        assert col.name == "id"
        assert col.is_primary_key is True

    def test_default_values(self) -> None:
        """测试默认值。"""
        from datapilot_semantic.metadata.schemas import ColumnSchema

        col = ColumnSchema(name="name", type="VARCHAR(100)")
        assert col.is_primary_key is False
        assert col.description is None


class TestTableSchema:
    """TableSchema 测试。"""

    def test_valid_table(self) -> None:
        """测试有效表结构。"""
        from datapilot_semantic.metadata.schemas import ColumnSchema, TableSchema

        table = TableSchema(
            table_name="users",
            schema_name="public",
            columns=[
                ColumnSchema(name="id", type="UUID", is_primary_key=True),
                ColumnSchema(name="name", type="VARCHAR(100)"),
            ],
            description="用户表",
            row_count=5000,
        )
        assert table.table_name == "users"
        assert len(table.columns) == 2
        assert table.row_count == 5000


class TestSourceTableResponse:
    """SourceTableResponse 测试。"""

    def test_from_orm(self) -> None:
        """测试从 ORM 对象序列化。"""
        from datapilot_semantic.metadata.schemas import SourceTableResponse

        now = datetime.now(timezone.utc)
        mock_table = MagicMock()
        mock_table.id = uuid.uuid4()
        mock_table.tenant_id = uuid.uuid4()
        mock_table.data_source_id = uuid.uuid4()
        mock_table.schema_name = "public"
        mock_table.table_name = "orders"
        mock_table.columns = [{"name": "id", "type": "BIGINT", "is_primary_key": True}]
        mock_table.row_count = 10000
        mock_table.description = "订单表"
        mock_table.last_synced_at = now
        mock_table.created_at = now
        mock_table.updated_at = now

        resp = SourceTableResponse.model_validate(mock_table, from_attributes=True)
        assert resp.table_name == "orders"
        assert resp.row_count == 10000


class TestSyncResultResponse:
    """SyncResultResponse 测试。"""

    def test_success_result(self) -> None:
        """测试成功同步结果。"""
        from datapilot_semantic.metadata.schemas import SyncResultResponse

        result = SyncResultResponse(
            datasource_id=uuid.uuid4(),
            status="success",
            total_tables=10,
            synced_tables=10,
            updated_tables=3,
            new_tables=7,
            message="同步完成",
        )
        assert result.status == "success"
        assert result.synced_tables == 10

    def test_partial_result(self) -> None:
        """测试部分同步结果。"""
        from datapilot_semantic.metadata.schemas import SyncResultResponse

        result = SyncResultResponse(
            datasource_id=uuid.uuid4(),
            status="partial",
            total_tables=10,
            synced_tables=8,
            updated_tables=5,
            new_tables=3,
            failed_tables=2,
        )
        assert result.status == "partial"
        assert result.failed_tables == 2

    def test_failed_result(self) -> None:
        """测试失败同步结果。"""
        from datapilot_semantic.metadata.schemas import SyncResultResponse

        result = SyncResultResponse(
            datasource_id=uuid.uuid4(),
            status="failed",
            total_tables=0,
            synced_tables=0,
            updated_tables=0,
            new_tables=0,
            message="连接超时",
        )
        assert result.status == "failed"


class TestDataSourceHealthResponse:
    """DataSourceHealthResponse 测试。"""

    def test_from_orm(self) -> None:
        """测试从 ORM 对象序列化。"""
        from datapilot_semantic.metadata.schemas import DataSourceHealthResponse

        now = datetime.now(timezone.utc)
        mock_health = MagicMock()
        mock_health.datasource_id = uuid.uuid4()
        mock_health.pool_usage = 45.5
        mock_health.avg_latency_ms = 12
        mock_health.status = "healthy"
        mock_health.last_heartbeat = now
        mock_health.created_at = now

        resp = DataSourceHealthResponse.model_validate(mock_health, from_attributes=True)
        assert resp.status == "healthy"
        assert resp.avg_latency_ms == 12
        assert resp.pool_usage == 45.5
