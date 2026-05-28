"""SQL 验证模块数据模型。

定义 Dry-run 预执行结果、成本预估结果和综合验证结果的 Pydantic 模型。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DryRunResult(BaseModel):
    """SQL Dry-run 预执行结果。

    Attributes:
        success: 预执行是否通过。
        error: 失败时的错误描述。
        checked_tables: 检查过的表名列表。
        warnings: 预执行过程中的警告信息。
    """

    model_config = ConfigDict(from_attributes=True)

    success: bool = False
    error: str = ""
    checked_tables: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CostEstimate(BaseModel):
    """SQL 成本预估结果。

    Attributes:
        estimated_rows: 预估影响行数。
        estimated_time_ms: 预估执行时间（毫秒）。
        cost_level: 成本等级，low / medium / high。
        explain_output: EXPLAIN 原始输出（用于调试）。
    """

    model_config = ConfigDict(from_attributes=True)

    estimated_rows: int = Field(default=0)
    estimated_time_ms: float = Field(default=0.0)
    cost_level: Literal["low", "medium", "high"] = Field(default="medium")
    explain_output: str = ""


class ValidationResult(BaseModel):
    """SQL 验证综合结果。

    汇总 AST 语法验证、Dry-run 预执行和成本预估的结果。

    Attributes:
        is_valid: 综合验证是否通过（所有步骤均无错误）。
        ast_valid: AST 语法验证是否通过。
        dryrun_passed: Dry-run 预执行是否通过。
        cost_estimate: 成本预估结果（可选）。
        errors: 所有验证步骤收集的错误信息。
        warnings: 所有验证步骤收集的警告信息。
    """

    model_config = ConfigDict(from_attributes=True)

    is_valid: bool = True
    ast_valid: bool = True
    dryrun_passed: bool = True
    cost_estimate: CostEstimate | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
