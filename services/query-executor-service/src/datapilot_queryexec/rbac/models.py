"""RBAC 权限与脱敏数据模型。

定义权限规则、脱敏规则和 RBAC 检查结果的数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class OperationType(StrEnum):
    """SQL 操作类型枚举。"""

    READ = "read"
    EXPORT = "export"
    DDL = "ddl"
    WRITE = "write"


class PermissionRule(BaseModel):
    """用户权限规则。

    定义用户在指定租户下的操作权限、数据源访问范围、
    行级过滤条件、列级隐藏规则和行数限制。
    """

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    tenant_id: str
    role: str = "viewer"  # viewer / analyst / admin
    allowed_operations: list[OperationType] = Field(
        default_factory=lambda: [OperationType.READ]
    )
    allowed_datasources: list[str] = Field(default_factory=list)  # 空 = 全部
    row_filter_expression: str = ""  # 行级权限 WHERE 表达式（如 "department_id = 100"）
    hidden_columns: list[str] = Field(default_factory=list)  # 列级权限，隐藏的列
    max_rows: int = 10000  # 单次查询最大行数限制


class MaskRule(BaseModel):
    """脱敏规则。

    定义针对特定列的脱敏方式，支持正则匹配和多种脱敏策略。
    """

    model_config = ConfigDict(from_attributes=True)

    column_name: str  # 列名（支持通配符 *email*）
    mask_type: str = "partial"  # full / partial / hash / replace
    pattern: str = ""  # 正则匹配模式
    replacement: str = "***"  # 替换字符
    examples: list[str] = Field(default_factory=list)  # 示例格式


@dataclass
class RBACCheckResult:
    """RBAC 检查结果。

    包含权限检查是否通过、过滤后的 SQL、被处理的列信息等。
    """

    allowed: bool
    filtered_sql: str = ""  # 权限过滤后的 SQL
    masked_columns: list[str] = field(default_factory=list)
    removed_columns: list[str] = field(default_factory=list)
    injected_where: str = ""
    blocked_reason: str = ""
    max_rows: int = 10000
