"""LLM 配置模块单元测试。"""

from __future__ import annotations

import os

import pytest


class TestLLMSettings:
    """LLMSettings 配置测试。"""

    def test_default_values(self) -> None:
        """默认配置值正确。"""
        from datapilot_llm.config import LLMSettings

        settings = LLMSettings()
        assert settings.default_model == "qwen-turbo"
        assert settings.qwen_api_base == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        assert settings.deepseek_api_base == "https://api.deepseek.com/v1"
        assert settings.timeout == 60
        assert settings.max_retries == 3

    def test_custom_values(self) -> None:
        """自定义配置值。"""
        from datapilot_llm.config import LLMSettings

        settings = LLMSettings(
            default_model="deepseek-v3",
            qwen_api_key="sk-qwen-test",
            deepseek_api_key="sk-ds-test",
            timeout=30,
            max_retries=5,
        )
        assert settings.default_model == "deepseek-v3"
        assert settings.qwen_api_key == "sk-qwen-test"
        assert settings.deepseek_api_key == "sk-ds-test"
        assert settings.timeout == 30
        assert settings.max_retries == 5

    def test_inherits_base_settings(self) -> None:
        """LLMSettings 继承 BaseAppSettings。"""
        from datapilot_common.config import BaseAppSettings
        from datapilot_llm.config import LLMSettings

        settings = LLMSettings()
        assert isinstance(settings, BaseAppSettings)
        assert hasattr(settings, "app_name")
        assert hasattr(settings, "debug")
        assert hasattr(settings, "log_level")

    def test_env_prefix(self) -> None:
        """环境变量前缀为 LLM_。"""
        from datapilot_llm.config import LLMSettings

        model_config = LLMSettings.model_config
        assert model_config.get("env_prefix") == "LLM_"

    def test_circuit_breaker_defaults(self) -> None:
        """熔断器配置默认值。"""
        from datapilot_llm.config import LLMSettings

        settings = LLMSettings()
        assert settings.circuit_breaker_failure_threshold == 5
        assert settings.circuit_breaker_recovery_timeout == 30

    def test_cost_defaults(self) -> None:
        """成本配置默认值。"""
        from datapilot_llm.config import LLMSettings

        settings = LLMSettings()
        assert settings.qwen_turbo_cost_per_million == 0.3
        assert settings.qwen_plus_cost_per_million == 1.2
        assert settings.qwen_max_cost_per_million == 12.0
        assert settings.deepseek_v3_input_cost_per_million == 1.0
        assert settings.deepseek_v3_output_cost_per_million == 2.0

    def test_env_override(self, monkeypatch) -> None:
        """环境变量可以覆盖默认配置。"""
        from datapilot_llm.config import LLMSettings

        monkeypatch.setenv("LLM_DEFAULT_MODEL", "deepseek-v3")
        monkeypatch.setenv("LLM_TIMEOUT", "30")
        settings = LLMSettings()
        assert settings.default_model == "deepseek-v3"
        assert settings.timeout == 30

    def test_timeout_bounds(self) -> None:
        """timeout 有最小值和最大值约束。"""
        from datapilot_llm.config import LLMSettings

        # 最小值 1
        with pytest.raises(Exception):
            LLMSettings(timeout=0)

    def test_max_retries_bounds(self) -> None:
        """max_retries 有最小值和最大值约束。"""
        from datapilot_llm.config import LLMSettings

        settings = LLMSettings(max_retries=0)
        assert settings.max_retries == 0
