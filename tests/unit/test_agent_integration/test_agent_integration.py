"""Agent 集成模块单元测试。

覆盖 LLM 降级链（LLMFallbackChain）、响应缓存（ResponseCache）
和上下文增强器（ContextEnricher）的核心行为。
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from datapilot_agent.llm.llm_fallback import (
    FallbackReason,
    FallbackResult,
    LLMFallbackChain,
    ResponseCache,
)
from datapilot_agent.llm.context_enricher import ContextEnricher, EnrichedContext


# ============================================================
# 辅助工具
# ============================================================


async def _success_fn(prompt: str, **kwargs: Any) -> str:
    """模拟成功的 LLM 调用。"""
    return f"响应: {prompt}"


async def _fail_fn(prompt: str, **kwargs: Any) -> str:
    """模拟失败的 LLM 调用（抛出异常）。"""
    raise RuntimeError("模型服务不可用")


async def _empty_fn(prompt: str, **kwargs: Any) -> str:
    """模拟返回空响应的 LLM 调用。"""
    return ""


async def _circuit_open_fn(prompt: str, **kwargs: Any) -> str:
    """模拟熔断状态（抛出 CircuitBreakerOpen 异常）。"""
    raise Exception("Circuit breaker is open")


async def _rate_limit_fn(prompt: str, **kwargs: Any) -> str:
    """模拟限流（抛出 429 异常）。"""
    raise Exception("HTTP 429 Rate limit exceeded")


async def _context_too_long_fn(prompt: str, **kwargs: Any) -> str:
    """模拟上下文过长异常。"""
    raise Exception("Context window too long")


async def _slow_fn(prompt: str, **kwargs: Any) -> str:
    """模拟超时的 LLM 调用（永远不返回）。"""
    await asyncio.sleep(1000)
    return "不会返回"


# ============================================================
# LLMFallbackChain — add_provider / get_providers
# ============================================================


class TestLLMFallbackChainAddProvider:
    """测试 Provider 注册与排序。"""

    def test_add_single_provider(self) -> None:
        """添加单个 Provider，get_providers 返回正确列表。"""
        chain = LLMFallbackChain()
        chain.add_provider("deepseek", _success_fn, priority=0)

        providers = chain.get_providers()
        assert len(providers) == 1
        assert providers[0]["name"] == "deepseek"
        assert providers[0]["priority"] == 0

    def test_add_multiple_providers_sorted_by_priority(self) -> None:
        """多个 Provider 按 priority 升序排列。"""
        chain = LLMFallbackChain()
        chain.add_provider("qwen", _success_fn, priority=2)
        chain.add_provider("deepseek", _success_fn, priority=0)
        chain.add_provider("qwen-plus", _success_fn, priority=1)

        providers = chain.get_providers()
        names = [p["name"] for p in providers]
        assert names == ["deepseek", "qwen-plus", "qwen"]

    def test_add_provider_with_default_priority(self) -> None:
        """不指定 priority 时默认为 0。"""
        chain = LLMFallbackChain()
        chain.add_provider("default-priority", _success_fn)

        providers = chain.get_providers()
        assert providers[0]["priority"] == 0

    def test_add_provider_with_custom_timeout(self) -> None:
        """自定义超时时间正确存储。"""
        chain = LLMFallbackChain()
        chain.add_provider("slow-model", _success_fn, max_timeout=60.0)

        providers = chain.get_providers()
        assert providers[0]["max_timeout"] == 60.0

    def test_add_provider_returns_self_for_chaining(self) -> None:
        """add_provider 返回 self，支持链式调用。"""
        chain = LLMFallbackChain()
        result = chain.add_provider("a", _success_fn).add_provider("b", _success_fn)

        assert result is chain
        assert len(chain.get_providers()) == 2

    def test_get_providers_empty(self) -> None:
        """无 Provider 时 get_providers 返回空列表。"""
        chain = LLMFallbackChain()
        assert chain.get_providers() == []


# ============================================================
# LLMFallbackChain — set_default_response
# ============================================================


class TestLLMFallbackChainDefaultResponse:
    """测试默认降级响应设置。"""

    def test_set_default_response(self) -> None:
        """设置自定义默认响应。"""
        chain = LLMFallbackChain()
        chain.set_default_response("系统繁忙")
        assert chain._default_response == "系统繁忙"

    def test_default_response_initial_value(self) -> None:
        """默认降级响应的初始值。"""
        chain = LLMFallbackChain()
        assert "暂时无法处理" in chain._default_response


# ============================================================
# LLMFallbackChain — invoke 成功场景
# ============================================================


class TestLLMFallbackChainInvokeSuccess:
    """测试 invoke 成功路径。"""

    @pytest.mark.asyncio
    async def test_invoke_single_provider_success(self) -> None:
        """单个 Provider 成功调用。"""
        chain = LLMFallbackChain()
        chain.add_provider("deepseek", _success_fn, priority=0)

        result = await chain.invoke("你好")

        assert result.success is True
        assert result.content == "响应: 你好"
        assert result.used_fallback is False
        assert result.fallback_reason == ""
        assert result.errors == []
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_invoke_primary_succeeds_no_fallback(self) -> None:
        """主 Provider 成功时不标记 used_fallback。"""
        chain = LLMFallbackChain()
        chain.add_provider("primary", _success_fn, priority=0)

        result = await chain.invoke("查询数据")

        assert result.success is True
        assert result.used_fallback is False


# ============================================================
# LLMFallbackChain — invoke 超时场景
# ============================================================


class TestLLMFallbackChainInvokeTimeout:
    """测试 invoke 超时降级。"""

    @pytest.mark.asyncio
    async def test_invoke_timeout_falls_to_next_provider(self) -> None:
        """主 Provider 超时后降级到备用 Provider。"""
        chain = LLMFallbackChain()
        chain.add_provider("slow", _slow_fn, priority=0, max_timeout=0.01)
        chain.add_provider("fast", _success_fn, priority=1)

        result = await chain.invoke("测试超时")

        assert result.success is True
        assert result.content == "响应: 测试超时"
        assert result.used_fallback is True
        assert len(result.errors) > 0
        assert "超时" in result.errors[0]

    @pytest.mark.asyncio
    async def test_invoke_all_timeout_returns_default(self) -> None:
        """所有 Provider 都超时，返回默认响应。"""
        chain = LLMFallbackChain()
        chain.add_provider("slow1", _slow_fn, priority=0, max_timeout=0.01)
        chain.add_provider("slow2", _slow_fn, priority=1, max_timeout=0.01)
        chain.set_default_response("全部超时了")

        result = await chain.invoke("都会超时")

        assert result.success is False
        assert result.content == "全部超时了"
        assert result.used_fallback is True
        assert result.fallback_reason == "all_providers_failed"
        assert len(result.errors) >= 2


# ============================================================
# LLMFallbackChain — invoke 全部失败
# ============================================================


class TestLLMFallbackChainInvokeAllFail:
    """测试 invoke 所有 Provider 失败的场景。"""

    @pytest.mark.asyncio
    async def test_all_providers_exception_returns_default(self) -> None:
        """所有 Provider 抛异常，返回默认响应。"""
        chain = LLMFallbackChain()
        chain.add_provider("bad1", _fail_fn, priority=0)
        chain.add_provider("bad2", _fail_fn, priority=1)

        result = await chain.invoke("全失败")

        assert result.success is False
        assert result.used_fallback is True
        assert result.fallback_reason == "all_providers_failed"
        assert len(result.errors) >= 2

    @pytest.mark.asyncio
    async def test_all_providers_empty_response_returns_default(self) -> None:
        """所有 Provider 返回空响应，视为失败，返回默认响应。"""
        chain = LLMFallbackChain()
        chain.add_provider("empty1", _empty_fn, priority=0)
        chain.add_provider("empty2", _empty_fn, priority=1)

        result = await chain.invoke("空响应")

        assert result.success is False
        assert result.used_fallback is True
        assert result.fallback_reason == "all_providers_failed"

    @pytest.mark.asyncio
    async def test_empty_provider_list_returns_default(self) -> None:
        """无任何 Provider 注册时，直接返回默认响应。"""
        chain = LLMFallbackChain()

        result = await chain.invoke("没有 Provider")

        assert result.success is False
        assert result.used_fallback is True
        assert result.content == chain._default_response
        assert result.latency_ms >= 0


# ============================================================
# LLMFallbackChain — invoke 熔断场景
# ============================================================


class TestLLMFallbackChainInvokeCircuitOpen:
    """测试熔断降级场景。"""

    @pytest.mark.asyncio
    async def test_circuit_open_falls_to_next(self) -> None:
        """主 Provider 熔断，降级到备用 Provider。"""
        chain = LLMFallbackChain()
        chain.add_provider("circuit", _circuit_open_fn, priority=0)
        chain.add_provider("backup", _success_fn, priority=1)

        result = await chain.invoke("熔断测试")

        assert result.success is True
        assert result.used_fallback is True
        assert result.content == "响应: 熔断测试"

    @pytest.mark.asyncio
    async def test_all_circuit_open_returns_default(self) -> None:
        """所有 Provider 都熔断，返回默认响应。"""
        chain = LLMFallbackChain()
        chain.add_provider("c1", _circuit_open_fn, priority=0)
        chain.add_provider("c2", _circuit_open_fn, priority=1)

        result = await chain.invoke("全部熔断")

        assert result.success is False
        assert result.fallback_reason == "all_providers_failed"


# ============================================================
# LLMFallbackChain — invoke 多 Provider 部分成功
# ============================================================


class TestLLMFallbackChainInvokeMultiple:
    """测试多个 Provider 场景。"""

    @pytest.mark.asyncio
    async def test_second_provider_succeeds(self) -> None:
        """第一个 Provider 失败，第二个成功。"""
        chain = LLMFallbackChain()
        chain.add_provider("bad", _fail_fn, priority=0)
        chain.add_provider("good", _success_fn, priority=1)

        result = await chain.invoke("第二个成功")

        assert result.success is True
        assert result.content == "响应: 第二个成功"
        assert result.used_fallback is True

    @pytest.mark.asyncio
    async def test_rate_limit_falls_to_next(self) -> None:
        """主 Provider 限流，降级到备用。"""
        chain = LLMFallbackChain()
        chain.add_provider("limited", _rate_limit_fn, priority=0)
        chain.add_provider("backup", _success_fn, priority=1)

        result = await chain.invoke("限流测试")

        assert result.success is True
        assert result.used_fallback is True

    @pytest.mark.asyncio
    async def test_context_too_long_falls_to_next(self) -> None:
        """上下文过长时降级到备用 Provider。"""
        chain = LLMFallbackChain()
        chain.add_provider("limited-ctx", _context_too_long_fn, priority=0)
        chain.add_provider("backup", _success_fn, priority=1)

        result = await chain.invoke("很长的上下文")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_invoke_passes_kwargs_to_provider(self) -> None:
        """额外 kwargs 正确传递给 Provider。"""
        captured: dict[str, Any] = {}

        async def capture_fn(prompt: str, **kwargs: Any) -> str:
            captured.update(kwargs)
            return f"kwargs: {kwargs}"

        chain = LLMFallbackChain()
        chain.add_provider("capture", capture_fn, priority=0)

        result = await chain.invoke("测试", temperature=0.7, max_tokens=100)

        assert result.success is True
        assert captured.get("temperature") == 0.7
        assert captured.get("max_tokens") == 100

    @pytest.mark.asyncio
    async def test_invoke_with_retry(self) -> None:
        """max_retries > 1 时，Provider 被多次尝试。"""
        attempt_count = 0

        async def count_fn(prompt: str, **kwargs: Any) -> str:
            nonlocal attempt_count
            attempt_count += 1
            raise RuntimeError("仍然失败")

        chain = LLMFallbackChain()
        chain.add_provider("retryable", count_fn, priority=0)

        result = await chain.invoke("重试测试", max_retries=3)

        assert result.success is False
        assert attempt_count == 3


# ============================================================
# ResponseCache
# ============================================================


class TestResponseCache:
    """测试简单响应缓存。"""

    def test_get_miss(self) -> None:
        """缓存未命中返回 None。"""
        cache = ResponseCache()
        assert cache.get("不存在的 prompt") is None

    def test_set_and_get_hit(self) -> None:
        """set 后 get 命中，返回正确值。"""
        cache = ResponseCache()
        cache.set("prompt1", "response1")

        assert cache.get("prompt1") == "response1"

    def test_multiple_set_and_get(self) -> None:
        """多个条目的读写。"""
        cache = ResponseCache()
        cache.set("a", "响应A")
        cache.set("b", "响应B")
        cache.set("c", "响应C")

        assert cache.get("a") == "响应A"
        assert cache.get("b") == "响应B"
        assert cache.get("c") == "响应C"

    def test_lru_eviction_at_max_size(self) -> None:
        """缓存满后 LRU 淘汰最早的条目。"""
        cache = ResponseCache(max_size=3)
        cache.set("a", "1")
        cache.set("b", "2")
        cache.set("c", "3")
        # 缓存已满，再添加应淘汰 "a"
        cache.set("d", "4")

        assert cache.size == 3
        assert cache.get("a") is None  # 被淘汰
        assert cache.get("b") == "2"
        assert cache.get("c") == "3"
        assert cache.get("d") == "4"

    def test_lru_access_updates_order(self) -> None:
        """访问已存在的条目会更新 LRU 顺序。"""
        cache = ResponseCache(max_size=3)
        cache.set("a", "1")
        cache.set("b", "2")
        cache.set("c", "3")
        # 访问 "a"，使其成为最近使用
        _ = cache.get("a")
        # 现在应该淘汰 "b"（最久未使用）
        cache.set("d", "4")

        assert cache.get("a") == "1"
        assert cache.get("b") is None  # 被淘汰
        assert cache.get("c") == "3"
        assert cache.get("d") == "4"

    def test_set_existing_key_updates_value(self) -> None:
        """对已存在的 key 调用 set 会更新值。"""
        cache = ResponseCache()
        cache.set("k", "旧值")
        cache.set("k", "新值")

        assert cache.get("k") == "新值"
        assert cache.size == 1

    def test_set_existing_key_updates_lru_order(self) -> None:
        """更新已存在的 key 也会刷新 LRU 顺序。"""
        cache = ResponseCache(max_size=3)
        cache.set("a", "1")
        cache.set("b", "2")
        cache.set("c", "3")
        # 更新 "a"，使其成为最近使用
        cache.set("a", "新值1")
        # 淘汰 "b"
        cache.set("d", "4")

        assert cache.get("a") == "新值1"
        assert cache.get("b") is None

    def test_clear(self) -> None:
        """clear 清空所有缓存。"""
        cache = ResponseCache()
        cache.set("a", "1")
        cache.set("b", "2")
        cache.clear()

        assert cache.size == 0
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_size_property(self) -> None:
        """size 属性正确反映缓存大小。"""
        cache = ResponseCache()
        assert cache.size == 0

        cache.set("a", "1")
        assert cache.size == 1

        cache.set("b", "2")
        assert cache.size == 2

    def test_invalid_max_size_raises(self) -> None:
        """max_size < 1 时抛出 ValueError。"""
        with pytest.raises(ValueError, match="max_size"):
            ResponseCache(max_size=0)

        with pytest.raises(ValueError, match="max_size"):
            ResponseCache(max_size=-1)

    def test_get_updates_lru_order(self) -> None:
        """get 操作更新 LRU 访问顺序。"""
        cache = ResponseCache(max_size=2)
        cache.set("a", "1")
        cache.set("b", "2")
        # 访问 "a" 使其变为最近
        cache.get("a")
        # "b" 应该被淘汰
        cache.set("c", "3")

        assert cache.get("a") == "1"
        assert cache.get("b") is None
        assert cache.get("c") == "3"


# ============================================================
# ContextEnricher
# ============================================================


class TestContextEnricherBasic:
    """测试上下文增强器基本功能。"""

    def test_enrich_with_only_turns(self) -> None:
        """仅传入对话轮次，不注入额外内容。"""
        enricher = ContextEnricher()
        turns = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好，我是 DataPilot"},
        ]

        ctx = enricher.enrich(turns)

        assert len(ctx.messages) == 2
        assert ctx.messages[0] == {"role": "user", "content": "你好"}
        assert ctx.messages[1] == {"role": "assistant", "content": "你好，我是 DataPilot"}
        assert ctx.injected_memories == 0
        assert ctx.injected_tools == 0

    def test_enrich_with_system_prompt(self) -> None:
        """设置 system prompt 时，消息列表首条为 system。"""
        enricher = ContextEnricher(system_prompt="你是数据助手。")
        turns = [{"role": "user", "content": "查询销售额"}]

        ctx = enricher.enrich(turns)

        assert ctx.messages[0]["role"] == "system"
        assert ctx.messages[0]["content"] == "你是数据助手。"
        assert ctx.messages[1]["role"] == "user"

    def test_enrich_without_system_prompt(self) -> None:
        """未设置 system prompt 时不注入 system 消息。"""
        enricher = ContextEnricher()
        turns = [{"role": "user", "content": "你好"}]

        ctx = enricher.enrich(turns)

        assert all(m["role"] != "system" for m in ctx.messages)


class TestContextEnricherMemories:
    """测试记忆注入。"""

    def test_enrich_with_memories(self) -> None:
        """注入记忆上下文。"""
        enricher = ContextEnricher()
        memories = [
            {"key": "preferred_db", "value": "postgresql"},
            {"key": "schema", "value": "sales_db"},
        ]

        ctx = enricher.enrich([], memories=memories)

        assert ctx.injected_memories == 2
        # 记忆注入为 system 消息
        memory_msgs = [m for m in ctx.messages if "上下文信息" in m["content"]]
        assert len(memory_msgs) == 1
        assert "preferred_db" in memory_msgs[0]["content"]
        assert "sales_db" in memory_msgs[0]["content"]

    def test_enrich_with_empty_memories(self) -> None:
        """空记忆列表不注入。"""
        enricher = ContextEnricher()

        ctx = enricher.enrich([], memories=[])

        assert ctx.injected_memories == 0

    def test_enrich_with_none_memories(self) -> None:
        """memories 为 None 时不注入。"""
        enricher = ContextEnricher()

        ctx = enricher.enrich([], memories=None)

        assert ctx.injected_memories == 0


class TestContextEnricherTools:
    """测试工具定义统计。"""

    def test_enrich_with_tool_definitions(self) -> None:
        """传入工具定义时正确统计数量。"""
        enricher = ContextEnricher()
        tools = [
            {"name": "query_db", "description": "执行 SQL"},
            {"name": "list_tables", "description": "列出表"},
        ]

        ctx = enricher.enrich([], tool_definitions=tools)

        assert ctx.injected_tools == 2
        # 工具定义不在消息中
        tool_msgs = [m for m in ctx.messages if "query_db" in m["content"]]
        assert len(tool_msgs) == 0

    def test_enrich_without_tool_definitions(self) -> None:
        """不传工具定义时 injected_tools 为 0。"""
        enricher = ContextEnricher()

        ctx = enricher.enrich([], tool_definitions=None)

        assert ctx.injected_tools == 0


class TestContextEnricherTokenTruncation:
    """测试 token 窗口裁剪。"""

    def test_truncation_for_large_context(self) -> None:
        """超出 token 窗口时从最早的消息开始裁剪。"""
        # 设置一个很小的 max_context_tokens
        enricher = ContextEnricher(max_context_tokens=50)

        turns = [
            {"role": "user", "content": "这是一条很长的用户消息，用于测试token窗口裁剪功能是否正常工作"},
            {"role": "assistant", "content": "这是一条很长的助手回复，用于验证裁剪是否保留最新消息"},
            {"role": "user", "content": "最新问题"},
        ]

        ctx = enricher.enrich(turns)

        # 最后一条消息应该被保留
        assert ctx.messages[-1]["content"] == "最新问题"
        # 总 token 应该在限制内
        assert ctx.total_tokens <= 50

    def test_truncation_preserves_system_messages(self) -> None:
        """裁剪时始终保留 system 消息。"""
        enricher = ContextEnricher(
            system_prompt="你是助手",
            max_context_tokens=20,
        )
        turns = [
            {"role": "user", "content": "这条消息会很长因为我们需要测试裁剪功能是否会保留system消息而只裁剪普通消息这条消息足够长了"},
            {"role": "assistant", "content": "另一条很长的回复用于测试裁剪逻辑"},
        ]

        ctx = enricher.enrich(turns)

        system_msgs = [m for m in ctx.messages if m["role"] == "system"]
        assert len(system_msgs) >= 1
        assert system_msgs[0]["content"] == "你是助手"

    def test_truncation_keeps_latest_user_message(self) -> None:
        """裁剪后至少保留最后一条用户消息。"""
        enricher = ContextEnricher(max_context_tokens=10)
        turns = [
            {"role": "user", "content": "很旧的问题会被裁剪掉"},
            {"role": "user", "content": "新问题"},
        ]

        ctx = enricher.enrich(turns)

        # 最后一条用户消息应该被保留
        assert len(ctx.messages) >= 1
        assert ctx.messages[-1]["content"] == "新问题"


class TestContextEnricherEdgeCases:
    """测试边界情况。"""

    def test_empty_input(self) -> None:
        """空输入返回空消息列表。"""
        enricher = ContextEnricher()

        ctx = enricher.enrich([])

        assert ctx.messages == []
        assert ctx.total_tokens == 0
        assert ctx.injected_memories == 0
        assert ctx.injected_tools == 0

    def test_empty_content_turns_skipped(self) -> None:
        """空内容的对话轮次被跳过。"""
        enricher = ContextEnricher()
        turns = [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "有内容的回复"},
            {"role": "user", "content": ""},
        ]

        ctx = enricher.enrich(turns)

        # 只有有内容的轮次被保留
        assert len(ctx.messages) == 1
        assert ctx.messages[0]["content"] == "有内容的回复"

    def test_memory_with_missing_key_value(self) -> None:
        """记忆条目缺少 key 或 value 时仍然格式化。"""
        enricher = ContextEnricher()
        memories = [
            {"key": "", "value": "只有值"},
            {"key": "只有键", "value": ""},
            {"key": "both", "value": "两个都有"},
        ]

        ctx = enricher.enrich([], memories=memories)

        # key 或 value 非空即计入
        assert ctx.injected_memories == 3

    def test_token_estimation(self) -> None:
        """token 估算使用 len(text) // 2。"""
        enricher = ContextEnricher()

        assert enricher._estimate_tokens("") == 0
        assert enricher._estimate_tokens("ABCD") == 2
        assert enricher._estimate_tokens("ABCDEFG") == 3

    def test_full_enrichment(self) -> None:
        """完整的增强流程：system + memories + turns + tools。"""
        enricher = ContextEnricher(
            system_prompt="你是 DataPilot 助手",
            max_context_tokens=10000,
        )
        turns = [
            {"role": "user", "content": "查询销售数据"},
            {"role": "assistant", "content": "好的，请指定时间范围"},
        ]
        memories = [{"key": "default_schema", "value": "sales"}]
        tools = [{"name": "query_db"}]

        ctx = enricher.enrich(turns, memories=memories, tool_definitions=tools)

        # 验证顺序：system prompt → memory system → user → assistant
        assert ctx.messages[0]["role"] == "system"
        assert "DataPilot" in ctx.messages[0]["content"]
        assert ctx.messages[1]["role"] == "system"  # 记忆
        assert "default_schema" in ctx.messages[1]["content"]
        assert ctx.messages[2]["role"] == "user"
        assert ctx.messages[3]["role"] == "assistant"
        assert ctx.injected_memories == 1
        assert ctx.injected_tools == 1
        assert ctx.total_tokens > 0
