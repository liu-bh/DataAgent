"""数据源 SQLAlchemy 模型单元测试。"""

import uuid
from unittest.mock import MagicMock

import pytest


class TestDataSourceModel:
    """DataSource 模型测试。"""

    def test_model_import(self) -> None:
        """测试模型可以正常导入。"""
        from datapilot_semantic.metadata.models import DataSource

        assert DataSource.__tablename__ == "data_sources"

    def test_model_columns(self) -> None:
        """验证 DataSource 模型字段定义。"""
        from datapilot_semantic.metadata.models import DataSource

        assert hasattr(DataSource, "id")
        assert hasattr(DataSource, "tenant_id")
        assert hasattr(DataSource, "name")
        assert hasattr(DataSource, "type")
        assert hasattr(DataSource, "host")
        assert hasattr(DataSource, "port")
        assert hasattr(DataSource, "database")
        assert hasattr(DataSource, "username")
        assert hasattr(DataSource, "password")
        assert hasattr(DataSource, "pool_size")
        assert hasattr(DataSource, "freshness_level")
        assert hasattr(DataSource, "freshness_cron")
        assert hasattr(DataSource, "status")
        assert hasattr(DataSource, "last_health_check")
        assert hasattr(DataSource, "deleted_at")
        assert hasattr(DataSource, "created_at")
        assert hasattr(DataSource, "updated_at")
        assert hasattr(DataSource, "health_records")
        assert hasattr(DataSource, "source_tables")

    def test_model_instance(self) -> None:
        """测试模型实例化。"""
        from datapilot_semantic.metadata.models import DataSource

        ds_id = uuid.uuid4()
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

        ds = DataSource(
            id=ds_id,
            tenant_id=tenant_id,
            name="测试数据源",
            type="mysql",
            host="localhost",
            port=3306,
            database="testdb",
            username="root",
            password="encrypted_password_hash",
        )

        assert ds.id == ds_id
        assert ds.tenant_id == tenant_id
        assert ds.name == "测试数据源"
        assert ds.type == "mysql"
        assert ds.host == "localhost"
        assert ds.port == 3306
        assert ds.database == "testdb"
        assert ds.status == "active"  # server_default 应为 active

    def test_soft_delete_field(self) -> None:
        """测试软删除字段默认为 None。"""
        from datapilot_semantic.metadata.models import DataSource

        ds = DataSource(
            name="test",
            type="postgresql",
            host="localhost",
            port=5432,
            database="db",
            username="user",
            password="pwd",
        )
        assert ds.deleted_at is None


class TestDataSourceHealthModel:
    """DataSourceHealth 模型测试。"""

    def test_model_import(self) -> None:
        """测试模型可以正常导入。"""
        from datapilot_semantic.metadata.models import DataSourceHealth

        assert DataSourceHealth.__tablename__ == "datasource_health"

    def test_model_columns(self) -> None:
        """验证 DataSourceHealth 模型字段定义。"""
        from datapilot_semantic.metadata.models import DataSourceHealth

        assert hasattr(DataSourceHealth, "id")
        assert hasattr(DataSourceHealth, "datasource_id")
        assert hasattr(DataSourceHealth, "pool_usage")
        assert hasattr(DataSourceHealth, "avg_latency_ms")
        assert hasattr(DataSourceHealth, "status")
        assert hasattr(DataSourceHealth, "last_heartbeat")
        assert hasattr(DataSourceHealth, "datasource")

    def test_model_instance(self) -> None:
        """测试模型实例化。"""
        from datapilot_semantic.metadata.models import DataSourceHealth

        health = DataSourceHealth(
            datasource_id=uuid.uuid4(),
            status="healthy",
            avg_latency_ms=10,
            pool_usage=25.5,
        )
        assert health.status == "healthy"
        assert health.avg_latency_ms == 10
        assert health.pool_usage == 25.5


class TestSourceTableModel:
    """SourceTable 模型测试。"""

    def test_model_import(self) -> None:
        """测试模型可以正常导入。"""
        from datapilot_semantic.metadata.models import SourceTable

        assert SourceTable.__tablename__ == "source_tables"

    def test_model_columns(self) -> None:
        """验证 SourceTable 模型字段定义。"""
        from datapilot_semantic.metadata.models import SourceTable

        assert hasattr(SourceTable, "id")
        assert hasattr(SourceTable, "tenant_id")
        assert hasattr(SourceTable, "data_source_id")
        assert hasattr(SourceTable, "schema_name")
        assert hasattr(SourceTable, "table_name")
        assert hasattr(SourceTable, "columns")
        assert hasattr(SourceTable, "row_count")
        assert hasattr(SourceTable, "description")
        assert hasattr(SourceTable, "embedding")
        assert hasattr(SourceTable, "last_synced_at")
        assert hasattr(SourceTable, "deleted_at")
        assert hasattr(SourceTable, "datasource")

    def test_embedding_nullable(self) -> None:
        """测试 embedding 字段默认为 None。"""
        from datapilot_semantic.metadata.models import SourceTable

        st = SourceTable(
            data_source_id=uuid.uuid4(),
            table_name="users",
        )
        assert st.embedding is None

    def test_model_instance(self) -> None:
        """测试模型实例化。"""
        from datapilot_semantic.metadata.models import SourceTable

        ds_id = uuid.uuid4()
        st = SourceTable(
            data_source_id=ds_id,
            schema_name="public",
            table_name="orders",
            columns=[{"name": "id", "type": "INTEGER", "is_primary_key": True, "description": None}],
            row_count=10000,
            description="订单表",
        )
        assert st.table_name == "orders"
        assert st.schema_name == "public"
        assert st.columns is not None
        assert len(st.columns) == 1
        assert st.row_count == 10000
