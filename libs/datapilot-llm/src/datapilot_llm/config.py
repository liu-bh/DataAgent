"""LLM 模块配置。

通过环境变量或 .env 文件加载配置，前缀为 LLM_。
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from datapilot_common.config import BaseAppSettings


class LLMSettings(BaseAppSettings):
    """LLM 模块配置。

    环境变量前缀: LLM_

    示例 .env::

        LLM_DEFAULT_MODEL=qwen-turbo
        LLM_QWEN_API_KEY=sk-xxx
        LLM_DEEPSEEK_API_KEY=sk-yyy
    """

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- 模型配置 ----------
    default_model: str = "qwen-turbo"
    """默认模型标识符，对应 Router 中的场景默认选择。"""

    # ---------- Qwen 配置 ----------
    qwen_api_key: str = ""
    """通义千问 API Key。"""
    qwen_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    """通义千问 API 地址（OpenAI 兼容模式）。"""

    # ---------- DeepSeek 配置 ----------
    deepseek_api_key: str = ""
    """DeepSeek API Key。"""
    deepseek_api_base: str = "https://api.deepseek.com/v1"
    """DeepSeek API 地址。"""

    # ---------- 通用参数 ----------
    timeout: int = Field(default=60, ge=1, le=300)
    """HTTP 请求超时时间（秒）。"""
    max_retries: int = Field(default=3, ge=0, le=10)
    """最大重试次数（指数退避，仅重试 5xx）。"""

    # ---------- 熔断器配置 ----------
    circuit_breaker_failure_threshold: int = Field(default=5, ge=1)
    """连续失败次数阈值，达到后触发熔断。"""
    circuit_breaker_recovery_timeout: int = Field(default=30, ge=5)
    """熔断后等待恢复的时间（秒），之后进入半开状态。"""

    # ---------- 成本配置（元/百万 token） ----------
    qwen_turbo_cost_per_million: float = Field(default=0.3)
    """Qwen-Turbo 成本：0.3 元/百万 token。"""
    qwen_plus_cost_per_million: float = Field(default=1.2)
    """Qwen-Plus 成本：1.2 元/百万 token。"""
    qwen_max_cost_per_million: float = Field(default=12.0)
    """Qwen-Max 成本：12 元/百万 token。"""
    deepseek_v3_input_cost_per_million: float = Field(default=1.0)
    """DeepSeek-V3 输入成本：1 元/百万 token。"""
    deepseek_v3_output_cost_per_million: float = Field(default=2.0)
    """DeepSeek-V3 输出成本：2 元/百万 token。"""
