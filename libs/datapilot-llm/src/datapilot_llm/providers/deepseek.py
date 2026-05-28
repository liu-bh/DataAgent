"""DeepSeek 提供商实现。

支持模型：
- deepseek-v3: 复杂推理能力强，适合 NL2SQL 等需要深度理解的场景

API 兼容 OpenAI Chat Completions 协议。
输入/输出 token 分别计费。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from datapilot_llm.client import LLMError, OpenAICompatibleClient
from datapilot_llm.config import LLMSettings
from datapilot_llm.provider import BaseProvider, LLMChunk, LLMResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger(__name__)

# DeepSeek 支持的模型标识符
DEEPSEEK_MODELS = {
    "deepseek-v3": "deepseek-v3",
}


class DeepSeekProvider(BaseProvider):
    """DeepSeek LLM 提供商。

    Args:
        settings: LLM 配置实例。
    """

    def __init__(self, settings: LLMSettings | None = None) -> None:
        if settings is None:
            settings = LLMSettings()
        self._settings = settings
        self._client: OpenAICompatibleClient | None = None

    def _get_client(self) -> OpenAICompatibleClient:
        """获取或创建 OpenAI 兼容客户端。"""
        if self._client is None:
            self._client = OpenAICompatibleClient(
                api_key=self._settings.deepseek_api_key,
                api_base=self._settings.deepseek_api_base,
                timeout=self._settings.timeout,
                max_retries=self._settings.max_retries,
                cost_per_million_input=self._settings.deepseek_v3_input_cost_per_million,
                cost_per_million_output=self._settings.deepseek_v3_output_cost_per_million,
            )
        return self._client

    @property
    def provider_name(self) -> str:
        """提供商名称。"""
        return "deepseek"

    def validate_model(self, model: str) -> bool:
        """验证模型标识符是否受支持。"""
        return model in DEEPSEEK_MODELS

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        model: str | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """非流式文本生成。

        Args:
            prompt: 用户提示词。
            system: 系统提示词。
            temperature: 采样温度。
            max_tokens: 最大生成 token 数。
            stop: 停止序列列表。
            model: 模型标识符，默认使用 deepseek-v3。
            json_mode: 是否启用 JSON mode。

        Returns:
            LLMResponse 包含生成结果和元数据。

        Raises:
            LLMError: LLM 调用失败。
        """
        actual_model = model or "deepseek-v3"
        if not self.validate_model(actual_model):
            logger.warning(
                "deepseek_invalid_model",
                model=actual_model,
                available=list(DEEPSEEK_MODELS.keys()),
            )
            actual_model = "deepseek-v3"

        client = self._get_client()

        logger.debug(
            "deepseek_generate_start",
            model=actual_model,
            prompt_length=len(prompt),
            temperature=temperature,
        )

        try:
            result = await client.chat_completion(
                model=actual_model,
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop,
                json_mode=json_mode,
            )
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(
                message=f"DeepSeek 生成失败: {exc}",
                model=actual_model,
            ) from exc

        response = LLMResponse(
            content=result["content"],
            prompt_tokens=result["prompt_tokens"],
            completion_tokens=result["completion_tokens"],
            model=result["model"],
            latency_ms=result["latency_ms"],
            cost=result["cost"],
        )

        logger.info(
            "deepseek_generate_complete",
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            latency_ms=response.latency_ms,
            cost=response.cost,
        )

        return response

    async def generate_stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        model: str | None = None,
        json_mode: bool = False,
    ) -> AsyncGenerator[LLMChunk, None]:
        """流式文本生成。

        Args:
            prompt: 用户提示词。
            system: 系统提示词。
            temperature: 采样温度。
            max_tokens: 最大生成 token 数。
            stop: 停止序列列表。
            model: 模型标识符。
            json_mode: 是否启用 JSON mode。

        Yields:
            LLMChunk 流式数据块。

        Raises:
            LLMError: LLM 调用失败。
        """
        actual_model = model or "deepseek-v3"
        if not self.validate_model(actual_model):
            actual_model = "deepseek-v3"

        client = self._get_client()

        logger.debug("deepseek_stream_start", model=actual_model)

        try:
            stream = await client.chat_completion_stream(
                model=actual_model,
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop,
                json_mode=json_mode,
            )
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(
                message=f"DeepSeek 流式调用失败: {exc}",
                model=actual_model,
            ) from exc

        try:
            async for chunk_data in stream:
                yield LLMChunk(
                    delta_content=chunk_data["delta_content"],
                    finish_reason=chunk_data["finish_reason"],
                )
        finally:
            await client.close()

    async def close(self) -> None:
        """关闭底层客户端。"""
        if self._client is not None:
            await self._client.close()
            self._client = None
