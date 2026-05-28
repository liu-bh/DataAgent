"""LLM Provider 抽象基类与响应数据模型。

定义所有 LLM 提供商必须实现的统一接口，以及标准化的响应结构。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@dataclass
class LLMChunk:
    """流式响应的单个数据块。

    Attributes:
        delta_content: 增量文本内容，流结束时可能为空字符串。
        finish_reason: 结束原因，如 "stop"、"length"、"content_filter"，
            未结束的中间块为 None。
    """

    delta_content: str
    finish_reason: str | None = None


@dataclass
class LLMResponse:
    """非流式调用的完整响应。

    Attributes:
        content: 模型生成的完整文本。
        prompt_tokens: 输入提示词消耗的 token 数。
        completion_tokens: 模型输出消耗的 token 数。
        model: 实际使用的模型标识符。
        latency_ms: 请求耗时（毫秒）。
        cost: 本次调用成本（元）。
    """

    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    latency_ms: float = 0.0
    cost: float = 0.0

    @property
    def total_tokens(self) -> int:
        """总 token 数（输入 + 输出）。"""
        return self.prompt_tokens + self.completion_tokens


class BaseProvider(ABC):
    """LLM 提供商抽象基类。

    所有 LLM 提供商（Qwen、DeepSeek 等）必须继承此类并实现
    generate 和 generate_stream 方法。
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        """非流式文本生成。

        Args:
            prompt: 用户提示词。
            system: 系统提示词，可选。
            temperature: 采样温度，越高随机性越大。
            max_tokens: 最大生成 token 数。
            stop: 停止序列列表。

        Returns:
            LLMResponse 包含生成结果和元数据。

        Raises:
            LLMError: LLM 调用失败时抛出。
        """
        ...

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
    ) -> AsyncGenerator[LLMChunk, None]:
        """流式文本生成。

        Args:
            prompt: 用户提示词。
            system: 系统提示词，可选。
            temperature: 采样温度。
            max_tokens: 最大生成 token 数。
            stop: 停止序列列表。

        Yields:
            LLMChunk 流式数据块。
        """
        ...  # pragma: no cover

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供商名称，如 "qwen"、"deepseek"。"""
        ...
