"""Router 模型选择与降级策略单元测试。"""

from __future__ import annotations

import pytest

from datapilot_llm.router import (
    CircuitBreaker,
    CircuitState,
    LLMRouter,
    Scene,
    DEFAULT_SCENE_MODEL_MAP,
)


# ---------- Scene 枚举测试 ----------


class TestScene:
    """Scene 枚举测试。"""

    def test_all_scenes_defined(self) -> None:
        """所有场景都已定义。"""
        expected = {"nl2sql", "intent", "explanation", "correction", "chitchat"}
        actual = {s.value for s in Scene}
        assert actual == expected

    def test_scene_values(self) -> None:
        assert Scene.NL2SQL.value == "nl2sql"
        assert Scene.INTENT.value == "intent"
        assert Scene.EXPLANATION.value == "explanation"
        assert Scene.CORRECTION.value == "correction"
        assert Scene.CHITCHAT.value == "chitchat"


# ---------- 默认场景模型映射测试 ----------


class TestSceneModelMap:
    """场景到模型的默认映射测试。"""

    def test_all_scenes_have_mapping(self) -> None:
        """每个场景都有至少一个主模型和一个备用模型。"""
        for scene in Scene:
            models = DEFAULT_SCENE_MODEL_MAP.get(scene)
            assert models is not None, f"场景 {scene.value} 缺少模型映射"
            assert len(models) >= 2, f"场景 {scene.value} 至少需要主模型和备用模型"

    def test_nl2sql_uses_deepseek(self) -> None:
        """NL2SQL 场景首选 DeepSeek-V3。"""
        assert DEFAULT_SCENE_MODEL_MAP[Scene.NL2SQL][0] == "deepseek-v3"

    def test_intent_uses_qwen_turbo(self) -> None:
        """意图识别场景首选 Qwen-Turbo。"""
        assert DEFAULT_SCENE_MODEL_MAP[Scene.INTENT][0] == "qwen-turbo"

    def test_chitchat_uses_qwen_turbo(self) -> None:
        """闲聊场景首选 Qwen-Turbo。"""
        assert DEFAULT_SCENE_MODEL_MAP[Scene.CHITCHAT][0] == "qwen-turbo"


# ---------- 熔断器状态转换测试 ----------


class TestCircuitBreaker:
    """熔断器状态转换测试。"""

    def _make_breaker(
        self,
        threshold: int = 5,
        recovery_timeout: int = 30,
    ) -> CircuitBreaker:
        """创建测试用熔断器。"""
        return CircuitBreaker(
            model="test-model",
            failure_threshold=threshold,
            recovery_timeout=recovery_timeout,
        )

    def test_initial_state_closed(self) -> None:
        """初始状态为 CLOSED。"""
        cb = self._make_breaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available() is True

    def test_closed_allows_requests(self) -> None:
        """CLOSED 状态允许请求通过。"""
        cb = self._make_breaker()
        assert cb.is_available() is True

    def test_single_failure_stays_closed(self) -> None:
        """单次失败不触发熔断。"""
        cb = self._make_breaker(threshold=5)
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 1

    def test_failure_at_threshold_opens(self) -> None:
        """连续失败达到阈值触发熔断。"""
        cb = self._make_breaker(threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3

    def test_open_blocks_requests(self) -> None:
        """OPEN 状态拒绝请求。"""
        cb = self._make_breaker(threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_available() is False

    def test_success_resets_failure_count(self) -> None:
        """成功调用重置失败计数。"""
        cb = self._make_breaker(threshold=5)
        for _ in range(3):
            cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED

    def test_half_open_success_recovers(self) -> None:
        """半开状态下成功调用恢复为 CLOSED。"""
        cb = self._make_breaker(threshold=2, recovery_timeout=0)
        # 触发熔断
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # 等待恢复时间后进入半开
        assert cb.is_available() is True
        assert cb.state == CircuitState.HALF_OPEN

        # 半开状态下成功，恢复
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self) -> None:
        """半开状态下失败重新熔断。"""
        cb = self._make_breaker(threshold=2, recovery_timeout=0)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # 进入半开
        cb.is_available()
        assert cb.state == CircuitState.HALF_OPEN

        # 失败重新熔断
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_recovery_timeout_blocks_before_elapsed(self) -> None:
        """未到恢复时间时仍然拒绝请求。"""
        cb = self._make_breaker(threshold=2, recovery_timeout=9999)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_available() is False

    def test_recovery_timeout_allows_after_elapsed(self) -> None:
        """超过恢复时间后进入半开状态。"""
        cb = self._make_breaker(threshold=2, recovery_timeout=0)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        # recovery_timeout=0 立即恢复
        assert cb.is_available() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_state_name_property(self) -> None:
        """state_name 返回正确的字符串。"""
        cb = self._make_breaker()
        assert cb.state_name == "closed"

        cb.state = CircuitState.OPEN
        assert cb.state_name == "open"

        cb.state = CircuitState.HALF_OPEN
        assert cb.state_name == "half_open"


# ---------- Router 模型选择测试 ----------


class TestLLMRouterModelSelection:
    """Router 模型选择逻辑测试。"""

    @pytest.fixture
    def router(self, llm_settings):
        """创建测试用 Router。"""
        # 重置调用日志
        from datapilot_llm.logger import reset_call_logger
        reset_call_logger()
        return LLMRouter(llm_settings)

    def test_nl2sql_selects_deepseek(self, router) -> None:
        """NL2SQL 场景选择 DeepSeek-V3。"""
        model = router._select_model(Scene.NL2SQL)
        assert model == "deepseek-v3"

    def test_intent_selects_qwen_turbo(self, router) -> None:
        """意图识别选择 Qwen-Turbo。"""
        model = router._select_model(Scene.INTENT)
        assert model == "qwen-turbo"

    def test_explanation_selects_qwen_plus(self, router) -> None:
        """SQL 解释选择 Qwen-Plus。"""
        model = router._select_model(Scene.EXPLANATION)
        assert model == "qwen-plus"

    def test_correction_selects_qwen_plus(self, router) -> None:
        """SQL 纠错选择 Qwen-Plus。"""
        model = router._select_model(Scene.CORRECTION)
        assert model == "qwen-plus"

    def test_chitchat_selects_qwen_turbo(self, router) -> None:
        """闲聊选择 Qwen-Turbo。"""
        model = router._select_model(Scene.CHITCHAT)
        assert model == "qwen-turbo"

    def test_fallback_when_primary_open(self, router) -> None:
        """主模型熔断时自动选择备用模型。"""
        # 熔断 deepseek-v3
        cb = router._registry.get_circuit_breaker("deepseek-v3")
        for _ in range(5):
            cb.record_failure()

        model = router._select_model(Scene.NL2SQL)
        # 应该降级到 qwen-max
        assert model == "qwen-max"

    def test_all_models_open_returns_first(self, router) -> None:
        """所有模型都熔断时返回第一个模型。"""
        # 熔断所有 NL2SQL 相关模型
        for model_id in ["deepseek-v3", "qwen-max"]:
            cb = router._registry.get_circuit_breaker(model_id)
            for _ in range(5):
                cb.record_failure()

        model = router._select_model(Scene.NL2SQL)
        # 全部熔断，返回第一个
        assert model == "deepseek-v3"

    def test_get_circuit_state(self, router) -> None:
        """获取单个模型熔断状态。"""
        state = router.get_circuit_state("qwen-turbo")
        assert state == "closed"

    def test_get_all_circuit_states(self, router) -> None:
        """获取所有模型熔断状态。"""
        states = router.get_all_circuit_states()
        assert "qwen-turbo" in states
        assert "deepseek-v3" in states
        assert "qwen-plus" in states
        assert "qwen-max" in states
        # 初始状态都是 closed
        assert all(s == "closed" for s in states.values())

    def test_configure_scene_models(self, router) -> None:
        """运行时配置场景模型优先级。"""
        router.configure_scene_models(
            Scene.NL2SQL, ["qwen-plus", "deepseek-v3"]
        )
        model = router._select_model(Scene.NL2SQL)
        assert model == "qwen-plus"

    def test_default_temperature(self, router) -> None:
        """场景默认温度。"""
        assert router._get_default_temperature(Scene.NL2SQL) == 0.1
        assert router._get_default_temperature(Scene.INTENT) == 0.3
        assert router._get_default_temperature(Scene.CHITCHAT) == 0.7

    def test_default_max_tokens(self, router) -> None:
        """场景默认最大 token 数。"""
        assert router._get_default_max_tokens(Scene.NL2SQL) == 4096
        assert router._get_default_max_tokens(Scene.INTENT) == 1024
        assert router._get_default_max_tokens(Scene.EXPLANATION) == 2048
