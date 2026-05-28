"""连接器工厂。

根据方言类型创建对应的数据源连接器实例，使用能力矩阵中的默认参数。

用法::

    from datapilot_queryexec.connectors.factory import ConnectorFactory

    connector = ConnectorFactory.create(
        dialect="mysql",
        datasource_id="ds-001",
        host="127.0.0.1",
        port=3306,
        database="mydb",
        username="root",
        password="secret",
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from datapilot_queryexec.connectors.capabilities import get_capabilities

if TYPE_CHECKING:
    from datapilot_queryexec.connectors.base import BaseConnector

logger = structlog.get_logger(__name__)


class ConnectorFactory:
    """数据源连接器工厂。

    根据方言名称创建对应的连接器实例。
    如果未指定 pool_size，则使用能力矩阵中的默认值。
    """

    @staticmethod
    def create(
        dialect: str,
        datasource_id: str,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        pool_size: int | None = None,
    ) -> BaseConnector:
        """根据方言创建连接器实例。

        Args:
            dialect: 数据源方言，如 "mysql"、"postgresql"、"doris"、
                     "starrocks"、"clickhouse"。
            datasource_id: 数据源唯一标识。
            host: 数据库主机地址。
            port: 数据库端口。
            database: 数据库名称。
            username: 用户名。
            password: 密码。
            pool_size: 连接池大小。为 None 时使用方言默认值。

        Returns:
            对应方言的连接器实例。

        Raises:
            ValueError: 不支持的方言。
        """
        dialect_lower = dialect.lower()

        # 获取方言默认参数
        try:
            caps = get_capabilities(dialect_lower)
        except ValueError:
            logger.error(
                "创建连接器失败：不支持的方言",
                dialect=dialect,
                datasource_id=datasource_id,
            )
            raise

        # 如果未指定 pool_size，使用能力矩阵中的默认值
        effective_pool_size = pool_size if pool_size is not None else caps.pool_size

        # 延迟导入具体连接器，避免循环依赖
        if dialect_lower == "mysql":
            from datapilot_queryexec.connectors.mysql import MySQLConnector

            connector: BaseConnector = MySQLConnector(
                datasource_id=datasource_id,
                host=host,
                port=port,
                database=database,
                username=username,
                password=password,
                pool_size=effective_pool_size,
            )
        elif dialect_lower == "postgresql":
            from datapilot_queryexec.connectors.postgresql import PostgreSQLConnector

            connector = PostgreSQLConnector(
                datasource_id=datasource_id,
                host=host,
                port=port,
                database=database,
                username=username,
                password=password,
                pool_size=effective_pool_size,
            )
        elif dialect_lower == "doris":
            from datapilot_queryexec.connectors.doris import DorisConnector

            connector = DorisConnector(
                datasource_id=datasource_id,
                host=host,
                port=port,
                database=database,
                username=username,
                password=password,
                pool_size=effective_pool_size,
            )
        elif dialect_lower == "starrocks":
            from datapilot_queryexec.connectors.doris import StarRocksConnector

            connector = StarRocksConnector(
                datasource_id=datasource_id,
                host=host,
                port=port,
                database=database,
                username=username,
                password=password,
                pool_size=effective_pool_size,
            )
        elif dialect_lower == "clickhouse":
            from datapilot_queryexec.connectors.clickhouse import ClickHouseConnector

            connector = ClickHouseConnector(
                datasource_id=datasource_id,
                host=host,
                port=port,
                database=database,
                username=username,
                password=password,
                pool_size=effective_pool_size,
            )
        else:
            # 理论上 get_capabilities 已经拦截，这里做双重保护
            msg = f"不支持的方言: {dialect!r}"
            logger.error(msg, datasource_id=datasource_id)
            raise ValueError(msg)

        logger.info(
            "连接器创建成功",
            dialect=dialect_lower,
            datasource_id=datasource_id,
            pool_size=effective_pool_size,
        )
        return connector

    @staticmethod
    def supported_dialects() -> list[str]:
        """返回所有支持的方言列表。

        Returns:
            支持的方言名称列表。
        """
        from datapilot_queryexec.connectors.capabilities import CAPABILITY_MATRIX

        return sorted(CAPABILITY_MATRIX.keys())
