"""DataPilot 通用配置加载模块。

基于 Pydantic BaseSettings，从 .env 文件和环境变量加载配置。
各服务通过 env_prefix 区分配置命名空间。

用法::

    class MyServiceSettings(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="MYSERVICE_")
        database_url: str
        redis_url: str = "redis://localhost:6379"

    settings = MyServiceSettings()
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseAppSettings(BaseSettings):
    """DataPilot 应用配置基类。

    提供公共配置字段和 env 加载行为。
    子类通过 model_config.env_prefix 指定服务前缀。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        # 允许通过 extra='ignore' 避免未知环境变量报错
        extra="ignore",
    )

    # ---------- 通用公共配置 ----------
    app_name: str = "datapilot"
    app_version: str = "0.1.0"
    debug: bool = False
    # 日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_level: str = "INFO"
    # 时区 (IANA 格式)
    timezone: str = "Asia/Shanghai"
