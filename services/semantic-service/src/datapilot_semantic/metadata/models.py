"""SQLAlchemy 模型定义 - 数据源、数据源健康、源表。

对应数据库表: data_sources, datasource_health, source_tables
所有业务表继承 TenantBase（包含 tenant_id），软删除通过 deleted_at 实现。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datapilot_common.database import Base, TenantBase


# ---------------------------------------------------------------------------
# DataSource 数据源
# ---------------------------------------------------------------------------


class DataSource(TenantBase, Base):
    """数据源表。

    存储外部数据源连接信息，密码加密存储。
    """

    __tablename__ = "data_sources"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="数据源名称")
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="数据源类型: mysql/postgresql/doris/starrocks/clickhouse/api",
    )
    host: Mapped[str] = mapped_column(String(255), nullable=False, comment="连接地址")
    port: Mapped[int] = mapped_column(Integer, nullable=False, comment="端口")
    database: Mapped[str] = mapped_column(String(100), nullable=False, comment="数据库名")
    username: Mapped[str] = mapped_column(String(100), nullable=False, comment="用户名")
    password: Mapped[str] = mapped_column(Text, nullable=False, comment="加密存储的密码")
    pool_size: Mapped[int] = mapped_column(Integer, nullable=True, comment="连接池大小")
    freshness_level: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="数据新鲜度: realtime/hourly/daily/custom",
    )
    freshness_cron: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="数据新鲜度同步频率（仅 custom）"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="active",
        comment="状态: active/disabled",
    )
    last_health_check: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最后健康检查时间"
    )
    # 软删除
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="软删除时间"
    )

    # 关系
    health_records: Mapped[list[DataSourceHealth]] = relationship(
        "DataSourceHealth",
        back_populates="datasource",
        lazy="selectin",
    )
    source_tables: Mapped[list[SourceTable]] = relationship(
        "SourceTable",
        back_populates="datasource",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint("type IN ('mysql','postgresql','doris','starrocks','clickhouse','api')", name="ck_data_sources_type"),
        CheckConstraint("status IN ('active','disabled')", name="ck_data_sources_status"),
        CheckConstraint(
            "freshness_level IS NULL OR freshness_level IN ('realtime','hourly','daily','custom')",
            name="ck_data_sources_freshness_level",
        ),
        Index("idx_data_sources_tenant_deleted", "tenant_id", "deleted_at"),
        Index("idx_data_sources_type", "type"),
    )


# ---------------------------------------------------------------------------
# DataSourceHealth 数据源健康
# ---------------------------------------------------------------------------


class DataSourceHealth(Base):
    """数据源健康检查记录表。

    记录数据源的健康状态，不含 tenant_id（健康数据跟随数据源）。
    """

    __tablename__ = "datasource_health"

    datasource_id: Mapped[UUID] = mapped_column(
        String(36),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联数据源 ID",
    )
    pool_usage: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="连接池使用率（百分比）"
    )
    avg_latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="平均查询延迟（毫秒）"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="健康状态: healthy/degraded/down",
    )
    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="最后心跳时间",
    )

    # 关系
    datasource: Mapped[DataSource] = relationship(
        "DataSource",
        back_populates="health_records",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('healthy','degraded','down')",
            name="ck_datasource_health_status",
        ),
        Index("idx_datasource_health_status", "status", "last_heartbeat"),
    )


# ---------------------------------------------------------------------------
# SourceTable 源表元数据
# ---------------------------------------------------------------------------


class SourceTable(TenantBase, Base):
    """源表元数据表。

    存储从外部数据源同步过来的表结构信息。
    embedding 字段预留为 nullable，由 Track C 负责向量化。
    被 Dimension.table_id、TableRelationship.left_table_id/right_table_id 引用。
    """

    __tablename__ = "source_tables"

    data_source_id: Mapped[UUID] = mapped_column(
        String(36),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联数据源 ID",
    )
    schema_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Schema 名"
    )
    table_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="表名"
    )
    columns: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="列定义 [{name, type, description, is_primary_key}]",
    )
    row_count: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="估算行数"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="表描述"
    )
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(1536),
        nullable=True,
        comment="表级语义向量（Track C 负责）",
    )
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最后同步时间"
    )
    # 软删除
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="软删除时间"
    )

    # 关系
    datasource: Mapped[DataSource] = relationship(
        "DataSource",
        back_populates="source_tables",
    )
    # 被 Dimension 的 table_id 引用
    dimensions: Mapped[list[Dimension]] = relationship(  # noqa: F821
        "Dimension",
        back_populates="source_table",
        lazy="noload",
    )
    # 被 TableRelationship 引用
    left_relationships: Mapped[list[TableRelationship]] = relationship(  # noqa: F821
        "TableRelationship",
        back_populates="left_table",
        foreign_keys="TableRelationship.left_table_id",
        lazy="noload",
    )
    right_relationships: Mapped[list[TableRelationship]] = relationship(  # noqa: F821
        "TableRelationship",
        back_populates="right_table",
        foreign_keys="TableRelationship.right_table_id",
        lazy="noload",
    )

    __table_args__ = (
        CheckConstraint(
            "row_count IS NULL OR row_count >= 0",
            name="ck_source_tables_row_count_non_negative",
        ),
        Index(
            "idx_source_tables_datasource_table",
            "data_source_id",
            "table_name",
        ),
        Index("idx_source_tables_tenant_deleted", "tenant_id", "deleted_at"),
    )
