"""维度模型。

对应 dimensions 表，存储语义维度的定义，支持同义词、层级和虚拟维度。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datapilot_common.database import Base, TenantBase


class Dimension(TenantBase, Base):
    """维度模型。

    维度用于描述指标的分组和切片视角，支持：
    - 同义词：synonyms 数组，用于 NL2SQL 时的语义匹配
    - 层级：hierarchy JSONB，描述维度层级关系
    - 虚拟维度：is_virtual=true 时使用 virtual_expression 进行 CASE WHEN 计算
    - 语义向量：embedding 用于语义搜索匹配
    """

    __tablename__ = "dimensions"
    __table_args__ = (
        CheckConstraint(
            "(is_virtual IS FALSE) OR (is_virtual IS TRUE AND virtual_expression IS NOT NULL)",
            name="ck_dimensions_virtual_expression",
        ),
    )

    # --- 关联 ---
    semantic_model: Mapped["SemanticModel"] = relationship(  # noqa: F821
        "SemanticModel",
        back_populates="dimensions",
        lazy="noload",
    )
    source_table: Mapped[Optional["SourceTable"]] = relationship(  # noqa: F821
        "SourceTable",
        back_populates="dimensions",
        lazy="noload",
    )
    metric_dimensions: Mapped[list["MetricDimension"]] = relationship(  # noqa: F821
        "MetricDimension",
        back_populates="dimension",
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
        comment="维度名称，如 地区",
    )
    column_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="对应物理列名",
    )
    table_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("source_tables.id"),
        nullable=True,
        comment="所属源表 ID",
    )
    synonyms: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False,
        default=list,
        comment="同义词数组，如 ['区域', '大区', '省份']",
    )
    hierarchy: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="层级定义，如 {level: 'province', children: ['city', 'district']}",
    )
    is_virtual: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否虚拟维度（CASE WHEN 计算）",
    )
    virtual_expression: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="虚拟维度表达式（is_virtual=true 时必填）",
    )
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(1536),
        nullable=True,
        comment="维度语义向量 (pgvector)",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="软删除时间，NULL 表示未删除",
    )
