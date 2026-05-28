"""创建语义层全部表。

Revision ID: 20260527_001
Revises: None
Create Date: 2026-05-27

创建以下表：
- data_sources: 数据源
- datasource_health: 数据源健康检查
- source_tables: 源表元数据
- semantic_models: 语义模型
- metrics: 指标（含版本管理）
- dimensions: 维度（含虚拟维度）
- metric_dimensions: 指标-维度关联表
- table_relationships: 表关系

同时创建必要的索引，包括 pgvector 向量索引和 GIN 数组索引。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260527_001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# 启用 pgvector 扩展
# ---------------------------------------------------------------------------


def _enable_extensions() -> None:
    """启用必要的 PostgreSQL 扩展。"""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')


# ---------------------------------------------------------------------------
# data_sources
# ---------------------------------------------------------------------------


def _create_data_sources() -> None:
    """创建 data_sources 表。"""
    op.create_table(
        "data_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("database", sa.String(100), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("password", sa.Text(), nullable=False),
        sa.Column("pool_size", sa.Integer(), nullable=True),
        sa.Column("freshness_level", sa.String(10), nullable=True),
        sa.Column("freshness_cron", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 约束
    op.create_check_constraint(
        "ck_data_sources_type",
        "data_sources",
        "type IN ('mysql','postgresql','doris','starrocks','clickhouse','api')",
    )
    op.create_check_constraint(
        "ck_data_sources_status",
        "data_sources",
        "status IN ('active','disabled')",
    )
    op.create_check_constraint(
        "ck_data_sources_freshness_level",
        "data_sources",
        "freshness_level IS NULL OR freshness_level IN ('realtime','hourly','daily','custom')",
    )
    # 索引
    op.create_index("idx_data_sources_tenant", "data_sources", ["tenant_id"])
    op.create_index("idx_data_sources_type", "data_sources", ["type"])
    op.create_index(
        "idx_data_sources_deleted_at",
        "data_sources",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def _drop_data_sources() -> None:
    """删除 data_sources 表。"""
    op.drop_index("idx_data_sources_deleted_at", table_name="data_sources")
    op.drop_index("idx_data_sources_type", table_name="data_sources")
    op.drop_index("idx_data_sources_tenant", table_name="data_sources")
    op.drop_constraint("ck_data_sources_freshness_level", "data_sources", type_="check")
    op.drop_constraint("ck_data_sources_status", "data_sources", type_="check")
    op.drop_constraint("ck_data_sources_type", "data_sources", type_="check")
    op.drop_table("data_sources")


# ---------------------------------------------------------------------------
# datasource_health
# ---------------------------------------------------------------------------


def _create_datasource_health() -> None:
    """创建 datasource_health 表。"""
    op.create_table(
        "datasource_health",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("datasource_id", sa.String(36), nullable=False),
        sa.Column("pool_usage", sa.Numeric(5, 2), nullable=True),
        sa.Column("avg_latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "last_heartbeat",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # 约束
    op.create_check_constraint(
        "ck_datasource_health_status",
        "datasource_health",
        "status IN ('healthy','degraded','down')",
    )
    # 外键
    op.create_foreign_key(
        "fk_datasource_health_datasource_id",
        "datasource_health",
        "data_sources",
        ["datasource_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # 索引
    op.create_index("idx_datasource_health_datasource", "datasource_health", ["datasource_id"])
    op.create_index(
        "idx_datasource_health_status",
        "datasource_health",
        ["status", "last_heartbeat"],
    )


def _drop_datasource_health() -> None:
    """删除 datasource_health 表。"""
    op.drop_index("idx_datasource_health_status", table_name="datasource_health")
    op.drop_index("idx_datasource_health_datasource", table_name="datasource_health")
    op.drop_constraint(
        "fk_datasource_health_datasource_id", "datasource_health", type_="foreignkey"
    )
    op.drop_constraint("ck_datasource_health_status", "datasource_health", type_="check")
    op.drop_table("datasource_health")


# ---------------------------------------------------------------------------
# source_tables
# ---------------------------------------------------------------------------


def _create_source_tables() -> None:
    """创建 source_tables 表。"""
    op.create_table(
        "source_tables",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("data_source_id", sa.String(36), nullable=False),
        sa.Column("schema_name", sa.String(100), nullable=True),
        sa.Column("table_name", sa.String(100), nullable=False),
        sa.Column(
            "columns",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 约束
    op.create_check_constraint(
        "ck_source_tables_row_count_non_negative",
        "source_tables",
        "row_count >= 0",
    )
    # 外键
    op.create_foreign_key(
        "fk_source_tables_data_source_id",
        "source_tables",
        "data_sources",
        ["data_source_id"],
        ["id"],
    )
    # 索引
    op.create_index("idx_source_tables_tenant", "source_tables", ["tenant_id"])
    op.create_index(
        "idx_source_tables_deleted_at",
        "source_tables",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_source_tables_data_source",
        "source_tables",
        ["data_source_id"],
    )
    # 向量索引 (IVFFlat)
    op.execute("""
        CREATE INDEX idx_source_tables_embedding
        ON source_tables USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)


def _drop_source_tables() -> None:
    """删除 source_tables 表。"""
    op.drop_index("idx_source_tables_embedding", table_name="source_tables")
    op.drop_index("idx_source_tables_data_source", table_name="source_tables")
    op.drop_index("idx_source_tables_deleted_at", table_name="source_tables")
    op.drop_index("idx_source_tables_tenant", table_name="source_tables")
    op.drop_constraint("fk_source_tables_data_source_id", "source_tables", type_="foreignkey")
    op.drop_constraint("ck_source_tables_row_count_non_negative", "source_tables", type_="check")
    op.drop_table("source_tables")


# ---------------------------------------------------------------------------
# semantic_models
# ---------------------------------------------------------------------------


def _create_semantic_models() -> None:
    """创建 semantic_models 表。"""
    op.create_table(
        "semantic_models",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column(
            "data_source_ids",
            postgresql.ARRAY(sa.String(36)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 域名约束
    op.create_check_constraint(
        "ck_semantic_models_domain",
        "semantic_models",
        "domain IN ('电商', '运营', '财务', '通用')",
    )
    # 索引
    op.create_index("idx_semantic_models_tenant", "semantic_models", ["tenant_id"])
    op.create_index("idx_semantic_models_domain", "semantic_models", ["domain"])
    op.create_index(
        "idx_semantic_models_deleted_at",
        "semantic_models",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # GIN 索引支持数组查询
    op.create_index(
        "idx_semantic_models_data_source_ids",
        "semantic_models",
        ["data_source_ids"],
        postgresql_using="gin",
    )


def _drop_semantic_models() -> None:
    """删除 semantic_models 表。"""
    op.drop_index("idx_semantic_models_data_source_ids", table_name="semantic_models")
    op.drop_index("idx_semantic_models_deleted_at", table_name="semantic_models")
    op.drop_index("idx_semantic_models_domain", table_name="semantic_models")
    op.drop_index("idx_semantic_models_tenant", table_name="semantic_models")
    op.drop_constraint("ck_semantic_models_domain", "semantic_models", type_="check")
    op.drop_table("semantic_models")


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------


def _create_metrics() -> None:
    """创建 metrics 表。"""
    op.create_table(
        "metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("semantic_model_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("calculation", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("effective_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parent_metric_id", sa.String(36), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String(50)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 约束
    op.create_check_constraint(
        "ck_metrics_version_positive",
        "metrics",
        "version >= 1",
    )
    # 外键
    op.create_foreign_key(
        "fk_metrics_semantic_model_id",
        "metrics",
        "semantic_models",
        ["semantic_model_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_metrics_parent_metric_id",
        "metrics",
        "metrics",
        ["parent_metric_id"],
        ["id"],
    )
    # 索引
    op.create_index("idx_metrics_tenant", "metrics", ["tenant_id"])
    op.create_index("idx_metrics_semantic_model", "metrics", ["semantic_model_id"])
    op.create_index("idx_metrics_name", "metrics", ["name"])
    op.create_index(
        "idx_metrics_deleted_at",
        "metrics",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # 向量索引
    op.execute("""
        CREATE INDEX idx_metrics_embedding
        ON metrics USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
    # GIN 索引支持标签搜索
    op.create_index(
        "idx_metrics_tags",
        "metrics",
        ["tags"],
        postgresql_using="gin",
    )


def _drop_metrics() -> None:
    """删除 metrics 表。"""
    op.drop_index("idx_metrics_tags", table_name="metrics")
    op.drop_index("idx_metrics_embedding", table_name="metrics")
    op.drop_index("idx_metrics_deleted_at", table_name="metrics")
    op.drop_index("idx_metrics_name", table_name="metrics")
    op.drop_index("idx_metrics_semantic_model", table_name="metrics")
    op.drop_index("idx_metrics_tenant", table_name="metrics")
    op.drop_constraint("fk_metrics_parent_metric_id", "metrics", type_="foreignkey")
    op.drop_constraint("fk_metrics_semantic_model_id", "metrics", type_="foreignkey")
    op.drop_constraint("ck_metrics_version_positive", "metrics", type_="check")
    op.drop_table("metrics")


# ---------------------------------------------------------------------------
# dimensions
# ---------------------------------------------------------------------------


def _create_dimensions() -> None:
    """创建 dimensions 表。"""
    op.create_table(
        "dimensions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("semantic_model_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("column_name", sa.String(200), nullable=True),
        sa.Column("table_id", sa.String(36), nullable=True),
        sa.Column(
            "synonyms",
            postgresql.ARRAY(sa.String(50)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "hierarchy",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("is_virtual", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("virtual_expression", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 约束：虚拟维度必须有表达式
    op.create_check_constraint(
        "ck_dimensions_virtual_expression",
        "dimensions",
        "(is_virtual IS FALSE) OR (is_virtual IS TRUE AND virtual_expression IS NOT NULL)",
    )
    # 外键
    op.create_foreign_key(
        "fk_dimensions_semantic_model_id",
        "dimensions",
        "semantic_models",
        ["semantic_model_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_dimensions_table_id",
        "dimensions",
        "source_tables",
        ["table_id"],
        ["id"],
    )
    # 索引
    op.create_index("idx_dimensions_tenant", "dimensions", ["tenant_id"])
    op.create_index("idx_dimensions_semantic_model", "dimensions", ["semantic_model_id"])
    op.create_index(
        "idx_dimensions_deleted_at",
        "dimensions",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # 向量索引
    op.execute("""
        CREATE INDEX idx_dimensions_embedding
        ON dimensions USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)


def _drop_dimensions() -> None:
    """删除 dimensions 表。"""
    op.drop_index("idx_dimensions_embedding", table_name="dimensions")
    op.drop_index("idx_dimensions_deleted_at", table_name="dimensions")
    op.drop_index("idx_dimensions_semantic_model", table_name="dimensions")
    op.drop_index("idx_dimensions_tenant", table_name="dimensions")
    op.drop_constraint("fk_dimensions_table_id", "dimensions", type_="foreignkey")
    op.drop_constraint("fk_dimensions_semantic_model_id", "dimensions", type_="foreignkey")
    op.drop_constraint("ck_dimensions_virtual_expression", "dimensions", type_="check")
    op.drop_table("dimensions")


# ---------------------------------------------------------------------------
# metric_dimensions
# ---------------------------------------------------------------------------


def _create_metric_dimensions() -> None:
    """创建 metric_dimensions 关联表。"""
    op.create_table(
        "metric_dimensions",
        sa.Column("metric_id", sa.String(36), nullable=False),
        sa.Column("dimension_id", sa.String(36), nullable=False),
        sa.PrimaryKeyConstraint("metric_id", "dimension_id", name="pk_metric_dimensions"),
    )
    # 外键
    op.create_foreign_key(
        "fk_metric_dimensions_metric_id",
        "metric_dimensions",
        "metrics",
        ["metric_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_metric_dimensions_dimension_id",
        "metric_dimensions",
        "dimensions",
        ["dimension_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # 索引
    op.create_index(
        "idx_metric_dimensions_dimension_id",
        "metric_dimensions",
        ["dimension_id"],
    )


def _drop_metric_dimensions() -> None:
    """删除 metric_dimensions 关联表。"""
    op.drop_index("idx_metric_dimensions_dimension_id", table_name="metric_dimensions")
    op.drop_constraint("fk_metric_dimensions_dimension_id", "metric_dimensions", type_="foreignkey")
    op.drop_constraint("fk_metric_dimensions_metric_id", "metric_dimensions", type_="foreignkey")
    op.drop_table("metric_dimensions")


# ---------------------------------------------------------------------------
# table_relationships
# ---------------------------------------------------------------------------


def _create_table_relationships() -> None:
    """创建 table_relationships 表。"""
    op.create_table(
        "table_relationships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("semantic_model_id", sa.String(36), nullable=False),
        sa.Column("left_table_id", sa.String(36), nullable=False),
        sa.Column("right_table_id", sa.String(36), nullable=False),
        sa.Column("join_type", sa.String(20), nullable=False),
        sa.Column("join_condition", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 约束
    op.create_check_constraint(
        "ck_table_relationships_join_type",
        "table_relationships",
        "join_type IN ('inner', 'left', 'right', 'full')",
    )
    # 外键
    op.create_foreign_key(
        "fk_table_relationships_semantic_model_id",
        "table_relationships",
        "semantic_models",
        ["semantic_model_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_table_relationships_left_table_id",
        "table_relationships",
        "source_tables",
        ["left_table_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_table_relationships_right_table_id",
        "table_relationships",
        "source_tables",
        ["right_table_id"],
        ["id"],
    )
    # 索引
    op.create_index(
        "idx_table_relationships_tenant",
        "table_relationships",
        ["tenant_id"],
    )
    op.create_index(
        "idx_table_relationships_semantic_model",
        "table_relationships",
        ["semantic_model_id"],
    )
    op.create_index(
        "idx_table_relationships_deleted_at",
        "table_relationships",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def _drop_table_relationships() -> None:
    """删除 table_relationships 表。"""
    op.drop_index("idx_table_relationships_deleted_at", table_name="table_relationships")
    op.drop_index("idx_table_relationships_semantic_model", table_name="table_relationships")
    op.drop_index("idx_table_relationships_tenant", table_name="table_relationships")
    op.drop_constraint(
        "fk_table_relationships_right_table_id", "table_relationships", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_table_relationships_left_table_id", "table_relationships", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_table_relationships_semantic_model_id", "table_relationships", type_="foreignkey"
    )
    op.drop_constraint("ck_table_relationships_join_type", "table_relationships", type_="check")
    op.drop_table("table_relationships")


# ---------------------------------------------------------------------------
# upgrade / downgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    """创建语义层全部表。"""
    _enable_extensions()

    # 按依赖顺序创建
    _create_data_sources()
    _create_datasource_health()
    _create_source_tables()
    _create_semantic_models()
    _create_metrics()
    _create_dimensions()
    _create_metric_dimensions()
    _create_table_relationships()


def downgrade() -> None:
    """删除语义层全部表。"""
    # 按依赖反序删除
    _drop_table_relationships()
    _drop_metric_dimensions()
    _drop_dimensions()
    _drop_metrics()
    _drop_semantic_models()
    _drop_source_tables()
    _drop_datasource_health()
    _drop_data_sources()
