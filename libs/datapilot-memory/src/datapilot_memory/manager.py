"""对话记忆管理器。

统一管理对话轮次、记忆存储和上下文构建。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from .context_window import ContextWindowManager
from .models import (
    ConversationContext,
    ConversationTurn,
    MemoryEntry,
    MemoryType,
)
from .store import MemoryStore
from .summarizer import ConversationSummarizer

logger = structlog.get_logger(__name__)


class MemoryManager:
    """对话记忆管理器。

    整合记忆存储、上下文窗口管理和对话摘要功能。
    """

    def __init__(
        self,
        store: MemoryStore | None = None,
        max_tokens: int = 8000,
    ) -> None:
        self._store = store or MemoryStore()
        self._context_window = ContextWindowManager(max_tokens=max_tokens)
        self._summarizer = ConversationSummarizer()
        # 会话对话轮次缓存：session_id -> [ConversationTurn]
        self._turns: dict[str, list[ConversationTurn]] = {}

    def add_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationTurn:
        """添加对话轮次。"""
        now = datetime.now(timezone.utc).isoformat()
        tokens = self._context_window.estimate_tokens(content)

        turn = ConversationTurn(
            role=role,
            content=content,
            timestamp=now,
            tokens=tokens,
            metadata=metadata or {},
        )

        self._turns.setdefault(session_id, []).append(turn)

        logger.debug(
            "添加对话轮次",
            session_id=session_id,
            role=role,
            tokens=tokens,
        )

        return turn

    def get_context(self, session_id: str, system_prompt: str = "") -> ConversationContext:
        """获取对话上下文。"""
        turns = self._turns.get(session_id, [])
        memories = self._store.list_by_session(session_id)

        total_tokens = sum(t.tokens for t in turns)
        # 加上 system_prompt 的 token 数
        if system_prompt:
            total_tokens += self._context_window.estimate_tokens(system_prompt)

        # 生成摘要
        summary = self._summarizer.summarize(turns) if turns else ""

        return ConversationContext(
            session_id=session_id,
            turns=list(turns),
            memories=memories,
            summary=summary,
            total_tokens=total_tokens,
            max_tokens=self._context_window.max_tokens,
        )

    def build_messages(
        self, session_id: str, system_prompt: str = ""
    ) -> list[dict]:
        """构建 LLM 消息列表。"""
        turns = self._turns.get(session_id, [])
        memories = self._store.list_by_session(session_id)

        return self._context_window.build_context(
            turns=turns,
            system_prompt=system_prompt,
            memories=memories,
        )

    def add_memory(
        self,
        session_id: str,
        content: str,
        memory_type: MemoryType = MemoryType.SHORT_TERM,
        summary: str = "",
        ttl_seconds: float = 3600.0,
    ) -> str:
        """添加记忆条目。"""
        now = datetime.now(timezone.utc)
        entry_id = str(uuid.uuid4())

        expires_at = ""
        if ttl_seconds > 0:
            from datetime import timedelta

            expires_dt = now + timedelta(seconds=ttl_seconds)
            expires_at = expires_dt.isoformat()

        entry = MemoryEntry(
            entry_id=entry_id,
            memory_type=memory_type,
            content=content,
            summary=summary,
            session_id=session_id,
            created_at=now.isoformat(),
            expires_at=expires_at,
            relevance_score=1.0,
            metadata={},
        )

        self._store.save(entry)

        logger.debug(
            "添加记忆条目",
            entry_id=entry_id,
            session_id=session_id,
            memory_type=memory_type.value,
        )

        return entry_id

    def search_memories(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """搜索记忆。"""
        return self._store.search(query, limit=limit)

    def summarize_conversation(self, session_id: str) -> str:
        """生成对话摘要。"""
        turns = self._turns.get(session_id, [])
        return self._summarizer.summarize(turns)

    def cleanup_expired(self) -> int:
        """清理过期记忆。"""
        count = self._store.cleanup_expired()
        if count > 0:
            logger.info("清理过期记忆", count=count)
        return count

    def clear_session(self, session_id: str) -> int:
        """清除会话的所有记忆和对话。"""
        # 清除对话轮次
        turn_count = len(self._turns.pop(session_id, []))
        # 清除记忆条目
        memory_count = self._store.clear(session_id)

        logger.info(
            "清除会话",
            session_id=session_id,
            turn_count=turn_count,
            memory_count=memory_count,
        )

        return turn_count + memory_count

    @property
    def store(self) -> MemoryStore:
        return self._store
