"""Function Calling 协议数据模型。

定义 Function Calling 流程中使用的数据结构，包括工具调用请求、
工具调用结果和执行结果。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """单个工具调用。

    Attributes:
        id: 工具调用唯一标识，由 LLM 生成。
        name: 工具名称，对应 registry 中注册的工具。
        arguments: 工具参数，JSON 可序列化的字典。
    """

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class FunctionCallRequest:
    """Function Calling 请求。

    Attributes:
        user_message: 用户自然语言输入。
        tool_schemas: OpenAI function calling 格式的工具 schema 列表。
        context: 额外上下文信息，传递给工具执行过程。
        max_rounds: 最大工具调用轮次，防止无限循环。
        system_prompt: 自定义系统提示词，覆盖默认提示。
    """

    user_message: str
    tool_schemas: list[dict[str, Any]]
    context: dict[str, Any] | None = None
    max_rounds: int = 5
    system_prompt: str | None = None


@dataclass
class FunctionCallResult:
    """Function Calling 执行结果。

    Attributes:
        tool_calls: 执行过的所有工具调用记录。
        results: 每个工具调用的返回结果。
        final_message: LLM 最终生成的自然语言回答。
        total_time_ms: 整体执行耗时（毫秒）。
        errors: 执行过程中的错误信息列表。
        rounds_used: 实际使用的工具调用轮次数。
    """

    tool_calls: list[ToolCall] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)
    final_message: str = ""
    total_time_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    rounds_used: int = 0
