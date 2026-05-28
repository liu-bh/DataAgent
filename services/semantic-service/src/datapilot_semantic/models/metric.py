"""指标模型。

对应 metrics 表，存储语义指标的定义，支持版本管理和嵌套引用。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datapilot_common.database import Base, TenantBase


class Metric(TenantBase, Base):
    """指标模型。

    指标是语义模型的核心度量单位，支持：
    - 版本管理：每次更新创建新版本，version 自增
    - 嵌套引用：parent_metric_id 支持复合指标（如利润率 = 利润 / 营收）
    - 语义向量：embedding 用于语义搜索匹配
    """

    __tablename__ = "metrics"
    __table_args__ = (
        CheckConstraint(
            "version >= 1",
            name="ck_metrics_version_positive",
        ),
    )

    # --- 关联 ---
    semantic_model: Mapped["SemanticModel"] = relationship(  # noqa: F821
        "SemanticModel",
        back_populates="metrics",
        lazy="noload",
    )
    parent_metric: Mapped[Optional["Metric"]] = relationship(  # noqa: F821
        "Metric",
        remote_side="Metric.id",
        foreign_keys="Metric.parent_metric_id",
        lazy="noload",
    )
    metric_dimensions: Mapped[list["MetricDimension"]] = relationship(  # noqa: F821
        "MetricDimension",
        back_populates="metric",
        lazy="noload",
    )

    # --- 字段 ---
    semantic_model_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("semantic_models.id"),
        nullable=False,
        comment="所属语义模型 ID",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="指标名称，如 GMV",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="指标描述",
    )
    calculation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="计算表达式，如 SUM(amount)",
    )
    unit: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="单位：元/个/率",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="版本号，创建时为 1，更新时自动递增",
    )
    effective_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="版本生效时间",
    )
    parent_metric_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("metrics.id"),
        nullable=True,
        comment="父指标 ID（嵌套引用）",
    )
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(1536),
        nullable=True,
        comment="指标语义向量 (pgvector)",
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False,
        default=list,
        comment="标签数组",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="软删除时间，NULL 表示未删除",
    )
