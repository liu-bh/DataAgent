"""LLM 调用降级策略。

当主 LLM 调用失败时，提供降级方案确保系统可用性。
支持多 Provider 优先级链、超时控制、熔断和默认降级响应。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)


class FallbackReason(StrEnum):
    """降级原因枚举。"""

    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    MODEL_ERROR = "model_error"
    CIRCUIT_OPEN = "circuit_open"
    CONTEXT_TOO_LONG = "context_too_long"


@dataclass
class FallbackResult:
    """降级执行结果。

    Attributes:
        success: 是否成功获得有效响应。
        content: 响应内容。
        used_fallback: 是否使用了降级 Provider 或默认响应。
        fallback_reason: 触发降级的原因，为空表示未降级。
        latency_ms: 调用总耗时（毫秒）。
        errors: 过程中收集的错误信息列表。
    """

    success: bool
    content: str = ""
    used_fallback: bool = False
    fallback_reason: str = ""
    latency_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


class LLMFallbackChain:
    """LLM 降级链。

    按优先级尝试多个 LLM Provider，失败时自动降级到下一个。
    当所有 LLM 都失败时，返回预设的降级响应。

    Usage::

        chain = LLMFallbackChain()
        chain.add_provider("deepseek", call_deepseek, priority=0)
        chain.add_provider("qwen", call_qwen, priority=1)
        chain.set_default_response("抱歉，系统繁忙，请稍后重试。")
        result = await chain.invoke("查询销售额")
    """

    def __init__(self) -> None:
        self._providers: list[dict[str, Any]] = []
        self._default_response: str = "抱歉，我暂时无法处理您的请求，请稍后重试。"

    def add_provider(
        self,
        name: str,
        call_fn: Callable,
        priority: int = 0,
        max_timeout: float = 30.0,
    ) -> LLMFallbackChain:
        """添加 LLM Provider。

        Args:
            name: Provider 名称。
            call_fn: 调用函数，签名 ``async def(prompt: str, **kwargs) -> str``。
            priority: 优先级，数值越小优先级越高。
            max_timeout: 超时时间（秒）。

        Returns:
            self，支持链式调用。
        """
        self._providers.append(
            {
                "name": name,
                "call_fn": call_fn,
                "priority": priority,
                "max_timeout": max_timeout,
            }
        )
        logger.debug("添加 LLM Provider", name=name, priority=priority, timeout=max_timeout)
        return self

    def set_default_response(self, response: str) -> None:
        """设置默认降级响应。

        Args:
            response: 所有 Provider 均失败时返回的文本。
        """
        self._default_response = response
        logger.debug("设置默认降级响应", response=response[:50])

    async def invoke(
        self,
        prompt: str,
        max_retries: int = 1,
        **kwargs: Any,
    ) -> FallbackResult:
        """按优先级调用 LLM Provider 链。

        流程:
        1. 按优先级排序 Provider
        2. 依次尝试调用，超时或异常时跳到下一个
        3. 所有 Provider 失败时返回默认降级响应

        Args:
            prompt: 用户输入的提示文本。
            max_retries: 每个 Provider 的最大重试次数。
            **kwargs: 传递给 Provider 调用函数的额外参数。

        Returns:
            FallbackResult 包含响应内容和执行统计。
        """
        start_time = time.perf_counter()
        errors: list[str] = []
        sorted_providers = self.get_providers()

        for provider in sorted_providers:
            provider_name = provider["name"]
            max_timeout = provider["max_timeout"]

            for attempt in range(1, max_retries + 1):
                try:
                    content, reason = await asyncio.wait_for(
                        self._try_provider(provider, prompt, **kwargs),
                        timeout=max_timeout,
                    )
                    if not reason:
                        # 调用成功
                        elapsed = (time.perf_counter() - start_time) * 1000
                        is_fallback = provider["priority"] > sorted_providers[0]["priority"]
                        logger.info(
                            "LLM 调用成功",
                            provider=provider_name,
                            priority=provider["priority"],
                            is_fallback=is_fallback,
                            attempt=attempt,
                            latency_ms=round(elapsed, 2),
                        )
                        return FallbackResult(
                            success=True,
                            content=content,
                            used_fallback=is_fallback,
                            fallback_reason="" if not is_fallback else "primary_failed",
                            latency_ms=round(elapsed, 2),
                            errors=errors,
                        )
                    # Provider 返回了降级原因（如熔断）
                    reason_str = f"{provider_name}: {reason} (尝试 {attempt})"
                    errors.append(reason_str)
                    logger.warning(
                        "Provider 返回降级原因",
                        provider=provider_name,
                        reason=reason,
                        attempt=attempt,
                    )
                except TimeoutError:
                    reason_str = f"{provider_name}: 超时 ({max_timeout}s, 尝试 {attempt})"
                    errors.append(reason_str)
                    logger.warning(
                        "Provider 调用超时",
                        provider=provider_name,
                        timeout=max_timeout,
                        attempt=attempt,
                    )
                except Exception as exc:
                    reason_str = f"{provider_name}: {type(exc).__name__}: {exc} (尝试 {attempt})"
                    errors.append(reason_str)
                    logger.error(
                        "Provider 调用异常",
                        provider=provider_name,
                        error=str(exc),
                        attempt=attempt,
                    )

            # 当前 Provider 所有重试均失败，尝试下一个
            logger.warning(
                "Provider 所有重试失败，切换下一个",
                provider=provider_name,
                total_errors=len(errors),
            )

        # 所有 Provider 均失败，返回默认降级响应
        elapsed = (time.perf_counter() - start_time) * 1000
        logger.error(
            "所有 LLM Provider 调用失败，返回默认降级响应",
            total_errors=len(errors),
            latency_ms=round(elapsed, 2),
        )
        return FallbackResult(
            success=False,
            content=self._default_response,
            used_fallback=True,
            fallback_reason="all_providers_failed",
            latency_ms=round(elapsed, 2),
            errors=errors,
        )

    async def _try_provider(
        self, provider: dict[str, Any], prompt: str, **kwargs: Any
    ) -> tuple[str, str]:
        """尝试调用单个 Provider。

        Args:
            provider: Provider 配置字典。
            prompt: 提示文本。
            **kwargs: 额外参数。

        Returns:
            元组 (content, reason)。
            reason 为空字符串表示调用成功；
            reason 非空表示该 Provider 触发了降级（如熔断、上下文过长等）。
        """
        call_fn: Callable = provider["call_fn"]
        try:
            result = await call_fn(prompt, **kwargs)
            # 如果 call_fn 返回 None 或空字符串，视为失败
            if not result:
                return ("", "empty_response")
            return (str(result), "")
        except Exception as exc:
            # 将已知异常类型映射为降级原因
            exc_name = type(exc).__name__
            if "Timeout" in exc_name or "timeout" in exc_name.lower():
                return ("", FallbackReason.TIMEOUT)
            if "RateLimit" in exc_name or "429" in str(exc):
                return ("", FallbackReason.RATE_LIMIT)
            if "Circuit" in exc_name or "breaker" in exc_name.lower():
                return ("", FallbackReason.CIRCUIT_OPEN)
            if "Context" in exc_name and "long" in str(exc).lower():
                return ("", FallbackReason.CONTEXT_TOO_LONG)
            # 未知异常，抛出让上层 invoke 处理
            raise

    def get_providers(self) -> list[dict[str, Any]]:
        """获取已注册的 Provider 列表（按优先级排序）。

        Returns:
            按优先级升序排列的 Provider 配置列表。
        """
        return sorted(self._providers, key=lambda p: p["priority"])


class ResponseCache:
    """简单响应缓存。

    缓存最近的 LLM 响应，当降级发生时尝试返回缓存结果。
    使用 LRU 策略，当缓存满时淘汰最早访问的条目。

    Attributes:
        max_size: 缓存最大条目数。
        size: 当前缓存条目数。
    """

    def __init__(self, max_size: int = 100) -> None:
        if max_size < 1:
            raise ValueError(f"max_size 必须 >= 1，收到 {max_size}")
        self._cache: dict[str, str] = {}
        self._access_order: list[str] = []
        self._max_size = max_size

    def get(self, prompt: str) -> str | None:
        """获取缓存的响应。

        命中时会更新访问顺序（LRU）。

        Args:
            prompt: 提示文本，作为缓存键。

        Returns:
            缓存的响应内容，未命中时返回 None。
        """
        if prompt in self._cache:
            # 更新 LRU 顺序：移到末尾
            self._access_order.remove(prompt)
            self._access_order.append(prompt)
            return self._cache[prompt]
        return None

    def set(self, prompt: str, response: str) -> None:
        """缓存响应。

        如果缓存已满，淘汰最早访问的条目。

        Args:
            prompt: 提示文本，作为缓存键。
            response: 要缓存的响应内容。
        """
        if prompt in self._cache:
            # 已存在则更新值和访问顺序
            self._access_order.remove(prompt)
            self._access_order.append(prompt)
            self._cache[prompt] = response
            return

        # 缓存已满，淘汰最早的条目
        if len(self._cache) >= self._max_size:
            oldest_key = self._access_order.pop(0)
            del self._cache[oldest_key]
            logger.debug("缓存淘汰", evicted_key=oldest_key[:50])

        self._cache[prompt] = response
        self._access_order.append(prompt)

    def clear(self) -> None:
        """清空缓存。"""
        self._cache.clear()
        self._access_order.clear()

    @property
    def size(self) -> int:
        """当前缓存条目数。"""
        return len(self._cache)
