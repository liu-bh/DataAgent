"""datapilot_common.config 单元测试。"""

from __future__ import annotations

import pytest
from pydantic_settings import SettingsConfigDict

from datapilot_common.config import BaseAppSettings


class _TestSettings(BaseAppSettings):
    """测试用配置子类。"""

    model_config = SettingsConfigDict(
        env_prefix="TEST_",
        env_file=".env.test",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://localhost/test"
    redis_url: str = "redis://localhost:6379"


class TestBaseAppSettings:
    """BaseAppSettings 基类测试。"""

    def test_default_values(self) -> None:
        settings = BaseAppSettings()
        assert settings.app_name == "datapilot"
        assert settings.app_version == "0.1.0"
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.timezone == "Asia/Shanghai"

    def test_inheritance(self) -> None:
        """子类继承公共字段。"""
        settings = _TestSettings()
        assert settings.app_name == "datapilot"
        assert settings.database_url == "postgresql+asyncpg://localhost/test"
        assert settings.redis_url == "redis://localhost:6379"

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """通过环境变量覆盖配置。"""
        monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+asyncpg://prod/db")
        monkeypatch.setenv("TEST_DEBUG", "true")
        monkeypatch.setenv("TEST_LOG_LEVEL", "DEBUG")
        settings = _TestSettings()
        assert settings.database_url == "postgresql+asyncpg://prod/db"
        assert settings.debug is True
        assert settings.log_level == "DEBUG"

    def test_extra_env_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """未知环境变量不报错（extra='ignore'）。"""
        monkeypatch.setenv("TEST_UNKNOWN_VAR", "some_value")
        settings = _TestSettings()
        assert not hasattr(settings, "unknown_var")

    def test_case_insensitive_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """环境变量名大小写不敏感。"""
        monkeypatch.setenv("test_database_url", "postgresql+asyncpg://case/db")
        settings = _TestSettings()
        assert settings.database_url == "postgresql+asyncpg://case/db"

    def test_nested_delimiter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """嵌套分隔符 __ 支持。"""
        # BaseAppSettings 使用 env_nested_delimiter="__"
        monkeypatch.setenv("TEST_APP_NAME", "my-app")
        settings = _TestSettings()
        assert settings.app_name == "my-app"


class TestServicePrefix:
    """验证 env_prefix 隔离不同服务配置。"""

    def test_different_prefixes_dont_interfere(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """不同前缀的环境变量互不干扰。"""

        class ServiceASettings(BaseAppSettings):
            model_config = SettingsConfigDict(env_prefix="A_", extra="ignore")
            database_url: str = "default_a"

        class ServiceBSettings(BaseAppSettings):
            model_config = SettingsConfigDict(env_prefix="B_", extra="ignore")
            database_url: str = "default_b"

        monkeypatch.setenv("A_DATABASE_URL", "postgres://a/db")
        # 不设置 B_DATABASE_URL，ServiceB 使用默认值

        a = ServiceASettings()
        b = ServiceBSettings()
        assert a.database_url == "postgres://a/db"
        assert b.database_url == "default_b"
