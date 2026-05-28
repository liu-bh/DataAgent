"""DataPilot Semantic Service - 元数据管理模块。

提供数据源注册、Schema 提取、元数据同步等能力。
"""

from datapilot_semantic.metadata.models import (
    DataSource,
    DataSourceHealth,
    SourceTable,
)
from datapilot_semantic.metadata.schemas import (
    ColumnSchema,
    DataSourceCreate,
    DataSourceHealthResponse,
    DataSourceResponse,
    DataSourceUpdate,
    SourceTableResponse,
    SyncResultResponse,
    TableSchema,
)

from datapilot_semantic.metadata.service import DataSourceService

__all__ = [
    "ColumnSchema",
    "DataSource",
    "DataSourceCreate",
    "DataSourceHealth",
    "DataSourceHealthResponse",
    "DataSourceResponse",
    "DataSourceService",
    "DataSourceUpdate",
    "SourceTable",
    "SourceTableResponse",
    "SyncResultResponse",
    "TableSchema",
]
