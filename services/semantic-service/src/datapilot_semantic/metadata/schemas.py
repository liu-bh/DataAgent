"""Pydantic Schema 定义 - 数据源请求/响应模型。

用于 API 路由的请求体校验和响应序列化。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 数据源连接配置（内部使用）
# ---------------------------------------------------------------------------


class DataConnectionConfig(BaseModel):
    """数据源连接配置。

    用于内部连接池管理和 Schema 提取。
    """

    type: str = Field(..., description="数据源类型: mysql/postgresql/doris/starrocks/clickhouse")
    host: str = Field(..., description="连接地址")
    port: int = Field(..., description="端口", gt=0, lt=65536)
    database: str = Field(..., description="数据库名")
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码（明文，仅用于连接）")


# ---------------------------------------------------------------------------
# 数据源 CRUD Schema
# ---------------------------------------------------------------------------


class DataSourceCreate(BaseModel):
    """创建数据源请求体。"""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., min_length=1, max_length=100, description="数据源名称")
    type: str = Field(
        ...,
        pattern=r"^(mysql|postgresql|doris|starrocks|clickhouse|api)$",
        description="数据源类型",
    )
    host: str = Field(..., min_length=1, max_length=255, description="连接地址")
    port: int = Field(..., gt=0, lt=65536, description="端口")
    database: str = Field(..., min_length=1, max_length=100, description="数据库名")
    username: str = Field(..., min_length=1, max_length=100, description="用户名")
    password: str = Field(..., min_length=1, description="密码")
    pool_size: Optional[int] = Field(default=5, ge=1, le=50, description="连接池大小")
    freshness_level: Optional[str] = Field(
        default=None,
        pattern=r"^(realtime|hourly|daily|custom)$",
        description="数据新鲜度",
    )
    freshness_cron: Optional[str] = Field(
        default=None, max_length=100, description="数据新鲜度同步频率"
    )


class DataSourceUpdate(BaseModel):
    """更新数据源请求体（所有字段可选）。"""

    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    host: Optional[str] = Field(default=None, min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, gt=0, lt=65536)
    database: Optional[str] = Field(default=None, min_length=1, max_length=100)
    username: Optional[str] = Field(default=None, min_length=1, max_length=100)
    password: Optional[str] = Field(default=None, min_length=1)
    pool_size: Optional[int] = Field(default=None, ge=1, le=50)
    freshness_level: Optional[str] = Field(
        default=None,
        pattern=r"^(realtime|hourly|daily|custom)$",
    )
    freshness_cron: Optional[str] = Field(default=None, max_length=100)
    status: Optional[str] = Field(
        default=None, pattern=r"^(active|disabled)$"
    )


class DataSourceResponse(BaseModel):
    """数据源详情响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    type: str
    host: str
    port: int
    database: str
    username: str
    # 注意：不返回密码
    pool_size: Optional[int] = None
    freshness_level: Optional[str] = None
    freshness_cron: Optional[str] = None
    status: str
    last_health_check: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# 数据源健康 Schema
# ---------------------------------------------------------------------------


class DataSourceHealthResponse(BaseModel):
    """数据源健康检查响应。"""

    model_config = ConfigDict(from_attributes=True)

    datasource_id: UUID
    pool_usage: Optional[float] = None
    avg_latency_ms: Optional[int] = None
    status: str
    last_heartbeat: datetime
    created_at: datetime


# ---------------------------------------------------------------------------
# 源表 Schema
# ---------------------------------------------------------------------------


class ColumnSchema(BaseModel):
    """列定义 Schema。"""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="列名")
    type: str = Field(..., description="列类型")
    is_primary_key: bool = Field(default=False, description="是否主键")
    description: Optional[str] = Field(default=None, description="列描述")


class TableSchema(BaseModel):
    """表结构 Schema（Schema Extractor 返回值）。"""

    model_config = ConfigDict(from_attributes=True)

    table_name: str = Field(..., description="表名")
    schema_name: Optional[str] = Field(default=None, description="Schema 名")
    columns: list[ColumnSchema] = Field(default_factory=list, description="列定义列表")
    description: Optional[str] = Field(default=None, description="表描述")
    row_count: Optional[int] = Field(default=None, description="估算行数")


class SourceTableResponse(BaseModel):
    """源表响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    data_source_id: UUID
    schema_name: Optional[str] = None
    table_name: str
    columns: Optional[list[dict[str, Any]]] = None
    row_count: Optional[int] = None
    description: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# 同步结果 Schema
# ---------------------------------------------------------------------------


class SyncResultResponse(BaseModel):
    """元数据同步结果响应。"""

    model_config = ConfigDict(from_attributes=True)

    datasource_id: UUID
    status: str = Field(..., description="同步状态: success/partial/failed")
    total_tables: int = Field(..., description="发现的表总数")
    synced_tables: int = Field(..., description="成功同步的表数")
    updated_tables: int = Field(..., description="更新的表数")
    new_tables: int = Field(..., description="新增的表数")
    failed_tables: int = Field(default=0, description="失败的表数")
    message: Optional[str] = Field(default=None, description="同步说明")
    synced_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="同步完成时间",
    )
