"""Prompt 版本数据模型。

定义 prompt_versions 表的 SQLAlchemy 模型。
Prompt 是全局资源，不需要 tenant_id，所有租户共享 Prompt 模板。
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from datapilot_common.database import Base

# 合法场景枚举
VALID_SCENES = ("nl2sql", "intent", "explanation", "correction")


class PromptVersion(Base):
    """Prompt 版本模型。

    每个场景（nl2sql / intent / explanation / correction）可拥有多个版本，
    同一场景同时只能有一个激活版本（is_active=True）。

    Attributes:
        scene: 场景标识，取值范围 nl2sql/intent/explanation/correction。
        version: 该场景内的版本号，自动递增。
        content: Prompt 模板内容（Markdown 格式）。
        is_active: 是否为当前激活版本。
        effectiveness_score: A/B 测试效果评分 (0.0000 ~ 1.0000)。
        ab_test_traffic: A/B 测试流量比例 (0.00 ~ 1.00)，0 表示不参与 A/B 测试。
    """

    __tablename__ = "prompt_versions"

    # 主键继承自 Base（id: UUID PK, created_at, updated_at）
    id: Mapped[str] = mapped_column(  # type: ignore[assignment]
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    scene: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="场景标识：nl2sql/intent/explanation/correction",
    )

    version: Mapped[int] = mapped_column(
        nullable=False,
        comment="场景内版本号，自动递增",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Prompt 模板内容",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否为当前激活版本",
    )

    effectiveness_score: Mapped[float | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
        default=None,
        comment="A/B 测试效果评分 0.0000~1.0000",
    )

    ab_test_traffic: Mapped[float] = mapped_column(
        Numeric(3, 2),
        nullable=False,
        default=0.0,
        comment="A/B 测试流量比例 0.00~1.00，0 表示不参与",
    )

    # 覆盖 created_at / updated_at 为 TIMESTAMPTZ，继承自 Base
    # Base 已提供这两个字段，此处不需要重复定义

    __table_args__ = (
        # 场景取值约束
        CheckConstraint(
            "scene IN ('nl2sql', 'intent', 'explanation', 'correction')",
            name="ck_prompt_versions_scene",
        ),
        # 效果评分范围约束
        CheckConstraint(
            "effectiveness_score IS NULL OR (effectiveness_score >= 0.0000 AND effectiveness_score <= 1.0000)",
            name="ck_prompt_versions_score_range",
        ),
        # A/B 测试流量范围约束
        CheckConstraint(
            "ab_test_traffic >= 0.00 AND ab_test_traffic <= 1.00",
            name="ck_prompt_versions_traffic_range",
        ),
        # 同一场景+版本唯一
        UniqueConstraint(
            "scene",
            "version",
            name="uidx_prompt_versions_scene_version",
        ),
        {"comment": "Prompt 版本管理表，全局资源，不区分租户"},
    )
