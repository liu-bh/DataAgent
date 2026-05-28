"""对话记忆系统单元测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from datapilot_memory.context_window import ContextWindowManager
from datapilot_memory.manager import MemoryManager
from datapilot_memory.models import ConversationContext, ConversationTurn, MemoryEntry, MemoryType
from datapilot_memory.store import MemoryStore
from datapilot_memory.summarizer import ConversationSummarizer


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _make_turn(
    role: str = "user",
    content: str = "你好",
    timestamp: str = "",
    tokens: int = 0,
    metadata: dict | None = None,
) -> ConversationTurn:
    return ConversationTurn(
        role=role,
        content=content,
        timestamp=timestamp,
        tokens=tokens,
        metadata=metadata or {},
    )


def _make_entry(
    entry_id: str = "e1",
    memory_type: MemoryType = MemoryType.SHORT_TERM,
    content: str = "测试记忆",
    session_id: str = "s1",
    expires_at: str = "",
    relevance_score: float = 1.0,
) -> MemoryEntry:
    return MemoryEntry(
        entry_id=entry_id,
        memory_type=memory_type,
        content=content,
        session_id=session_id,
        expires_at=expires_at,
        relevance_score=relevance_score,
    )


# ---------------------------------------------------------------------------
# MemoryType 枚举
# ---------------------------------------------------------------------------


class TestMemoryType:
    """MemoryType 枚举测试。"""

    def test_values(self) -> None:
        assert MemoryType.EPHEMERAL == "ephemeral"
        assert MemoryType.SHORT_TERM == "short_term"
        assert MemoryType.LONG_TERM == "long_term"

    def test_enum_members_count(self) -> None:
        assert len(MemoryType) == 3


# ---------------------------------------------------------------------------
# ConversationTurn
# ---------------------------------------------------------------------------


class TestConversationTurn:
    """ConversationTurn 数据模型测试。"""

    def test_defaults(self) -> None:
        turn = ConversationTurn(role="user", content="hello")
        assert turn.role == "user"
        assert turn.content == "hello"
        assert turn.timestamp == ""
        assert turn.tokens == 0
        assert turn.metadata == {}

    def test_all_fields(self) -> None:
        turn = ConversationTurn(
            role="assistant",
            content="回复内容",
            timestamp="2025-01-01T00:00:00+00:00",
            tokens=10,
            metadata={"key": "value"},
        )
        assert turn.role == "assistant"
        assert turn.content == "回复内容"
        assert turn.timestamp == "2025-01-01T00:00:00+00:00"
        assert turn.tokens == 10
        assert turn.metadata == {"key": "value"}


# ---------------------------------------------------------------------------
# MemoryEntry
# ---------------------------------------------------------------------------


class TestMemoryEntry:
    """MemoryEntry 数据模型测试。"""

    def test_defaults(self) -> None:
        entry = MemoryEntry(
            entry_id="e1",
            memory_type=MemoryType.EPHEMERAL,
            content="内容",
        )
        assert entry.entry_id == "e1"
        assert entry.memory_type == MemoryType.EPHEMERAL
        assert entry.summary == ""
        assert entry.session_id == ""
        assert entry.created_at == ""
        assert entry.expires_at == ""
        assert entry.relevance_score == 0.0
        assert entry.metadata == {}

    def test_all_fields(self) -> None:
        entry = MemoryEntry(
            entry_id="e2",
            memory_type=MemoryType.LONG_TERM,
            content="重要内容",
            summary="摘要",
            session_id="s1",
            created_at="2025-01-01",
            expires_at="2026-01-01",
            relevance_score=0.95,
            metadata={"source": "manual"},
        )
        assert entry.entry_id == "e2"
        assert entry.memory_type == MemoryType.LONG_TERM
        assert entry.summary == "摘要"
        assert entry.session_id == "s1"
        assert entry.relevance_score == 0.95
        assert entry.metadata == {"source": "manual"}


# ---------------------------------------------------------------------------
# ConversationContext
# ---------------------------------------------------------------------------


class TestConversationContext:
    """ConversationContext 数据模型测试。"""

    def test_defaults(self) -> None:
        ctx = ConversationContext(session_id="s1")
        assert ctx.session_id == "s1"
        assert ctx.turns == []
        assert ctx.memories == []
        assert ctx.summary == ""
        assert ctx.total_tokens == 0
        assert ctx.max_tokens == 8000

    def test_custom_max_tokens(self) -> None:
        ctx = ConversationContext(session_id="s1", max_tokens=4000)
        assert ctx.max_tokens == 4000


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------


class TestMemoryStore:
    """MemoryStore 存储测试。"""

    def setup_method(self) -> None:
        self.store = MemoryStore()

    def test_save_and_get(self) -> None:
        entry = _make_entry(entry_id="e1", content="记忆内容", session_id="s1")
        self.store.save(entry)
        result = self.store.get("e1")
        assert result is not None
        assert result.content == "记忆内容"

    def test_get_nonexistent(self) -> None:
        assert self.store.get("nonexistent") is None

    def test_save_update(self) -> None:
        entry = _make_entry(entry_id="e1", content="旧内容")
        self.store.save(entry)
        updated = _make_entry(entry_id="e1", content="新内容")
        self.store.save(updated)
        result = self.store.get("e1")
        assert result is not None
        assert result.content == "新内容"

    def test_list_by_session(self) -> None:
        for i in range(5):
            entry = _make_entry(entry_id=f"e{i}", session_id="s1", content=f"记忆{i}")
            self.store.save(entry)
        # 不同会话
        other = _make_entry(entry_id="other", session_id="s2", content="其他")
        self.store.save(other)

        results = self.store.list_by_session("s1")
        assert len(results) == 5

    def test_list_by_session_limit(self) -> None:
        for i in range(10):
            entry = _make_entry(entry_id=f"e{i}", session_id="s1")
            self.store.save(entry)

        results = self.store.list_by_session("s1", limit=3)
        assert len(results) == 3

    def test_list_by_type(self) -> None:
        for i in range(3):
            entry = _make_entry(
                entry_id=f"st{i}",
                memory_type=MemoryType.SHORT_TERM,
                session_id="s1",
            )
            self.store.save(entry)
        for i in range(2):
            entry = _make_entry(
                entry_id=f"lt{i}",
                memory_type=MemoryType.LONG_TERM,
                session_id="s1",
            )
            self.store.save(entry)

        st_results = self.store.list_by_type(MemoryType.SHORT_TERM)
        assert len(st_results) == 3

        lt_results = self.store.list_by_type(MemoryType.LONG_TERM)
        assert len(lt_results) == 2

    def test_search_keywords(self) -> None:
        entry1 = _make_entry(entry_id="e1", content="销售数据查询", session_id="s1")
        entry2 = _make_entry(entry_id="e2", content="用户活跃度分析", session_id="s1")
        entry3 = _make_entry(entry_id="e3", content="库存盘点", session_id="s1")
        self.store.save(entry1)
        self.store.save(entry2)
        self.store.save(entry3)

        results = self.store.search("销售")
        assert len(results) >= 1
        assert any(r.entry_id == "e1" for r in results)

    def test_search_empty_query(self) -> None:
        entry = _make_entry(entry_id="e1")
        self.store.save(entry)
        assert self.store.search("") == []
        assert self.store.search("   ") == []

    def test_search_limit(self) -> None:
        for i in range(10):
            entry = _make_entry(
                entry_id=f"e{i}",
                content=f"测试查询{i}",
                session_id="s1",
            )
            self.store.save(entry)

        results = self.store.search("测试")
        assert len(results) <= 5  # 默认 limit=5

    def test_delete(self) -> None:
        entry = _make_entry(entry_id="e1", session_id="s1")
        self.store.save(entry)
        assert self.store.delete("e1") is True
        assert self.store.get("e1") is None
        assert self.store.count("s1") == 0

    def test_delete_nonexistent(self) -> None:
        assert self.store.delete("nonexistent") is False

    def test_cleanup_expired(self) -> None:
        # 一个已过期的条目
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        expired_entry = _make_entry(entry_id="expired", expires_at=past, session_id="s1")
        self.store.save(expired_entry)

        # 一个未过期的条目
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        valid_entry = _make_entry(entry_id="valid", expires_at=future, session_id="s1")
        self.store.save(valid_entry)

        # 一个没有过期时间的条目
        no_expiry = _make_entry(entry_id="no_exp", session_id="s1")
        self.store.save(no_expiry)

        cleaned = self.store.cleanup_expired()
        assert cleaned == 1
        assert self.store.get("expired") is None
        assert self.store.get("valid") is not None
        assert self.store.get("no_exp") is not None

    def test_clear_session(self) -> None:
        for i in range(3):
            entry = _make_entry(entry_id=f"s1_e{i}", session_id="s1")
            self.store.save(entry)
        other = _make_entry(entry_id="s2_e1", session_id="s2")
        self.store.save(other)

        cleared = self.store.clear("s1")
        assert cleared == 3
        assert self.store.count("s1") == 0
        assert self.store.count("s2") == 1

    def test_clear_all(self) -> None:
        for i in range(5):
            entry = _make_entry(entry_id=f"e{i}", session_id="s1")
            self.store.save(entry)

        cleared = self.store.clear()
        assert cleared == 5
        assert self.store.count() == 0

    def test_count(self) -> None:
        assert self.store.count() == 0
        for i in range(4):
            entry = _make_entry(entry_id=f"e{i}", session_id="s1")
            self.store.save(entry)
        assert self.store.count() == 4
        assert self.store.count("s1") == 4
        assert self.store.count("s2") == 0

    def test_list_by_session_sorted_by_relevance(self) -> None:
        e1 = _make_entry(entry_id="e1", session_id="s1", relevance_score=0.5)
        e2 = _make_entry(entry_id="e2", session_id="s1", relevance_score=0.9)
        e3 = _make_entry(entry_id="e3", session_id="s1", relevance_score=0.3)
        self.store.save(e1)
        self.store.save(e2)
        self.store.save(e3)

        results = self.store.list_by_session("s1")
        assert results[0].entry_id == "e2"
        assert results[1].entry_id == "e1"
        assert results[2].entry_id == "e3"


# ---------------------------------------------------------------------------
# ContextWindowManager
# ---------------------------------------------------------------------------


class TestContextWindowManager:
    """ContextWindowManager 上下文窗口测试。"""

    def setup_method(self) -> None:
        self.mgr = ContextWindowManager(max_tokens=100)

    def test_max_tokens_property(self) -> None:
        assert self.mgr.max_tokens == 100

    def test_estimate_tokens(self) -> None:
        # "hello" = 5 chars => 5 // 2 = 2
        assert self.mgr.estimate_tokens("hello") == 2
        # 空字符串
        assert self.mgr.estimate_tokens("") == 0
        # 中文 6 字 => 6 // 2 = 3
        assert self.mgr.estimate_tokens("你好世界") == 2

    def test_build_context_with_system_prompt(self) -> None:
        messages = self.mgr.build_context([], system_prompt="你是一个助手。")
        assert len(messages) == 1
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "你是一个助手。"

    def test_build_context_with_turns(self) -> None:
        turns = [
            _make_turn(role="user", content="你好"),
            _make_turn(role="assistant", content="你好！有什么可以帮你？"),
        ]
        messages = self.mgr.build_context(turns)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_build_context_with_memories(self) -> None:
        turns = [_make_turn(role="user", content="查询销售")]
        mem = _make_entry(content="用户偏好销售数据", relevance_score=0.9)
        messages = self.mgr.build_context(turns, memories=[mem])
        # 应包含记忆消息
        roles = [m["role"] for m in messages]
        assert "user" in roles
        assert "system" in roles  # 记忆以 system 角色注入

    def test_build_context_truncation(self) -> None:
        # 使用很小的 max_tokens，验证裁剪
        small_mgr = ContextWindowManager(max_tokens=10)
        turns = [
            _make_turn(role="user", content="第一个问题"),
            _make_turn(role="assistant", content="第一个回答"),
            _make_turn(role="user", content="第二个问题"),
            _make_turn(role="assistant", content="第二个回答"),
            _make_turn(role="user", content="第三个问题"),
            _make_turn(role="assistant", content="第三个回答"),
        ]
        messages = small_mgr.build_context(turns)
        # 所有消息的 token 数应不超过 max_tokens（大致）
        total = sum(small_mgr.estimate_tokens(m["content"]) for m in messages)
        assert total <= small_mgr.max_tokens + 50  # 允许少量误差

    def test_can_fit_true(self) -> None:
        turns = [_make_turn(content="短")]
        assert self.mgr.can_fit(turns, additional_tokens=50) is True

    def test_can_fit_false(self) -> None:
        # 一个很长的内容超过 max_tokens
        long_content = "x" * 300  # 估算 150 tokens > 100
        turns = [_make_turn(content=long_content)]
        assert self.mgr.can_fit(turns, additional_tokens=0) is False

    def test_truncate_turns_no_truncation(self) -> None:
        turns = [
            _make_turn(content="A"),
            _make_turn(content="B"),
        ]
        result = self.mgr.truncate_turns(turns, max_tokens=100)
        assert len(result) == 2

    def test_truncate_turns_removes_oldest(self) -> None:
        turns = [
            _make_turn(role="user", content="旧的对话内容比较长一点"),
            _make_turn(role="assistant", content="旧的助手回复也比较长"),
            _make_turn(role="user", content="新问题"),
            _make_turn(role="assistant", content="新回复"),
        ]
        result = self.mgr.truncate_turns(turns, max_tokens=4)
        # 应保留最新的对话
        assert len(result) < len(turns)
        # 最后一条应该保留
        assert result[-1].content == "新回复"


# ---------------------------------------------------------------------------
# ConversationSummarizer
# ---------------------------------------------------------------------------


class TestConversationSummarizer:
    """ConversationSummarizer 摘要测试。"""

    def setup_method(self) -> None:
        self.summarizer = ConversationSummarizer()

    def test_summarize_empty(self) -> None:
        result = self.summarizer.summarize([])
        assert "暂无对话记录" in result

    def test_summarize_with_user_and_assistant(self) -> None:
        turns = [
            _make_turn(role="user", content="查询销售数据"),
            _make_turn(role="assistant", content="好的，以下是销售数据：总销售额100万。"),
        ]
        result = self.summarizer.summarize(turns)
        assert "2 轮" in result
        assert "查询销售数据" in result
        assert "100万" in result

    def test_summarize_only_user(self) -> None:
        turns = [
            _make_turn(role="user", content="你好"),
        ]
        result = self.summarizer.summarize(turns)
        assert "1 轮" in result
        assert "你好" in result

    def test_extract_key_questions(self) -> None:
        turns = [
            _make_turn(role="user", content="第一个问题"),
            _make_turn(role="assistant", content="回答一"),
            _make_turn(role="user", content="第二个问题"),
        ]
        questions = self.summarizer.extract_key_questions(turns)
        assert len(questions) == 2
        assert questions[0] == "第一个问题"
        assert questions[1] == "第二个问题"

    def test_extract_key_questions_empty_user(self) -> None:
        turns = [
            _make_turn(role="assistant", content="自动回复"),
        ]
        questions = self.summarizer.extract_key_questions(turns)
        assert questions == []

    def test_extract_key_questions_truncates_long(self) -> None:
        long_question = "x" * 100
        turns = [
            _make_turn(role="user", content=long_question),
        ]
        questions = self.summarizer.extract_key_questions(turns)
        assert len(questions) == 1
        assert len(questions[0]) <= 83  # 80 + "..."
        assert questions[0].endswith("...")

    def test_format_summary_without_last_response(self) -> None:
        result = self.summarizer.summarize(
            [_make_turn(role="user", content="问题")]
        )
        assert "最近助手回复摘要" not in result


# ---------------------------------------------------------------------------
# MemoryManager
# ---------------------------------------------------------------------------


class TestMemoryManager:
    """MemoryManager 集成测试。"""

    def setup_method(self) -> None:
        self.manager = MemoryManager(max_tokens=8000)

    def test_add_turn(self) -> None:
        turn = self.manager.add_turn("s1", "user", "你好")
        assert turn.role == "user"
        assert turn.content == "你好"
        assert turn.timestamp != ""
        assert turn.tokens > 0

    def test_get_context_empty(self) -> None:
        ctx = self.manager.get_context("s1")
        assert ctx.session_id == "s1"
        assert ctx.turns == []
        assert ctx.memories == []

    def test_get_context_with_turns(self) -> None:
        self.manager.add_turn("s1", "user", "问题一")
        self.manager.add_turn("s1", "assistant", "回答一")
        ctx = self.manager.get_context("s1")
        assert len(ctx.turns) == 2
        assert ctx.summary != ""
        assert ctx.total_tokens > 0

    def test_build_messages_empty(self) -> None:
        messages = self.manager.build_messages("s1")
        assert messages == []

    def test_build_messages_with_system_prompt(self) -> None:
        self.manager.add_turn("s1", "user", "你好")
        messages = self.manager.build_messages("s1", system_prompt="你是助手。")
        assert len(messages) >= 2
        assert messages[0]["role"] == "system"

    def test_add_memory(self) -> None:
        entry_id = self.manager.add_memory(
            session_id="s1",
            content="重要信息",
            memory_type=MemoryType.LONG_TERM,
            ttl_seconds=7200,
        )
        assert entry_id != ""
        # 验证可以从 store 中获取
        entry = self.manager.store.get(entry_id)
        assert entry is not None
        assert entry.content == "重要信息"
        assert entry.memory_type == MemoryType.LONG_TERM
        assert entry.expires_at != ""

    def test_add_memory_default_type(self) -> None:
        entry_id = self.manager.add_memory(session_id="s1", content="临时信息")
        entry = self.manager.store.get(entry_id)
        assert entry is not None
        assert entry.memory_type == MemoryType.SHORT_TERM

    def test_search_memories(self) -> None:
        self.manager.add_memory(session_id="s1", content="销售报表数据")
        self.manager.add_memory(session_id="s1", content="用户画像分析")
        results = self.manager.search_memories("销售")
        assert len(results) >= 1
        assert any("销售" in r.content for r in results)

    def test_summarize_conversation(self) -> None:
        self.manager.add_turn("s1", "user", "查询数据")
        self.manager.add_turn("s1", "assistant", "结果是...")
        summary = self.manager.summarize_conversation("s1")
        assert "2 轮" in summary

    def test_cleanup_expired(self) -> None:
        # 手动添加一个已过期的条目
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        expired = _make_entry(
            entry_id="exp",
            session_id="s1",
            expires_at=past,
        )
        self.manager.store.save(expired)

        cleaned = self.manager.cleanup_expired()
        assert cleaned == 1
        assert self.manager.store.get("exp") is None

    def test_cleanup_no_expired(self) -> None:
        self.manager.add_memory(session_id="s1", content="有效记忆", ttl_seconds=3600)
        cleaned = self.manager.cleanup_expired()
        assert cleaned == 0

    def test_clear_session(self) -> None:
        self.manager.add_turn("s1", "user", "问题")
        self.manager.add_memory(session_id="s1", content="记忆")
        cleared = self.manager.clear_session("s1")
        assert cleared == 2
        ctx = self.manager.get_context("s1")
        assert ctx.turns == []
        assert ctx.memories == []

    def test_store_property(self) -> None:
        assert isinstance(self.manager.store, MemoryStore)

    def test_multiple_sessions_isolated(self) -> None:
        self.manager.add_turn("s1", "user", "会话1")
        self.manager.add_turn("s2", "user", "会话2")
        ctx1 = self.manager.get_context("s1")
        ctx2 = self.manager.get_context("s2")
        assert len(ctx1.turns) == 1
        assert ctx1.turns[0].content == "会话1"
        assert len(ctx2.turns) == 1
        assert ctx2.turns[0].content == "会话2"

    def test_build_messages_includes_memories(self) -> None:
        self.manager.add_turn("s1", "user", "查询")
        # 手动添加带高 relevance_score 的记忆条目
        mem = _make_entry(content="偏好SQL查询", session_id="s1", relevance_score=0.9)
        self.manager.store.save(mem)
        messages = self.manager.build_messages("s1")
        # 至少包含 user 消息和记忆消息
        contents = [m["content"] for m in messages]
        assert any("查询" in c for c in contents)
        assert any("偏好" in c for c in contents)
