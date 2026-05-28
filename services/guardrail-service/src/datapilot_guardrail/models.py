"""Guardrail 数据模型。

定义风险等级、检查结果和配额配置等核心数据结构。
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(StrEnum):
    """SQL 风险等级。"""

    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


class GuardrailResult(BaseModel):
    """Guardrail 检查结果。

    Attributes:
        passed: 是否通过所有检查。
        risk_level: SQL 风险等级。
        blocked_reason: 拦截原因（仅在 passed=False 时有值）。
        max_rows: 允许的最大返回行数。
        quota_remaining: 剩余配额（-1 表示未启用或不可用）。
        warnings: 检查过程中的警告信息列表。
    """

    model_config = ConfigDict(from_attributes=True)

    passed: bool
    risk_level: RiskLevel = RiskLevel.SAFE
    blocked_reason: str = ""
    max_rows: int = 10000
    quota_remaining: int = -1
    warnings: list[str] = Field(default_factory=list)


class QuotaConfig(BaseModel):
    """查询配额配置。

    Attributes:
        daily_limit: 每日查询次数上限。
        hourly_limit: 每小时查询次数上限。
        max_rows_per_query: 单次查询最大返回行数。
    """

    model_config = ConfigDict(from_attributes=True)

    daily_limit: int = 1000
    hourly_limit: int = 200
    max_rows_per_query: int = 10000
