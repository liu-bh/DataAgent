"""Prompt 管理相关 Pydantic Schema。

定义 Prompt 创建、响应、激活、A/B 测试结果等数据传输对象。
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — Pydantic 需要 datetime 运行时可用
from decimal import Decimal  # noqa: TC003 — Pydantic 需要 Decimal 运行时可用
from typing import Literal
from uuid import UUID  # noqa: TC003 — Pydantic 需要 UUID 运行时可用

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# 场景类型
# ---------------------------------------------------------------------------

SceneType = Literal["nl2sql", "intent", "explanation", "correction"]


# ---------------------------------------------------------------------------
# 创建 Prompt
# ---------------------------------------------------------------------------


class PromptCreate(BaseModel):
    """创建 Prompt 版本请求体。

    Attributes:
        scene: 场景标识。
        content: Prompt 模板内容。
        ab_test_traffic: A/B 测试流量比例，0~1，默认 0（不参与）。
        version_description: 版本描述说明（可选）。
    """

    scene: SceneType
    content: str = Field(..., min_length=1, description="Prompt 模板内容")
    ab_test_traffic: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="A/B 测试流量比例，0 表示不参与",
    )
    version_description: str | None = Field(
        default=None,
        max_length=500,
        description="版本描述说明",
    )

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Prompt 响应
# ---------------------------------------------------------------------------


class PromptResponse(BaseModel):
    """Prompt 版本响应体。

    Attributes:
        id: Prompt 版本 ID。
        scene: 场景标识。
        version: 版本号。
        content: Prompt 模板内容。
        is_active: 是否为当前激活版本。
        effectiveness_score: A/B 测试效果评分。
        ab_test_traffic: A/B 测试流量比例。
        created_at: 创建时间。
    """

    id: UUID
    scene: str
    version: int
    content: str
    is_active: bool
    effectiveness_score: Decimal | None = None
    ab_test_traffic: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# 激活响应
# ---------------------------------------------------------------------------


class PromptActivateResponse(BaseModel):
    """激活 Prompt 版本响应体。

    Attributes:
        prompt_id: 被激活的 Prompt 版本 ID。
        scene: 场景标识。
        version: 版本号。
        message: 激活结果说明。
    """

    prompt_id: UUID
    scene: str
    version: int
    message: str

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# A/B 测试结果
# ---------------------------------------------------------------------------


class ABTestVersionMetrics(BaseModel):
    """A/B 测试单版本指标。

    Attributes:
        prompt_id: Prompt 版本 ID。
        traffic: 分配流量比例。
        execution_accuracy: SQL 执行准确率。
        avg_latency_ms: 平均延迟（毫秒）。
        user_edit_rate: 用户编辑率。
        satisfaction_rate: 用户满意度。
        sample_count: 样本数量。
    """

    prompt_id: UUID
    traffic: float
    execution_accuracy: float | None = None
    avg_latency_ms: float | None = None
    user_edit_rate: float | None = None
    satisfaction_rate: float | None = None
    sample_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ABTestResults(BaseModel):
    """A/B 测试结果对比。

    Attributes:
        version_a: 版本 A 的指标（通常为当前激活版本）。
        version_b: 版本 B 的指标（实验版本）。
        recommendation: 推荐结论：version_a / version_b / no_significant_difference。
        confidence: 置信度 0~1。
    """

    version_a: ABTestVersionMetrics
    version_b: ABTestVersionMetrics
    recommendation: Literal["version_a", "version_b", "no_significant_difference"]
    confidence: float = Field(ge=0.0, le=1.0, description="推荐置信度")

    model_config = ConfigDict(from_attributes=True)
