"""上下文增强器。

为 Agent 对话注入系统提示、记忆上下文和工具定义。
将多种信息源组装为标准 LLM 消息列表，并进行 token 窗口管理。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class EnrichedContext:
    """增强后的上下文。

    Attributes:
        messages: 组装后的 LLM 消息列表。
            每个消息格式为 ``{"role": "system/user/assistant", "content": "..."}``。
        total_tokens: 估算的 token 总数。
        injected_memories: 注入的记忆条目数。
        injected_tools: 注入的工具定义数。
    """

    messages: list[dict[str, str]] = field(default_factory=list)
    total_tokens: int = 0
    injected_memories: int = 0
    injected_tools: int = 0


class ContextEnricher:
    """上下文增强器。

    将系统提示、对话历史、记忆和工具定义组装为 LLM 消息列表。
    支持按 token 窗口裁剪对话历史，保留 system 消息。

    Usage::

        enricher = ContextEnricher(
            system_prompt="你是 DataPilot 智能数据助手。",
            max_context_tokens=8000,
        )
        ctx = enricher.enrich(
            conversation_turns=[
                {"role": "user", "content": "查询上月销售额"},
                {"role": "assistant", "content": "SELECT SUM(amount) FROM sales ..."},
            ],
            memories=[{"key": "preferred_db", "value": "postgresql"}],
            tool_definitions=[{"name": "query_db", "description": "执行 SQL 查询"}],
        )
    """

    def __init__(
        self,
        system_prompt: str = "",
        max_context_tokens: int = 8000,
    ) -> None:
        """初始化上下文增强器。

        Args:
            system_prompt: 系统提示文本。为空时不注入 system 消息。
            max_context_tokens: 最大上下文 token 数（粗略估算）。
        """
        self._system_prompt = system_prompt
        self._max_tokens = max_context_tokens

    def enrich(
        self,
        conversation_turns: list[dict[str, str]],
        memories: list[dict[str, Any]] | None = None,
        tool_definitions: list[dict[str, Any]] | None = None,
    ) -> EnrichedContext:
        """构建增强上下文。

        组装顺序:
        1. system prompt（如果设置）
        2. 注入的记忆上下文（如果有）
        3. 对话历史（按时间顺序）
        4. 工具定义在调用 LLM 时单独传入（不占用上下文 token）

        Args:
            conversation_turns: 对话轮次列表。
                每个元素为 ``{"role": "user/assistant", "content": "..."}``。
            memories: 记忆条目列表。每个条目为包含 ``key`` 和 ``value`` 的字典。
            tool_definitions: 工具定义列表。仅用于统计注入数量。

        Returns:
            EnrichedContext 包含 messages 和统计信息。
        """
        messages: list[dict[str, str]] = []
        injected_memories = 0
        injected_tools = 0

        # 1. 注入系统提示
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})

        # 2. 注入记忆上下文
        memories = memories or []
        if memories:
            memory_lines: list[str] = []
            for mem in memories:
                key = mem.get("key", "")
                value = mem.get("value", "")
                if key or value:
                    memory_lines.append(f"- {key}: {value}")
                    injected_memories += 1

            if memory_lines:
                memory_text = "已知上下文信息：\n" + "\n".join(memory_lines)
                messages.append({"role": "system", "content": memory_text})

        # 3. 追加对话历史
        for turn in conversation_turns:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if content:  # 跳过空内容的轮次
                messages.append({"role": role, "content": content})

        # 4. 统计工具注入数（工具定义不在上下文中，仅统计）
        if tool_definitions is not None:
            injected_tools = len(tool_definitions)

        # 5. Token 裁剪
        messages = self._truncate_for_window(messages, self._max_tokens)

        # 6. 估算 token 总数
        total_tokens = sum(self._estimate_tokens(m["content"]) for m in messages)

        logger.debug(
            "上下文增强完成",
            message_count=len(messages),
            total_tokens=total_tokens,
            injected_memories=injected_memories,
            injected_tools=injected_tools,
        )

        return EnrichedContext(
            messages=messages,
            total_tokens=total_tokens,
            injected_memories=injected_memories,
            injected_tools=injected_tools,
        )

    def _estimate_tokens(self, text: str) -> int:
        """粗略估算 token 数。

        中文约 1 字 ≈ 1 token，英文约 4 字符 ≈ 1 token。
        这里使用简单的 len(text) // 2 作为折中估算。

        Args:
            text: 输入文本。

        Returns:
            估算的 token 数。
        """
        if not text:
            return 0
        return len(text) // 2

    def _truncate_for_window(
        self, messages: list[dict[str, str]], max_tokens: int
    ) -> list[dict[str, str]]:
        """从最早的对话开始裁剪。保留 system 消息。

        策略:
        1. 始终保留所有 system 消息
        2. 从最早的非 system 消息开始移除，直到总 token 数 <= max_tokens
        3. 确保至少保留最后一条用户消息（如果有）

        Args:
            messages: 原始消息列表。
            max_tokens: 最大允许 token 数。

        Returns:
            裁剪后的消息列表。
        """
        # 分离 system 消息和非 system 消息
        system_msgs: list[dict[str, str]] = []
        non_system_msgs: list[dict[str, str]] = []
        for msg in messages:
            if msg["role"] == "system":
                system_msgs.append(msg)
            else:
                non_system_msgs.append(msg)

        # 计算 system 消息占用的 token
        system_tokens = sum(self._estimate_tokens(m["content"]) for m in system_msgs)

        # 剩余可用 token
        remaining_tokens = max_tokens - system_tokens
        if remaining_tokens <= 0:
            # system 消息已超出限制，仍返回 system 消息
            return system_msgs

        # 从尾部开始保留非 system 消息，直到超出 token 预算
        kept: list[dict[str, str]] = []
        used_tokens = 0
        for msg in reversed(non_system_msgs):
            msg_tokens = self._estimate_tokens(msg["content"])
            if used_tokens + msg_tokens <= remaining_tokens:
                kept.append(msg)
                used_tokens += msg_tokens
            # 跳过超出的消息

        # 反转回正序
        kept.reverse()

        return system_msgs + kept
