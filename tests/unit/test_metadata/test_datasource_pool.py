"""数据源连接池管理单元测试。"""

import uuid
from unittest.mock import MagicMock, patch

import pytest


class TestEncryptPassword:
    """密码加密工具测试。"""

    def test_encrypt_consistency(self) -> None:
        """测试相同密码加密结果一致。"""
        from datapilot_semantic.metadata.datasource_pool import encrypt_password

        hash1 = encrypt_password("my_password")
        hash2 = encrypt_password("my_password")
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 十六进制长度

    def test_different_passwords(self) -> None:
        """测试不同密码加密结果不同。"""
        from datapilot_semantic.metadata.datasource_pool import encrypt_password

        hash1 = encrypt_password("password_a")
        hash2 = encrypt_password("password_b")
        assert hash1 != hash2

    def test_custom_salt(self) -> None:
        """测试自定义 salt。"""
        from datapilot_semantic.metadata.datasource_pool import encrypt_password

        hash_default = encrypt_password("test")
        hash_custom = encrypt_password("test", salt="custom-salt")
        assert hash_default != hash_custom

    def test_empty_password(self) -> None:
        """测试空密码加密。"""
        from datapilot_semantic.metadata.datasource_pool import encrypt_password

        hashed = encrypt_password("")
        assert len(hashed) == 64


class TestVerifyPassword:
    """密码验证测试。"""

    def test_verify_success(self) -> None:
        """测试密码验证成功。"""
        from datapilot_semantic.metadata.datasource_pool import (
            encrypt_password,
            verify_password,
        )

        hashed = encrypt_password("correct_password")
        assert verify_password("correct_password", hashed) is True

    def test_verify_failure(self) -> None:
        """测试密码验证失败。"""
        from datapilot_semantic.metadata.datasource_pool import (
            encrypt_password,
            verify_password,
        )

        hashed = encrypt_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_verify_with_salt(self) -> None:
        """测试带 salt 的密码验证。"""
        from datapilot_semantic.metadata.datasource_pool import (
            encrypt_password,
            verify_password,
        )

        salt = "my-app-salt"
        hashed = encrypt_password("secret", salt=salt)
        assert verify_password("secret", hashed, salt=salt) is True
        assert verify_password("secret", hashed) is False  # 默认 salt 不同


class TestBuildConnectionUrl:
    """连接 URL 构建测试。"""

    def test_mysql_url(self) -> None:
        """测试 MySQL 连接 URL 构建。"""
        from datapilot_semantic.metadata.datasource_pool import build_connection_url
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        config = DataConnectionConfig(
            type="mysql",
            host="10.0.0.1",
            port=3306,
            database="analytics",
            username="admin",
            password="p@ss123",
        )
        url = build_connection_url(config)
        assert url.startswith("mysql+pymysql://admin:")
        assert "10.0.0.1:3306" in url
        assert "analytics" in url

    def test_postgresql_url(self) -> None:
        """测试 PostgreSQL 连接 URL 构建。"""
        from datapilot_semantic.metadata.datasource_pool import build_connection_url
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        config = DataConnectionConfig(
            type="postgresql",
            host="db.example.com",
            port=5432,
            database="mydb",
            username="user",
            password="pwd",
        )
        url = build_connection_url(config)
        assert url.startswith("postgresql+psycopg2://user:")
        assert "db.example.com:5432" in url

    def test_clickhouse_url(self) -> None:
        """测试 ClickHouse 连接 URL 构建。"""
        from datapilot_semantic.metadata.datasource_pool import build_connection_url
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        config = DataConnectionConfig(
            type="clickhouse",
            host="ch.local",
            port=8123,
            database="events",
            username="default",
            password="",
        )
        url = build_connection_url(config)
        assert url.startswith("clickhouse+native://default:")

    def test_doris_url(self) -> None:
        """测试 Doris 连接 URL（使用 MySQL 协议）。"""
        from datapilot_semantic.metadata.datasource_pool import build_connection_url
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        config = DataConnectionConfig(
            type="doris",
            host="doris.local",
            port=9030,
            database="dwh",
            username="root",
            password="pwd",
        )
        url = build_connection_url(config)
        assert url.startswith("mysql+pymysql://root:")

    def test_api_type_raises(self) -> None:
        """测试 API 类型抛出 ValueError。"""
        from datapilot_semantic.metadata.datasource_pool import build_connection_url
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        config = DataConnectionConfig(
            type="api",
            host="http://api.example.com",
            port=80,
            database="",
            username="",
            password="",
        )
        with pytest.raises(ValueError, match="API"):
            build_connection_url(config)

    def test_unsupported_type_raises(self) -> None:
        """测试不支持的类型抛出 ValueError。"""
        from datapilot_semantic.metadata.datasource_pool import build_connection_url
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        config = DataConnectionConfig(
            type="oracle",
            host="localhost",
            port=1521,
            database="orcl",
            username="sys",
            password="pwd",
        )
        with pytest.raises(ValueError, match="不支持"):
            build_connection_url(config)

    def test_special_chars_in_password(self) -> None:
        """测试密码中的特殊字符被正确编码。"""
        from datapilot_semantic.metadata.datasource_pool import build_connection_url
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        config = DataConnectionConfig(
            type="mysql",
            host="localhost",
            port=3306,
            database="db",
            username="user",
            password="p@ss:word/123",
        )
        url = build_connection_url(config)
        # 特殊字符应该被 URL 编码
        assert "p%40ss%3Aword%2F123" in url


class TestDataSourcePool:
    """DataSourcePool 连接池管理测试。"""

    def test_get_pool_manager_singleton(self) -> None:
        """测试全局连接池管理器单例。"""
        from datapilot_semantic.metadata.datasource_pool import get_pool_manager

        mgr1 = get_pool_manager()
        mgr2 = get_pool_manager()
        assert mgr1 is mgr2

    def test_dispose_all(self) -> None:
        """测试释放所有连接池。"""
        from datapilot_semantic.metadata.datasource_pool import DataSourcePool

        pool = DataSourcePool()
        pool.dispose_all()  # 不应抛出异常


class TestTestConnection:
    """连接测试函数测试。"""

    def test_api_type_skips_test(self) -> None:
        """测试 API 类型跳过连接测试。"""
        from datapilot_semantic.metadata.datasource_pool import test_connection
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        config = DataConnectionConfig(
            type="api",
            host="http://api.example.com",
            port=80,
            database="",
            username="",
            password="",
        )
        assert test_connection(config) is True

    def test_connection_failure(self) -> None:
        """测试连接失败返回 False。"""
        from datapilot_semantic.metadata.datasource_pool import test_connection
        from datapilot_semantic.metadata.schemas import DataConnectionConfig

        config = DataConnectionConfig(
            type="mysql",
            host="192.0.2.1",  # 测试用 IP，不可达
            port=3306,
            database="nonexistent",
            username="test",
            password="test",
        )
        result = test_connection(config)
        assert result is False
