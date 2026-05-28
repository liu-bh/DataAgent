"""工具数据模型定义。"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class ToolCategory(str, enum.Enum):
    """工具类别枚举。"""

    SQL = "sql"
    PYTHON = "python"
    SEARCH = "search"
    ANALYSIS = "analysis"
    SYSTEM = "system"


@dataclass
class ToolParameter:
    """工具参数定义。"""

    name: str
    type: str  # string / integer / float / boolean / array / object
    description: str
    required: bool = True
    default: Any = None
    enum: list[str] | None = None
    minimum: float | None = None
    maximum: float | None = None


@dataclass
class ToolDefinition:
    """工具定义，描述工具的元信息。"""

    name: str
    description: str
    category: ToolCategory
    parameters: list[ToolParameter] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)
    version: str = "1.0.0"
    timeout_seconds: float = 30.0
    required_permissions: list[str] = field(default_factory=list)


@dataclass
class ToolExecutionResult:
    """工具执行结果。"""

    tool_name: str
    success: bool
    output: Any = None
    error: str = ""
    execution_time_ms: float = 0.0
