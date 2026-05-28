"""语义模型。

对应 semantic_models 表，是语义层的核心组织单元，用于将指标和维度
按业务域分组管理。
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — SQLAlchemy Mapped[datetime] 需要运行时可用

from sqlalchemy import CheckConstraint, DateTime, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datapilot_common.database import Base, TenantBase

# 允许的业务域枚举值
VALID_DOMAINS = ("电商", "运营", "财务", "通用")


class SemanticModel(TenantBase, Base):
    """语义模型。

    一个语义模型代表一个业务视图，包含关联的指标、维度和源表关系。
    domain 字段限定为: 电商 / 运营 / 财务 / 通用。
    data_source_ids 为 UUID 数组，记录关联的数据源列表。
    """

    __tablename__ = "semantic_models"
    __table_args__ = (
        CheckConstraint(
            "domain IN ('电商', '运营', '财务', '通用')",
            name="ck_semantic_models_domain",
        ),
    )

    # --- 关联 ---
    metrics: Mapped[list[Metric]] = relationship(  # noqa: F821
        "Metric",
        back_populates="semantic_model",
        lazy="noload",
    )
    dimensions: Mapped[list[Dimension]] = relationship(  # noqa: F821
        "Dimension",
        back_populates="semantic_model",
        lazy="noload",
    )
    table_relationships: Mapped[list[TableRelationship]] = relationship(  # noqa: F821
        "TableRelationship",
        back_populates="semantic_model",
        lazy="noload",
    )

    # --- 字段 ---
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="业务语义视图名称",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="视图描述",
    )
    domain: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="业务域（电商/运营/财务/通用）",
    )
    data_source_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String(36)),
        nullable=False,
        default=list,
        comment="关联的数据源 ID 数组",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="软删除时间，NULL 表示未删除",
    )
