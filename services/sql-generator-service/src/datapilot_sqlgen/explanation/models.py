"""SQL 自然语言解释结果数据模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SQLExplanation(BaseModel):
    """SQL 自然语言解释结果。

    Attributes:
        summary: 一句话解释。
        key_points: 关键信息点列表。
        potential_issues: 潜在问题列表。
    """

    model_config = ConfigDict(from_attributes=True)

    summary: str = Field(default="", description="一句话解释")
    key_points: list[str] = Field(default_factory=list, description="关键信息点")
    potential_issues: list[str] = Field(default_factory=list, description="潜在问题")
