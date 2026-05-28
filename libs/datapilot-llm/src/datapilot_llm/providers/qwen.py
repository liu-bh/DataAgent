"""Qwen 提供商实现。

支持三个模型等级：
- qwen-turbo: 快速响应，适合意图识别、闲聊等轻量场景
- qwen-plus: 平衡性能与质量，适合 SQL 解释、纠错等中等场景
- qwen-max: 高精度，适合对质量要求极高的场景

API 兼容 OpenAI Chat Completions 协议。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import structlog

from datapilot_llm.client import LLMError, LLMResponse as ClientResponse, OpenAICompatibleClient
from datapilot_llm.config import LLMSettings
from datapilot_llm.provider import BaseProvider, LLMChunk, LLMResponse

logger = structlog.get_logger(__name__)

# Qwen 支持的模型标识符
QWEN_MODELS = {
    "qwen-turbo": "qwen-turbo",
    "qwen-plus": "qwen-plus",
    "qwen-max": "qwen-max",
}


class QwenProvider(BaseProvider):
    """通义千问（Qwen）LLM 提供商。

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
                api_key=self._settings.qwen_api_key,
                api_base=self._settings.qwen_api_base,
                timeout=self._settings.timeout,
                max_retries=self._settings.max_retries,
                cost_per_million_input=self._settings.qwen_turbo_cost_per_million,
                cost_per_million_output=self._settings.qwen_turbo_cost_per_million,
            )
        return self._client

    def _get_cost_for_model(self, model: str) -> tuple[float, float]:
        """获取指定模型的输入/输出成本（元/百万 token）。

        Qwen 按统一价格计费（不区分输入/输出）。
        """
        cost_map: dict[str, float] = {
            "qwen-turbo": self._settings.qwen_turbo_cost_per_million,
            "qwen-plus": self._settings.qwen_plus_cost_per_million,
            "qwen-max": self._settings.qwen_max_cost_per_million,
        }
        cost = cost_map.get(model, self._settings.qwen_turbo_cost_per_million)
        return cost, cost

    def _update_client_costs(self, model: str) -> None:
        """根据模型更新客户端的成本配置。"""
        input_cost, output_cost = self._get_cost_for_model(model)
        if self._client is not None:
            self._client._cost_per_million_input = input_cost
            self._client._cost_per_million_output = output_cost

    @property
    def provider_name(self) -> str:
        """提供商名称。"""
        return "qwen"

    def validate_model(self, model: str) -> bool:
        """验证模型标识符是否受支持。"""
        return model in QWEN_MODELS

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
            model: 模型标识符，默认使用 default_model。
            json_mode: 是否启用 JSON mode。

        Returns:
            LLMResponse 包含生成结果和元数据。

        Raises:
            LLMError: LLM 调用失败。
        """
        actual_model = model or self._settings.default_model
        if not self.validate_model(actual_model):
            logger.warning(
                "qwen_invalid_model",
                model=actual_model,
                available=list(QWEN_MODELS.keys()),
            )
            actual_model = self._settings.default_model

        self._update_client_costs(actual_model)
        client = self._get_client()

        logger.debug(
            "qwen_generate_start",
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
                message=f"Qwen 生成失败: {exc}",
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
            "qwen_generate_complete",
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
        actual_model = model or self._settings.default_model
        if not self.validate_model(actual_model):
            actual_model = self._settings.default_model

        self._update_client_costs(actual_model)
        client = self._get_client()

        logger.debug("qwen_stream_start", model=actual_model)

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
                message=f"Qwen 流式调用失败: {exc}",
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
