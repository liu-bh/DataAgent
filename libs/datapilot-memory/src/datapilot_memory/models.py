"""对话记忆数据模型定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MemoryType(StrEnum):
    """记忆类型枚举。"""

    EPHEMERAL = "ephemeral"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"


@dataclass
class ConversationTurn:
    """单轮对话记录。"""

    role: str  # "user" / "assistant" / "system"
    content: str
    timestamp: str = ""
    tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryEntry:
    """记忆条目。"""

    entry_id: str
    memory_type: MemoryType
    content: str
    summary: str = ""
    session_id: str = ""
    created_at: str = ""
    expires_at: str = ""
    relevance_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationContext:
    """对话上下文。"""

    session_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    memories: list[MemoryEntry] = field(default_factory=list)
    summary: str = ""
    total_tokens: int = 0
    max_tokens: int = 8000
