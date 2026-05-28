"""成本计算单元测试。"""

from __future__ import annotations

import pytest

from datapilot_llm.config import LLMSettings


class TestQwenCost:
    """Qwen 成本计算测试。"""

    def test_turbo_cost(self) -> None:
        """Qwen-Turbo: 0.3 元/百万 token。"""
        settings = LLMSettings()
        assert settings.qwen_turbo_cost_per_million == 0.3

        # 1M token 应该花费 0.3 元
        tokens = 1_000_000
        cost = (tokens / 1_000_000) * settings.qwen_turbo_cost_per_million
        assert abs(cost - 0.3) < 1e-9

    def test_plus_cost(self) -> None:
        """Qwen-Plus: 1.2 元/百万 token。"""
        settings = LLMSettings()
        assert settings.qwen_plus_cost_per_million == 1.2

    def test_max_cost(self) -> None:
        """Qwen-Max: 12 元/百万 token。"""
        settings = LLMSettings()
        assert settings.qwen_max_cost_per_million == 12.0

    def test_turbo_cost_small_tokens(self) -> None:
        """少量 token 的成本计算。"""
        settings = LLMSettings()
        tokens = 500  # 500 input tokens
        cost = (tokens / 1_000_000) * settings.qwen_turbo_cost_per_million
        expected = 500 * 0.3 / 1_000_000
        assert abs(cost - expected) < 1e-12


class TestDeepSeekCost:
    """DeepSeek 成本计算测试（输入输出差异化计费）。"""

    def test_input_cost(self) -> None:
        """DeepSeek-V3 输入: 1 元/百万 token。"""
        settings = LLMSettings()
        assert settings.deepseek_v3_input_cost_per_million == 1.0

    def test_output_cost(self) -> None:
        """DeepSeek-V3 输出: 2 元/百万 token。"""
        settings = LLMSettings()
        assert settings.deepseek_v3_output_cost_per_million == 2.0

    def test_total_cost(self) -> None:
        """DeepSeek 总成本 = 输入成本 + 输出成本。"""
        settings = LLMSettings()
        input_tokens = 1_000_000
        output_tokens = 500_000

        input_cost = (input_tokens / 1_000_000) * settings.deepseek_v3_input_cost_per_million
        output_cost = (output_tokens / 1_000_000) * settings.deepseek_v3_output_cost_per_million
        total = input_cost + output_cost

        assert abs(total - 2.0) < 1e-9

    def test_small_tokens_cost(self) -> None:
        """少量 token 的差异化成本。"""
        settings = LLMSettings()
        input_tokens = 200
        output_tokens = 50

        input_cost = (input_tokens / 1_000_000) * settings.deepseek_v3_input_cost_per_million
        output_cost = (output_tokens / 1_000_000) * settings.deepseek_v3_output_cost_per_million

        assert abs(input_cost - 0.0002) < 1e-10
        assert abs(output_cost - 0.0001) < 1e-10


class TestCostComparison:
    """不同模型成本对比测试。"""

    def test_qwen_turbo_cheapest(self) -> None:
        """Qwen-Turbo 是最便宜的模型。"""
        settings = LLMSettings()
        assert settings.qwen_turbo_cost_per_million < settings.qwen_plus_cost_per_million
        assert settings.qwen_turbo_cost_per_million < settings.qwen_max_cost_per_million

    def test_deepseek_reasonable_pricing(self) -> None:
        """DeepSeek-V3 定价合理，介于 Qwen-Plus 和 Qwen-Max 之间。"""
        settings = LLMSettings()
        # 输入成本
        assert settings.deepseek_v3_input_cost_per_million < settings.qwen_max_cost_per_million
        # 综合成本（假设输入输出 1:1）
        avg_deepseek = (
            settings.deepseek_v3_input_cost_per_million
            + settings.deepseek_v3_output_cost_per_million
        ) / 2
        assert avg_deepseek < settings.qwen_max_cost_per_million

    def test_1m_tokens_all_models(self) -> None:
        """1M 输入 + 1M 输出的各模型成本对比。"""
        settings = LLMSettings()

        # Qwen 按统一价格（输入+输出）
        qwen_turbo = (2_000_000 / 1_000_000) * settings.qwen_turbo_cost_per_million
        qwen_plus = (2_000_000 / 1_000_000) * settings.qwen_plus_cost_per_million
        qwen_max = (2_000_000 / 1_000_000) * settings.qwen_max_cost_per_million

        # DeepSeek 差异化
        deepseek = (
            (1_000_000 / 1_000_000) * settings.deepseek_v3_input_cost_per_million
            + (1_000_000 / 1_000_000) * settings.deepseek_v3_output_cost_per_million
        )

        assert qwen_turbo < qwen_plus < qwen_max
        # DeepSeek 综合成本低于 Qwen-Max
        assert deepseek < qwen_max
