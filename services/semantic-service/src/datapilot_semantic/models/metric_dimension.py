"""指标-维度关联模型。

对应 metric_dimensions 关联表，实现指标与维度的多对多关系。
复合主键 (metric_id, dimension_id)。
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datapilot_common.database import Base


class MetricDimension(Base):
    """指标-维度关联模型。

    多对多中间表，一个指标可关联多个维度，一个维度也可被多个指标引用。
    复合主键由 metric_id 和 dimension_id 组成。
    注意：此表不继承 TenantBase，因为 tenant 信息通过关联的 metric/dimension 间接获取。
    """

    __tablename__ = "metric_dimensions"
    __table_args__ = (
        PrimaryKeyConstraint(
            "metric_id",
            "dimension_id",
            name="pk_metric_dimensions",
        ),
    )

    # --- 关联 ---
    metric: Mapped[Metric] = relationship(  # noqa: F821
        "Metric",
        back_populates="metric_dimensions",
        lazy="noload",
    )
    dimension: Mapped[Dimension] = relationship(  # noqa: F821
        "Dimension",
        back_populates="metric_dimensions",
        lazy="noload",
    )

    # --- 字段 ---
    metric_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("metrics.id", ondelete="CASCADE"),
        nullable=False,
        comment="指标 ID",
    )
    dimension_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("dimensions.id", ondelete="CASCADE"),
        nullable=False,
        comment="维度 ID",
    )
