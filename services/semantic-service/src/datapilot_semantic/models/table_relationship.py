"""表关系模型。

对应 table_relationships 表，定义语义模型中源表之间的 JOIN 路径。
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — SQLAlchemy Mapped[datetime] 需要运行时可用

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datapilot_common.database import Base, TenantBase


class TableRelationship(TenantBase, Base):
    """表关系模型。

    定义语义模型中两个源表之间的关联关系，包括连接类型和连接条件。
    join_type 限定为: inner / left / right / full。
    """

    __tablename__ = "table_relationships"
    __table_args__ = (
        CheckConstraint(
            "join_type IN ('inner', 'left', 'right', 'full')",
            name="ck_table_relationships_join_type",
        ),
    )

    # --- 关联 ---
    semantic_model: Mapped[SemanticModel] = relationship(  # noqa: F821
        "SemanticModel",
        back_populates="table_relationships",
        lazy="noload",
    )
    left_table: Mapped[SourceTable] = relationship(  # noqa: F821
        "SourceTable",
        back_populates="left_relationships",
        foreign_keys="TableRelationship.left_table_id",
        lazy="noload",
    )
    right_table: Mapped[SourceTable] = relationship(  # noqa: F821
        "SourceTable",
        back_populates="right_relationships",
        foreign_keys="TableRelationship.right_table_id",
        lazy="noload",
    )

    # --- 字段 ---
    semantic_model_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("semantic_models.id"),
        nullable=False,
        comment="所属语义模型 ID",
    )
    left_table_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("source_tables.id"),
        nullable=False,
        comment="左表 ID",
    )
    right_table_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("source_tables.id"),
        nullable=False,
        comment="右表 ID",
    )
    join_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="连接类型：inner/left/right/full",
    )
    join_condition: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="连接条件，如 orders.user_id = users.id",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="软删除时间，NULL 表示未删除",
    )
