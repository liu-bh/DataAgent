"""Schema Extractor 单元测试。"""

from unittest.mock import MagicMock, patch

import pytest


class TestGetSchemaQuery:
    """_get_schema_query 辅助函数测试。"""

    def test_mysql_query(self) -> None:
        """测试 MySQL 方言的查询 SQL。"""
        from datapilot_semantic.metadata.schema_extractor import _get_schema_query

        sql = _get_schema_query("mysql")
        assert "information_schema.COLUMNS" in sql
        assert "information_schema.TABLES" in sql
        assert ":schema_name" in sql

    def test_postgresql_query(self) -> None:
        """测试 PostgreSQL 方言的查询 SQL。"""
        from datapilot_semantic.metadata.schema_extractor import _get_schema_query

        sql = _get_schema_query("postgresql")
        assert "information_schema.columns" in sql
        assert "PRIMARY KEY" in sql

    def test_doris_query(self) -> None:
        """测试 Doris 方言（复用 MySQL 查询）。"""
        from datapilot_semantic.metadata.schema_extractor import _get_schema_query

        sql = _get_schema_query("doris")
        assert "information_schema.COLUMNS" in sql

    def test_starrocks_query(self) -> None:
        """测试 StarRocks 方言（复用 MySQL 查询）。"""
        from datapilot_semantic.metadata.schema_extractor import _get_schema_query

        sql = _get_schema_query("starrocks")
        assert "information_schema.COLUMNS" in sql

    def test_clickhouse_query(self) -> None:
        """测试 ClickHouse 方言的查询 SQL。"""
        from datapilot_semantic.metadata.schema_extractor import _get_schema_query

        sql = _get_schema_query("clickhouse")
        assert "system.columns" in sql
        assert ":schema_name" in sql

    def test_unsupported_dialect(self) -> None:
        """测试不支持的方言抛出 ValueError。"""
        from datapilot_semantic.metadata.schema_extractor import _get_schema_query

        with pytest.raises(ValueError, match="不支持"):
            _get_schema_query("oracle")


class TestExtractSchema:
    """extract_schema 函数测试（mock 连接）。"""

    @patch("datapilot_semantic.metadata.schema_extractor.create_engine")
    def test_extract_mysql_schema(self, mock_create_engine: MagicMock) -> None:
        """测试 MySQL schema 提取。"""
        from datapilot_semantic.metadata.schema_extractor import extract_schema
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        # Mock 数据库返回
        mock_row = MagicMock()
        mock_row.table_name = "users"
        mock_row.schema_name = "testdb"
        mock_row.column_name = "id"
        mock_row.column_type = "BIGINT"
        mock_row.column_key = "PRI"
        mock_row.column_comment = "主键"
        mock_row.table_comment = "用户表"
        mock_row.table_rows = 1000

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_engine.dispose = MagicMock()
        mock_create_engine.return_value = mock_engine

        config = DataConnectionConfig(
            type="mysql",
            host="localhost",
            port=3306,
            database="testdb",
            username="root",
            password="pwd",
        )

        tables = extract_schema(config)

        assert len(tables) == 1
        assert tables[0].table_name == "users"
        assert tables[0].schema_name == "testdb"
        assert len(tables[0].columns) == 1
        assert tables[0].columns[0].name == "id"
        assert tables[0].columns[0].is_primary_key is True
        assert tables[0].columns[0].description == "主键"

    @patch("datapilot_semantic.metadata.schema_extractor.create_engine")
    def test_extract_multiple_tables(self, mock_create_engine: MagicMock) -> None:
        """测试提取多张表。"""
        from datapilot_semantic.metadata.schema_extractor import extract_schema
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        # 模拟两张表、多个列
        rows = []
        for table_idx, (table_name, table_comment) in enumerate(
            [("users", "用户表"), ("orders", "订单表")]
        ):
            for col_idx, (col_name, col_type, col_key, col_comment) in enumerate(
                [
                    ("id", "BIGINT", "PRI", "主键"),
                    ("name", "VARCHAR(100)", "", "名称"),
                    ("created_at", "DATETIME", "", "创建时间"),
                ]
            ):
                row = MagicMock()
                row.table_name = table_name
                row.schema_name = "testdb"
                row.column_name = col_name
                row.column_type = col_type
                row.column_key = col_key
                row.column_comment = col_comment
                row.table_comment = table_comment
                row.table_rows = 100 * (table_idx + 1)
                rows.append(row)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_engine.dispose = MagicMock()
        mock_create_engine.return_value = mock_engine

        config = DataConnectionConfig(
            type="mysql",
            host="localhost",
            port=3306,
            database="testdb",
            username="root",
            password="pwd",
        )

        tables = extract_schema(config)

        assert len(tables) == 2
        assert tables[0].table_name == "users"
        assert tables[0].description == "用户表"
        assert len(tables[0].columns) == 3
        assert tables[1].table_name == "orders"
        assert len(tables[1].columns) == 3

    @patch("datapilot_semantic.metadata.schema_extractor.create_engine")
    def test_extract_empty_schema(self, mock_create_engine: MagicMock) -> None:
        """测试空 Schema 提取。"""
        from datapilot_semantic.metadata.schema_extractor import extract_schema
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_engine.dispose = MagicMock()
        mock_create_engine.return_value = mock_engine

        config = DataConnectionConfig(
            type="postgresql",
            host="localhost",
            port=5432,
            database="emptydb",
            username="user",
            password="pwd",
        )

        tables = extract_schema(config)
        assert len(tables) == 0

    @patch("datapilot_semantic.metadata.schema_extractor.create_engine")
    def test_extract_with_explicit_schema_name(
        self, mock_create_engine: MagicMock
    ) -> None:
        """测试显式指定 schema_name。"""
        from datapilot_semantic.metadata.schema_extractor import extract_schema
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_engine.dispose = MagicMock()
        mock_create_engine.return_value = mock_engine

        config = DataConnectionConfig(
            type="postgresql",
            host="localhost",
            port=5432,
            database="mydb",
            username="user",
            password="pwd",
        )

        tables = extract_schema(config, schema_name="analytics")
        # 验证传入了正确的 schema_name 参数
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert call_args[0][1] == {"schema_name": "analytics"}

    @patch("datapilot_semantic.metadata.schema_extractor.create_engine")
    def test_extract_connection_error(self, mock_create_engine: MagicMock) -> None:
        """测试连接失败时抛出 RuntimeError。"""
        from datapilot_semantic.metadata.schema_extractor import extract_schema
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("连接被拒绝")
        mock_engine.dispose = MagicMock()
        mock_create_engine.return_value = mock_engine

        config = DataConnectionConfig(
            type="mysql",
            host="bad-host",
            port=3306,
            database="db",
            username="user",
            password="pwd",
        )

        with pytest.raises(RuntimeError, match="提取 Schema 失败"):
            extract_schema(config)

    @patch("datapilot_semantic.metadata.schema_extractor.create_engine")
    def test_default_schema_name_mysql(
        self, mock_create_engine: MagicMock
    ) -> None:
        """测试 MySQL 默认 schema_name 为 database 名。"""
        from datapilot_semantic.metadata.schema_extractor import extract_schema
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_engine.dispose = MagicMock()
        mock_create_engine.return_value = mock_engine

        config = DataConnectionConfig(
            type="mysql",
            host="localhost",
            port=3306,
            database="my_database",
            username="root",
            password="pwd",
        )

        extract_schema(config)
        call_args = mock_conn.execute.call_args
        assert call_args[0][1] == {"schema_name": "my_database"}

    @patch("datapilot_semantic.metadata.schema_extractor.create_engine")
    def test_default_schema_name_postgresql(
        self, mock_create_engine: MagicMock
    ) -> None:
        """测试 PostgreSQL 默认 schema_name 为 public。"""
        from datapilot_semantic.metadata.schema_extractor import extract_schema
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_engine.dispose = MagicMock()
        mock_create_engine.return_value = mock_engine

        config = DataConnectionConfig(
            type="postgresql",
            host="localhost",
            port=5432,
            database="mydb",
            username="user",
            password="pwd",
        )

        extract_schema(config)
        call_args = mock_conn.execute.call_args
        assert call_args[0][1] == {"schema_name": "public"}
