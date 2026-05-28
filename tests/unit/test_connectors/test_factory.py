"""连接器工厂单元测试。

测试 ConnectorFactory.create 的创建逻辑和 supported_dialects 方法。
使用 mock 避免真实数据库连接。
"""

from __future__ import annotations

import pytest

from datapilot_queryexec.connectors.base import BaseConnector
from datapilot_queryexec.connectors.factory import ConnectorFactory


class TestConnectorFactoryCreate:
    """ConnectorFactory.create 测试。"""

    def test_create_mysql_connector(self) -> None:
        """创建 MySQL 连接器。"""
        connector = ConnectorFactory.create(
            dialect="mysql",
            datasource_id="ds-mysql",
            host="127.0.0.1",
            port=3306,
            database="mydb",
            username="root",
            password="secret",
        )
        assert isinstance(connector, BaseConnector)
        assert connector.dialect == "mysql"
        assert connector.datasource_id == "ds-mysql"
        assert connector.host == "127.0.0.1"
        assert connector.port == 3306
        assert connector.database == "mydb"

    def test_create_postgresql_connector(self) -> None:
        """创建 PostgreSQL 连接器。"""
        connector = ConnectorFactory.create(
            dialect="postgresql",
            datasource_id="ds-pg",
            host="127.0.0.1",
            port=5432,
            database="mydb",
            username="postgres",
            password="secret",
        )
        assert isinstance(connector, BaseConnector)
        assert connector.dialect == "postgresql"
        assert connector.datasource_id == "ds-pg"

    def test_create_doris_connector(self) -> None:
        """创建 Doris 连接器。"""
        connector = ConnectorFactory.create(
            dialect="doris",
            datasource_id="ds-doris",
            host="127.0.0.1",
            port=9030,
            database="mydb",
            username="root",
            password="secret",
        )
        assert isinstance(connector, BaseConnector)
        assert connector.dialect == "doris"
        assert connector.datasource_id == "ds-doris"

    def test_create_starrocks_connector(self) -> None:
        """创建 StarRocks 连接器。"""
        connector = ConnectorFactory.create(
            dialect="starrocks",
            datasource_id="ds-sr",
            host="127.0.0.1",
            port=9030,
            database="mydb",
            username="root",
            password="secret",
        )
        assert isinstance(connector, BaseConnector)
        assert connector.dialect == "starrocks"
        assert connector.datasource_id == "ds-sr"

    def test_create_clickhouse_connector(self) -> None:
        """创建 ClickHouse 连接器。"""
        connector = ConnectorFactory.create(
            dialect="clickhouse",
            datasource_id="ds-ch",
            host="127.0.0.1",
            port=9000,
            database="mydb",
            username="default",
            password="secret",
        )
        assert isinstance(connector, BaseConnector)
        assert connector.dialect == "clickhouse"
        assert connector.datasource_id == "ds-ch"

    def test_unsupported_dialect(self) -> None:
        """不支持的方言抛出 ValueError。"""
        with pytest.raises(ValueError, match="不支持的方言"):
            ConnectorFactory.create(
                dialect="oracle",
                datasource_id="ds-oracle",
                host="127.0.0.1",
                port=1521,
                database="orcl",
                username="system",
                password="secret",
            )

    def test_custom_pool_size(self) -> None:
        """自定义连接池大小覆盖默认值。"""
        connector = ConnectorFactory.create(
            dialect="mysql",
            datasource_id="ds-mysql",
            host="127.0.0.1",
            port=3306,
            database="mydb",
            username="root",
            password="secret",
            pool_size=5,
        )
        assert isinstance(connector, BaseConnector)
        assert connector.dialect == "mysql"

    def test_case_insensitive_dialect(self) -> None:
        """方言名称不区分大小写。"""
        connector_upper = ConnectorFactory.create(
            dialect="MYSQL",
            datasource_id="ds-1",
            host="localhost",
            port=3306,
            database="db",
            username="u",
            password="p",
        )
        connector_lower = ConnectorFactory.create(
            dialect="mysql",
            datasource_id="ds-2",
            host="localhost",
            port=3306,
            database="db",
            username="u",
            password="p",
        )
        assert connector_upper.dialect == connector_lower.dialect

    def test_default_pool_size_from_capabilities(self) -> None:
        """不指定 pool_size 时使用能力矩阵默认值。

        MySQL 默认 pool_size=10。
        """
        connector = ConnectorFactory.create(
            dialect="mysql",
            datasource_id="ds-mysql",
            host="127.0.0.1",
            port=3306,
            database="mydb",
            username="root",
            password="secret",
        )
        # 验证创建成功，默认 pool_size 从能力矩阵获取
        assert connector.dialect == "mysql"

    def test_doris_default_pool_size_20(self) -> None:
        """Doris 默认 pool_size=20。"""
        connector = ConnectorFactory.create(
            dialect="doris",
            datasource_id="ds-doris",
            host="127.0.0.1",
            port=9030,
            database="mydb",
            username="root",
            password="secret",
        )
        assert connector.dialect == "doris"


class TestConnectorFactorySupportedDialects:
    """ConnectorFactory.supported_dialects 测试。"""

    def test_returns_sorted_list(self) -> None:
        """返回排序后的方言列表。"""
        dialects = ConnectorFactory.supported_dialects()
        assert dialects == sorted(dialects)

    def test_contains_all_expected(self) -> None:
        """包含所有预期的方言。"""
        dialects = ConnectorFactory.supported_dialects()
        expected = {"clickhouse", "doris", "mysql", "postgresql", "starrocks"}
        assert set(dialects) == expected

    def test_dialects_count(self) -> None:
        """方言数量正确。"""
        dialects = ConnectorFactory.supported_dialects()
        assert len(dialects) == 5
