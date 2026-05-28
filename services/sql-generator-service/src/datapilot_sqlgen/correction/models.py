"""Self-Correction 数据模型。

定义错误分类枚举和纠错结果数据类，供 correction 包内所有模块共享，
避免循环导入。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ErrorCategory(StrEnum):
    """SQL 执行错误分类。"""

    SYNTAX_ERROR = "syntax_error"
    """SQL 语法错误。"""

    TABLE_NOT_FOUND = "table_not_found"
    """表不存在。"""

    COLUMN_NOT_FOUND = "column_not_found"
    """列不存在。"""

    EMPTY_RESULT = "empty_result"
    """结果为空（自定义标记，非数据库原生错误）。"""

    TIMEOUT = "timeout"
    """执行超时。"""

    OTHER = "other"
    """其他错误。"""


@dataclass
class CorrectionResult:
    """SQL 纠错结果。

    Attributes:
        success: 是否成功修正。
        corrected_sql: 修正后的 SQL（成功时为最终版本，失败时为最后一次尝试结果）。
        attempts: 总尝试轮次。
        error_category: 错误分类。
        original_error: 原始错误信息。
        corrections_history: 每轮纠错的 SQL 历史（用于调试和审计）。
    """

    success: bool
    corrected_sql: str
    attempts: int
    error_category: str
    original_error: str = ""
    corrections_history: list[str] = field(default_factory=list)
