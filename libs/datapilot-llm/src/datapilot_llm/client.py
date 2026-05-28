"""OpenAI 兼容 API 客户端。

封装 httpx.AsyncClient，实现 /v1/chat/completions 的非流式和流式调用。
支持 JSON mode、超时控制、指数退避重试、自动 token 消耗和成本计算。
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class LLMError(Exception):
    """LLM 调用异常。

    Attributes:
        status_code: HTTP 状态码，网络错误时为 0。
        message: 错误描述。
        model: 调用的模型标识符。
        retryable: 是否可重试。
    """

    def __init__(
        self,
        message: str = "LLM 调用失败",
        status_code: int = 0,
        model: str = "",
        retryable: bool = False,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.model = model
        self.retryable = retryable
        super().__init__(self.message)


@dataclass
class TokenUsage:
    """Token 使用统计。

    Attributes:
        prompt_tokens: 输入 token 数。
        completion_tokens: 输出 token 数。
    """

    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        """总 token 数。"""
        return self.prompt_tokens + self.completion_tokens


class OpenAICompatibleClient:
    """OpenAI 兼容 API 异步客户端。

    支持 OpenAI Chat Completions API 协议，兼容 Qwen、DeepSeek 等提供商。

    Args:
        api_key: API 密钥。
        api_base: API 基础地址，如 https://api.deepseek.com/v1。
        timeout: 请求超时秒数。
        max_retries: 最大重试次数（仅 5xx 和网络错误）。
        cost_per_million_input: 输入 token 单价（元/百万 token）。
        cost_per_million_output: 输出 token 单价（元/百万 token）。
    """

    def __init__(
        self,
        api_key: str,
        api_base: str,
        timeout: int = 60,
        max_retries: int = 3,
        cost_per_million_input: float = 1.0,
        cost_per_million_output: float = 1.0,
    ) -> None:
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._cost_per_million_input = cost_per_million_input
        self._cost_per_million_output = cost_per_million_output
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 httpx 客户端（惰性初始化）。"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._api_base,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self._timeout, connect=10.0),
            )
        return self._client

    def _build_messages(
        self,
        prompt: str,
        system: str | None = None,
    ) -> list[dict[str, str]]:
        """构建 OpenAI 格式的消息列表。"""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _calculate_cost(self, usage: TokenUsage) -> float:
        """根据 token 消耗计算调用成本（元）。"""
        input_cost = (usage.prompt_tokens / 1_000_000) * self._cost_per_million_input
        output_cost = (usage.completion_tokens / 1_000_000) * self._cost_per_million_output
        return input_cost + output_cost

    @staticmethod
    def _is_retryable(status_code: int) -> bool:
        """判断 HTTP 状态码是否可重试。

        仅 5xx 服务端错误和 429 限流错误可重试，
        4xx 客户端错误不重试（429 除外）。
        """
        return status_code >= 500 or status_code == 429

    def _parse_usage(self, data: dict[str, Any]) -> TokenUsage:
        """从 API 响应中解析 token 使用量。"""
        usage_data = data.get("usage", {})
        return TokenUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
        )

    async def chat_completion(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        """非流式 Chat Completion 调用。

        Args:
            model: 模型标识符。
            prompt: 用户提示词。
            system: 系统提示词。
            temperature: 采样温度。
            max_tokens: 最大生成 token 数。
            stop: 停止序列列表。
            json_mode: 是否启用 JSON mode。

        Returns:
            包含 content, usage, model, latency_ms, cost 的字典。

        Raises:
            LLMError: 调用失败且重试用尽后抛出。
        """
        messages = self._build_messages(prompt, system)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if stop:
            payload["stop"] = stop
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_error: LLMError | None = None
        start_time = time.perf_counter()

        for attempt in range(self._max_retries + 1):
            try:
                client = await self._get_client()
                response = await client.post(
                    "/chat/completions",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                latency_ms = (time.perf_counter() - start_time) * 1000
                usage = self._parse_usage(data)
                content = data["choices"][0]["message"]["content"]
                actual_model = data.get("model", model)

                return {
                    "content": content,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "model": actual_model,
                    "latency_ms": round(latency_ms, 2),
                    "cost": round(self._calculate_cost(usage), 6),
                }

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                body = exc.response.text
                retryable = self._is_retryable(status_code)
                last_error = LLMError(
                    message=f"HTTP {status_code}: {body[:500]}",
                    status_code=status_code,
                    model=model,
                    retryable=retryable,
                )
                logger.warning(
                    "llm_http_error",
                    model=model,
                    status_code=status_code,
                    attempt=attempt + 1,
                    max_retries=self._max_retries,
                    retryable=retryable,
                )

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                last_error = LLMError(
                    message=f"网络错误: {exc}",
                    status_code=0,
                    model=model,
                    retryable=True,
                )
                logger.warning(
                    "llm_network_error",
                    model=model,
                    error=str(exc),
                    attempt=attempt + 1,
                )

            except Exception as exc:
                last_error = LLMError(
                    message=f"未知错误: {exc}",
                    status_code=0,
                    model=model,
                    retryable=False,
                )
                logger.error(
                    "llm_unknown_error",
                    model=model,
                    error=str(exc),
                    attempt=attempt + 1,
                )
                break  # 未知错误不重试

            # 如果不可重试或已达到最大重试次数，直接抛出
            if not last_error.retryable or attempt >= self._max_retries:
                break

            # 指数退避等待
            wait_time = 2**attempt
            logger.debug("llm_retry_wait", wait_seconds=wait_time, attempt=attempt + 1)
            await asyncio.sleep(wait_time)

        # 所有重试均失败
        assert last_error is not None
        raise last_error

    async def chat_completion_stream(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        json_mode: bool = False,
    ) -> AsyncStreamIterator:
        """流式 Chat Completion 调用。

        Args:
            model: 模型标识符。
            prompt: 用户提示词。
            system: 系统提示词。
            temperature: 采样温度。
            max_tokens: 最大生成 token 数。
            stop: 停止序列列表。
            json_mode: 是否启用 JSON mode。

        Returns:
            AsyncStreamIterator 可异步迭代获取流式数据块。

        Raises:
            LLMError: 调用失败且重试用尽后抛出。
        """
        messages = self._build_messages(prompt, system)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if stop:
            payload["stop"] = stop
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_error: LLMError | None = None

        for attempt in range(self._max_retries + 1):
            try:
                client = await self._get_client()
                response = await client.post(
                    "/chat/completions",
                    json=payload,
                )
                response.raise_for_status()
                return AsyncStreamIterator(
                    response=response,
                    model=model,
                    cost_per_million_input=self._cost_per_million_input,
                    cost_per_million_output=self._cost_per_million_output,
                )

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                body = exc.response.text
                retryable = self._is_retryable(status_code)
                last_error = LLMError(
                    message=f"HTTP {status_code}: {body[:500]}",
                    status_code=status_code,
                    model=model,
                    retryable=retryable,
                )

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                last_error = LLMError(
                    message=f"网络错误: {exc}",
                    status_code=0,
                    model=model,
                    retryable=True,
                )

            except Exception as exc:
                last_error = LLMError(
                    message=f"未知错误: {exc}",
                    status_code=0,
                    model=model,
                    retryable=False,
                )
                break

            if not last_error.retryable or attempt >= self._max_retries:
                break

            wait_time = 2**attempt
            await asyncio.sleep(wait_time)

        assert last_error is not None
        raise last_error

    async def close(self) -> None:
        """关闭底层 HTTP 客户端。"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> OpenAICompatibleClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


class AsyncStreamIterator:
    """SSE 流式响应迭代器。

    解析 OpenAI 兼容的 Server-Sent Events 流式响应。

    Args:
        response: httpx 响应对象（stream 模式）。
        model: 模型标识符。
        cost_per_million_input: 输入 token 单价。
        cost_per_million_output: 输出 token 单价。
    """

    def __init__(
        self,
        response: httpx.Response,
        model: str,
        cost_per_million_input: float,
        cost_per_million_output: float,
    ) -> None:
        self._response = response
        self._model = model
        self._cost_per_million_input = cost_per_million_input
        self._cost_per_million_output = cost_per_million_output
        self._prompt_tokens: int = 0
        self._completion_tokens: int = 0
        self._finish_reason: str | None = None

    @property
    def usage(self) -> TokenUsage:
        """流式响应结束后的 token 使用统计。"""
        return TokenUsage(
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
        )

    @property
    def cost(self) -> float:
        """根据已统计的 token 计算成本（元）。"""
        input_cost = (self._prompt_tokens / 1_000_000) * self._cost_per_million_input
        output_cost = (self._completion_tokens / 1_000_000) * self._cost_per_million_output
        return input_cost + output_cost

    def _parse_sse_line(self, line: str) -> dict[str, Any] | None:
        """解析 SSE 行，返回 data 字段的 JSON 数据。"""
        line = line.strip()
        if not line or line.startswith(":"):
            return None
        if line.startswith("data: "):
            data_str = line[6:]
            if data_str.strip() == "[DONE]":
                return None
            try:
                return json.loads(data_str)
            except json.JSONDecodeError:
                return None
        return None

    def _extract_chunk(self, data: dict[str, Any]) -> dict[str, Any] | None:
        """从 SSE 数据中提取增量内容。"""
        from datapilot_llm.provider import LLMChunk

        if not data.get("choices"):
            # 可能是 usage 统计信息
            usage_data = data.get("usage")
            if usage_data:
                self._prompt_tokens = usage_data.get("prompt_tokens", 0)
                self._completion_tokens = usage_data.get("completion_tokens", 0)
            return None

        choice = data["choices"][0]
        delta = choice.get("delta", {})
        content = delta.get("content", "")
        finish_reason = choice.get("finish_reason")

        return {
            "delta_content": content or "",
            "finish_reason": finish_reason,
        }

    async def __aiter__(self) -> AsyncStreamIterator:
        """返回自身作为异步迭代器。"""
        return self

    async def __anext__(self) -> dict[str, Any]:
        """获取下一个流式数据块。"""
        async for line in self._response.aiter_lines():
            data = self._parse_sse_line(line)
            if data is None:
                continue
            chunk = self._extract_chunk(data)
            if chunk is not None:
                if chunk["finish_reason"]:
                    self._finish_reason = chunk["finish_reason"]
                return chunk

        # 流结束
        raise StopAsyncIteration
