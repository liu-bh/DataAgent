"""上下文窗口管理。

控制 LLM 上下文大小，自动裁剪以适应 token 窗口。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ConversationTurn, MemoryEntry


class ContextWindowManager:
    """上下文窗口管理器。

    策略: system_prompt > 最新对话 > 重要记忆 > 早期对话
    """

    def __init__(self, max_tokens: int = 8000) -> None:
        self._max_tokens = max_tokens

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    def estimate_tokens(self, text: str) -> int:
        """估算文本 token 数。

        简化实现：len(text) // 2 作为粗略估算。
        中文约 1.5 字/token，英文约 4 字符/token，取中间值。
        """
        return len(text) // 2

    def build_context(
        self,
        turns: list[ConversationTurn],
        system_prompt: str = "",
        memories: list[MemoryEntry] | None = None,
    ) -> list[dict]:
        """构建上下文消息列表，自动裁剪。

        返回 [{"role": "system/user/assistant", "content": "..."}]

        优先级: system_prompt > 最新 2 轮对话 > 重要记忆 > 更多历史对话
        """
        memories = memories or []
        messages: list[dict] = []
        used_tokens = 0

        # 1. system_prompt（最高优先级）
        if system_prompt:
            sys_tokens = self.estimate_tokens(system_prompt)
            if used_tokens + sys_tokens > self._max_tokens:
                # system_prompt 放不下，至少保留截断版本
                truncated = system_prompt[: self._max_tokens * 2]
                messages.append({"role": "system", "content": truncated})
                used_tokens += self.estimate_tokens(truncated)
            else:
                messages.append({"role": "system", "content": system_prompt})
                used_tokens += sys_tokens

        # 2. 按优先级分割对话轮次
        # 最新 2 轮（即最新 2 条 user + 最新 2 条 assistant）
        recent_turns: list[ConversationTurn] = turns[-4:] if len(turns) > 4 else list(turns)
        older_turns: list[ConversationTurn] = turns[:-4] if len(turns) > 4 else []

        # 3. 添加最新对话（高优先级）
        remaining = self._max_tokens - used_tokens
        added_recent: list[dict] = []
        recent_used = 0
        for turn in recent_turns:
            turn_tokens = self.estimate_tokens(turn.content)
            if recent_used + turn_tokens <= remaining:
                added_recent.append({"role": turn.role, "content": turn.content})
                recent_used += turn_tokens
        messages.extend(added_recent)
        used_tokens += recent_used

        # 4. 添加重要记忆（按 relevance_score 降序）
        remaining = self._max_tokens - used_tokens
        sorted_memories = sorted(memories, key=lambda m: m.relevance_score, reverse=True)
        for mem in sorted_memories:
            mem_content = f"[记忆] {mem.content}"
            mem_tokens = self.estimate_tokens(mem_content)
            if remaining >= mem_tokens:
                messages.append({"role": "system", "content": mem_content})
                remaining -= mem_tokens
            else:
                break

        # 5. 添加更多早期对话（从新到旧）
        remaining = self._max_tokens - used_tokens
        for turn in reversed(older_turns):
            turn_tokens = self.estimate_tokens(turn.content)
            if remaining >= turn_tokens:
                messages.append({"role": turn.role, "content": turn.content})
                remaining -= turn_tokens
            else:
                break

        return messages

    def can_fit(self, turns: list[ConversationTurn], additional_tokens: int = 0) -> bool:
        """判断当前对话是否还有空间容纳更多 token。"""
        total = sum(self.estimate_tokens(t.content) for t in turns)
        return total + additional_tokens < self._max_tokens

    def truncate_turns(
        self, turns: list[ConversationTurn], max_tokens: int
    ) -> list[ConversationTurn]:
        """从最早的对话开始裁剪，保留最新的对话。

        如果 max_tokens 大于等于所有对话的总 token 数，返回全部。
        """
        if not turns:
            return []

        total = sum(self.estimate_tokens(t.content) for t in turns)
        if total <= max_tokens:
            return list(turns)

        # 从最早的开始移除，直到满足 token 限制
        result = list(turns)
        while result and sum(self.estimate_tokens(t.content) for t in result) > max_tokens:
            result.pop(0)

        return result
