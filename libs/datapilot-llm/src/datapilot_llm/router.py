"""LLM 模型路由器 + 熔断器。

根据使用场景自动选择最优模型，内置熔断保护与自动降级策略。
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

from datapilot_llm.client import LLMError
from datapilot_llm.config import LLMSettings
from datapilot_llm.logger import LLMCallLogger, get_call_logger
from datapilot_llm.providers.deepseek import DeepSeekProvider
from datapilot_llm.providers.qwen import QwenProvider

if TYPE_CHECKING:
    from datapilot_llm.provider import BaseProvider, LLMResponse

logger = structlog.get_logger(__name__)


class Scene(enum.StrEnum):
    """LLM 使用场景枚举。"""

    NL2SQL = "nl2sql"
    """自然语言转 SQL，需要复杂推理能力。"""

    INTENT = "intent"
    """意图识别，快速分类即可。"""

    EXPLANATION = "explanation"
    """SQL 解释，需要平衡质量和速度。"""

    CORRECTION = "correction"
    """SQL 纠错，需要中等推理能力。"""

    CHITCHAT = "chitchat"
    """闲聊，轻量快速。"""


# 场景到模型的默认映射：主模型 -> 备用模型
DEFAULT_SCENE_MODEL_MAP: dict[Scene, list[str]] = {
    Scene.NL2SQL: ["deepseek-v3", "qwen-max"],
    Scene.INTENT: ["qwen-turbo", "qwen-plus"],
    Scene.EXPLANATION: ["qwen-plus", "qwen-turbo"],
    Scene.CORRECTION: ["qwen-plus", "qwen-max"],
    Scene.CHITCHAT: ["qwen-turbo", "qwen-plus"],
}

# 模型标识符到提供商名称的映射
MODEL_TO_PROVIDER: dict[str, str] = {
    "deepseek-v3": "deepseek",
    "qwen-turbo": "qwen",
    "qwen-plus": "qwen",
    "qwen-max": "qwen",
}


class CircuitState(enum.StrEnum):
    """熔断器状态。"""

    CLOSED = "closed"
    """正常状态，允许请求通过。"""

    OPEN = "open"
    """熔断状态，拒绝请求。"""

    HALF_OPEN = "half_open"
    """半开状态，允许少量探测请求。"""


@dataclass
class CircuitBreaker:
    """单模型熔断器。

    连续失败达到阈值后自动熔断，一段时间后半开探测。
    探测成功则恢复，失败则重新熔断。

    Attributes:
        model: 模型标识符。
        failure_threshold: 连续失败触发熔断的阈值。
        recovery_timeout: 熔断恢复等待时间（秒）。
        failure_count: 当前连续失败次数。
        state: 熔断器状态。
        last_failure_time: 上次失败时间戳。
        last_state_change_time: 上次状态变更时间戳。
    """

    model: str
    failure_threshold: int = 5
    recovery_timeout: int = 30
    failure_count: int = 0
    state: CircuitState = CircuitState.CLOSED
    last_failure_time: float = 0.0
    last_state_change_time: float = 0.0

    def _current_time(self) -> float:
        """获取当前时间戳。"""
        return time.monotonic()

    def is_available(self) -> bool:
        """判断当前是否允许请求通过。

        Returns:
            True 表示熔断器允许请求（CLOSED 或 HALF_OPEN），False 表示熔断中。
        """
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # 检查是否已过恢复时间，进入半开状态
            elapsed = self._current_time() - self.last_state_change_time
            if elapsed >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change_time = self._current_time()
                logger.info(
                    "circuit_breaker_half_open",
                    model=self.model,
                    elapsed_seconds=round(elapsed, 1),
                )
                return True
            return False

        # HALF_OPEN 状态允许探测请求
        return True

    def record_success(self) -> None:
        """记录一次成功调用。"""
        if self.state == CircuitState.HALF_OPEN:
            # 半开状态下成功，恢复为关闭
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_state_change_time = self._current_time()
            logger.info("circuit_breaker_recovered", model=self.model)
        else:
            # 正常状态下成功，重置失败计数
            self.failure_count = 0

    def record_failure(self) -> None:
        """记录一次失败调用。"""
        self.failure_count += 1
        self.last_failure_time = self._current_time()

        if self.state == CircuitState.HALF_OPEN:
            # 半开状态下失败，重新熔断
            self.state = CircuitState.OPEN
            self.last_state_change_time = self._current_time()
            logger.warning(
                "circuit_breaker_reopen",
                model=self.model,
                failure_count=self.failure_count,
            )
        elif self.failure_count >= self.failure_threshold:
            # 失败次数达到阈值，触发熔断
            self.state = CircuitState.OPEN
            self.last_state_change_time = self._current_time()
            logger.warning(
                "circuit_breaker_open",
                model=self.model,
                failure_count=self.failure_count,
                threshold=self.failure_threshold,
            )

    @property
    def state_name(self) -> str:
        """当前状态名称。"""
        return self.state.value


@dataclass
class ProviderRegistry:
    """提供商注册表。

    管理所有可用的 Provider 实例和对应的熔断器。
    """

    qwen: QwenProvider | None = None
    deepseek: DeepSeekProvider | None = None
    circuit_breakers: dict[str, CircuitBreaker] = field(default_factory=dict)

    def get_provider(self, provider_name: str) -> BaseProvider | None:
        """根据提供商名称获取 Provider 实例。"""
        if provider_name == "qwen" and self.qwen is not None:
            return self.qwen
        if provider_name == "deepseek" and self.deepseek is not None:
            return self.deepseek
        return None

    def get_circuit_breaker(self, model: str) -> CircuitBreaker:
        """获取指定模型的熔断器，不存在则创建。"""
        if model not in self.circuit_breakers:
            self.circuit_breakers[model] = CircuitBreaker(model=model)
        return self.circuit_breakers[model]


class LLMRouter:
    """LLM 统一路由入口。

    根据使用场景自动选择最优模型，内置熔断保护和自动降级。

    用法::

        router = LLMRouter(settings)
        response = await router.generate(Scene.NL2SQL, "查询上月销售额")
        async for chunk in router.generate_stream(Scene.CHITCHAT, "你好"):
            print(chunk.delta_content, end="")
    """

    def __init__(self, settings: LLMSettings | None = None) -> None:
        if settings is None:
            settings = LLMSettings()
        self._settings = settings
        self._call_logger: LLMCallLogger = get_call_logger()

        # 初始化提供商
        self._qwen = QwenProvider(settings)
        self._deepseek = DeepSeekProvider(settings)

        # 注册表
        self._registry = ProviderRegistry(
            qwen=self._qwen,
            deepseek=self._deepseek,
        )

        # 初始化熔断器
        for model_id in MODEL_TO_PROVIDER:
            self._registry.get_circuit_breaker(model_id)

        # 场景模型映射（可运行时修改）
        self._scene_models: dict[Scene, list[str]] = dict(DEFAULT_SCENE_MODEL_MAP)

    def _resolve_provider(self, model: str) -> BaseProvider | None:
        """根据模型标识符解析到对应的 Provider 实例。"""
        provider_name = MODEL_TO_PROVIDER.get(model)
        if provider_name is None:
            return None
        return self._registry.get_provider(provider_name)

    def _select_model(self, scene: Scene) -> str:
        """根据场景选择可用模型。

        遍历场景的模型优先级列表，跳过已熔断的模型，
        返回第一个可用的模型。如果全部熔断，返回第一个模型（强制尝试）。

        Args:
            scene: 使用场景。

        Returns:
            选中的模型标识符。
        """
        candidates = self._scene_models.get(scene, [self._settings.default_model])

        for model in candidates:
            cb = self._registry.get_circuit_breaker(model)
            if cb.is_available():
                return model
            logger.debug(
                "model_skipped_circuit_open",
                model=model,
                scene=scene.value,
                circuit_state=cb.state_name,
            )

        # 所有模型都熔断，使用第一个模型强制尝试
        logger.warning(
            "all_models_circuit_open",
            scene=scene.value,
            fallback_model=candidates[0],
        )
        return candidates[0]

    async def generate(
        self,
        scene: Scene,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        model: str | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """非流式生成（自动路由）。

        Args:
            scene: 使用场景。
            prompt: 用户提示词。
            system: 系统提示词。
            temperature: 采样温度，None 使用场景默认值。
            max_tokens: 最大 token 数，None 使用场景默认值。
            stop: 停止序列。
            model: 强制指定模型，跳过路由。
            json_mode: 是否启用 JSON mode。

        Returns:
            LLMResponse 生成结果。

        Raises:
            LLMError: 所有模型均不可用时抛出。
        """
        if model is None:
            model = self._select_model(scene)

        # 场景默认参数
        if temperature is None:
            temperature = self._get_default_temperature(scene)
        if max_tokens is None:
            max_tokens = self._get_default_max_tokens(scene)

        provider = self._resolve_provider(model)
        if provider is None:
            raise LLMError(
                message=f"未找到模型 {model} 对应的提供商",
                model=model,
            )

        cb = self._registry.get_circuit_breaker(model)
        start_time = time.perf_counter()

        try:
            response = await provider.generate(
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop,
                model=model,
                json_mode=json_mode,
            )
            cb.record_success()

            # 记录调用日志
            await self._call_logger.log(
                model=response.model,
                scene=scene.value,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                latency_ms=response.latency_ms,
                cost=response.cost,
                success=True,
            )

            return response

        except LLMError as exc:
            cb.record_failure()
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # 记录失败日志
            await self._call_logger.log(
                model=model,
                scene=scene.value,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=round(elapsed_ms, 2),
                cost=0.0,
                success=False,
                error_message=exc.message,
            )

            # 尝试降级到备用模型
            if model in self._scene_models.get(scene, []):
                fallback_models = [m for m in self._scene_models[scene] if m != model]
                for fallback in fallback_models:
                    fallback_cb = self._registry.get_circuit_breaker(fallback)
                    if fallback_cb.is_available():
                        logger.warning(
                            "llm_fallback",
                            original_model=model,
                            fallback_model=fallback,
                            scene=scene.value,
                            error=exc.message,
                        )
                        return await self.generate(
                            scene=scene,
                            prompt=prompt,
                            system=system,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            stop=stop,
                            model=fallback,
                            json_mode=json_mode,
                        )

            raise

    async def generate_stream(
        self,
        scene: Scene,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        model: str | None = None,
        json_mode: bool = False,
    ):
        """流式生成（自动路由）。

        Args:
            scene: 使用场景。
            prompt: 用户提示词。
            system: 系统提示词。
            temperature: 采样温度。
            max_tokens: 最大 token 数。
            stop: 停止序列。
            model: 强制指定模型。
            json_mode: 是否启用 JSON mode。

        Yields:
            LLMChunk 流式数据块。
        """
        if model is None:
            model = self._select_model(scene)

        if temperature is None:
            temperature = self._get_default_temperature(scene)
        if max_tokens is None:
            max_tokens = self._get_default_max_tokens(scene)

        provider = self._resolve_provider(model)
        if provider is None:
            raise LLMError(
                message=f"未找到模型 {model} 对应的提供商",
                model=model,
            )

        cb = self._registry.get_circuit_breaker(model)

        try:
            chunk_gen = provider.generate_stream(
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop,
                model=model,
                json_mode=json_mode,
            )
            async for chunk in chunk_gen:
                yield chunk
            cb.record_success()

        except LLMError:
            cb.record_failure()
            raise

    def _get_default_temperature(self, scene: Scene) -> float:
        """获取场景默认温度。

        NL2SQL 需要确定性输出，使用较低温度。
        闲聊等场景可以稍高。
        """
        temperature_map: dict[Scene, float] = {
            Scene.NL2SQL: 0.1,
            Scene.INTENT: 0.3,
            Scene.EXPLANATION: 0.5,
            Scene.CORRECTION: 0.3,
            Scene.CHITCHAT: 0.7,
        }
        return temperature_map.get(scene, 0.7)

    def _get_default_max_tokens(self, scene: Scene) -> int:
        """获取场景默认最大 token 数。"""
        max_tokens_map: dict[Scene, int] = {
            Scene.NL2SQL: 4096,
            Scene.INTENT: 1024,
            Scene.EXPLANATION: 2048,
            Scene.CORRECTION: 4096,
            Scene.CHITCHAT: 1024,
        }
        return max_tokens_map.get(scene, 4096)

    def get_circuit_state(self, model: str) -> str:
        """获取指定模型的熔断器状态。"""
        cb = self._registry.get_circuit_breaker(model)
        return cb.state_name

    def get_all_circuit_states(self) -> dict[str, str]:
        """获取所有模型的熔断器状态。"""
        return {model: cb.state_name for model, cb in self._registry.circuit_breakers.items()}

    def configure_scene_models(self, scene: Scene, models: list[str]) -> None:
        """运行时配置场景的模型优先级列表。

        Args:
            scene: 使用场景。
            models: 按优先级排列的模型标识符列表。
        """
        self._scene_models[scene] = models
        logger.info(
            "scene_models_configured",
            scene=scene.value,
            models=models,
        )

    async def close(self) -> None:
        """关闭所有提供商客户端。"""
        await self._qwen.close()
        await self._deepseek.close()
        await self._call_logger.close()
