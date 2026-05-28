"""多数据源连接器模块。

提供 MySQL、PostgreSQL、Doris/StarRocks、ClickHouse 的异步连接器，
以及连接器工厂、数据源能力矩阵和差异化重试策略。

用法::

    from datapilot_queryexec.connectors import ConnectorFactory, RetryPolicy

    connector = ConnectorFactory.create(
        dialect="mysql",
        datasource_id="ds-001",
        host="localhost",
        port=3306,
        database="mydb",
        username="root",
        password="secret",
    )
    await connector.connect()
    result = await connector.execute("SELECT 1")
"""

from datapilot_queryexec.connectors.base import BaseConnector, ConnectorHealth, ExecuteResult
from datapilot_queryexec.connectors.capabilities import (
    DataSourceCapabilities,
    check_feature,
    get_capabilities,
)
from datapilot_queryexec.connectors.factory import ConnectorFactory
from datapilot_queryexec.connectors.retry import RetryPolicy

__all__ = [
    "BaseConnector",
    "ConnectorFactory",
    "ConnectorHealth",
    "DataSourceCapabilities",
    "ExecuteResult",
    "RetryPolicy",
    "check_feature",
    "get_capabilities",
]
