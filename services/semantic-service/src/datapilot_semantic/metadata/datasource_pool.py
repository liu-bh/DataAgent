"""数据源连接池管理模块。

提供数据源连接工厂，支持 MySQL/PostgreSQL/Doris/ClickHouse。
使用 sqlalchemy create_engine 创建同步连接（读取 information_schema 用同步连接）。
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from datapilot_semantic.metadata.schemas import DataConnectionConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 密码加密工具
# ---------------------------------------------------------------------------


def encrypt_password(password: str, salt: str = "datapilot-salt-v1") -> str:
    """使用 SHA256 加密密码。

    生产环境建议使用 Fernet 对称加密，此处使用 SHA256 + salt 作为最小实现。

    Args:
        password: 明文密码。
        salt: 加密盐值。

    Returns:
        加密后的密码哈希值（十六进制字符串）。
    """
    salted = f"{salt}:{password}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


def verify_password(password: str, hashed: str, salt: str = "datapilot-salt-v1") -> bool:
    """验证密码是否匹配。

    Args:
        password: 明文密码。
        hashed: 加密后的密码哈希值。
        salt: 加密盐值（必须与加密时一致）。

    Returns:
        密码是否匹配。
    """
    return encrypt_password(password, salt) == hashed


# ---------------------------------------------------------------------------
# 方言 -> 默认端口 & 驱动映射
# ---------------------------------------------------------------------------

_DIALECT_DEFAULT_PORT: dict[str, int] = {
    "mysql": 3306,
    "postgresql": 5432,
    "doris": 9030,
    "starrocks": 9030,
    "clickhouse": 8123,
    "api": 0,  # API 类型不需要数据库连接
}

_DIALECT_DRIVER: dict[str, str] = {
    "mysql": "mysql+pymysql",
    "postgresql": "postgresql+psycopg2",
    "doris": "mysql+pymysql",
    "starrocks": "mysql+pymysql",
    "clickhouse": "clickhouse+native",
}


# ---------------------------------------------------------------------------
# 连接 URL 构建
# ---------------------------------------------------------------------------


def build_connection_url(config: DataConnectionConfig) -> str:
    """根据连接配置构建 SQLAlchemy 连接 URL。

    Args:
        config: 数据源连接配置。

    Returns:
        SQLAlchemy 连接 URL 字符串。

    Raises:
        ValueError: 不支持的数据源类型。
    """
    ds_type = config.type.lower()

    if ds_type == "api":
        raise ValueError("API 类型的数据源不支持数据库连接")

    driver = _DIALECT_DRIVER.get(ds_type)
    if driver is None:
        raise ValueError(f"不支持的数据源类型: {ds_type}")

    # URL 编码密码中的特殊字符
    encoded_password = quote_plus(config.password)
    url = f"{driver}://{config.username}:{encoded_password}@{config.host}:{config.port}/{config.database}"
    return url


# ---------------------------------------------------------------------------
# 连接工厂
# ---------------------------------------------------------------------------


class DataSourcePool:
    """数据源连接池管理器。

    为每个数据源维护独立的同步连接池。
    连接池在内部缓存，避免重复创建。

    用法::

        pool_manager = DataSourcePool()
        engine = pool_manager.get_engine(config)
        # 使用 engine 执行查询...
        pool_manager.dispose(config.datasource_id)
    """

    def __init__(self) -> None:
        self._engines: dict[str, Engine] = {}

    def get_engine(
        self,
        config: DataConnectionConfig,
        *,
        pool_size: int = 3,
        max_overflow: int = 5,
        pool_recycle: int = 3600,
        echo: bool = False,
    ) -> Engine:
        """获取或创建数据源连接 Engine。

        Args:
            config: 数据源连接配置。
            pool_size: 连接池大小。
            max_overflow: 连接池最大溢出数。
            pool_recycle: 连接回收时间（秒）。
            echo: 是否输出 SQL 日志。

        Returns:
            SQLAlchemy Engine 实例。
        """
        # 使用唯一键标识连接池
        cache_key = f"{config.type}://{config.host}:{config.port}/{config.database}"

        if cache_key in self._engines:
            return self._engines[cache_key]

        url = build_connection_url(config)

        engine = create_engine(
            url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,
            echo=echo,
            connect_args={"connect_timeout": 10},
        )

        self._engines[cache_key] = engine
        logger.info(
            "创建数据源连接池: type=%s, host=%s, port=%s, database=%s",
            config.type,
            config.host,
            config.port,
            config.database,
        )
        return engine

    def dispose(self, cache_key: str) -> None:
        """释放指定连接池。

        Args:
            cache_key: 连接池缓存键。
        """
        engine = self._engines.pop(cache_key, None)
        if engine is not None:
            engine.dispose()
            logger.info("释放数据源连接池: %s", cache_key)

    def dispose_all(self) -> None:
        """释放所有连接池。"""
        for key in list(self._engines.keys()):
            self.dispose(key)
        logger.info("已释放所有数据源连接池")


# ---------------------------------------------------------------------------
# 连接测试
# ---------------------------------------------------------------------------


def test_connection(config: DataConnectionConfig) -> bool:
    """测试数据源连接是否可用。

    创建临时连接并执行简单查询，成功返回 True，失败返回 False。

    Args:
        config: 数据源连接配置。

    Returns:
        连接是否成功。
    """
    ds_type = config.type.lower()

    if ds_type == "api":
        logger.info("API 类型数据源跳过连接测试")
        return True

    try:
        url = build_connection_url(config)
        # 使用短生命周期的引擎进行测试
        engine = create_engine(
            url,
            pool_size=1,
            max_overflow=0,
            pool_recycle=3600,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 10},
        )
        with engine.connect() as conn:
            # MySQL / Doris / StarRocks 使用 SELECT 1
            # PostgreSQL 使用 SELECT 1
            # ClickHouse 使用 SELECT 1
            conn.execute(text("SELECT 1"))
        engine.dispose()
        logger.info(
            "数据源连接测试成功: %s://%s:%s/%s",
            ds_type,
            config.host,
            config.port,
            config.database,
        )
        return True
    except Exception as e:
        logger.warning(
            "数据源连接测试失败: %s://%s:%s/%s, error=%s",
            ds_type,
            config.host,
            config.port,
            config.database,
            e,
        )
        return False


# ---------------------------------------------------------------------------
# 全局连接池实例
# ---------------------------------------------------------------------------

# 模块级单例，供 API 层使用
_pool_manager: DataSourcePool | None = None


def get_pool_manager() -> DataSourcePool:
    """获取全局连接池管理器实例。"""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = DataSourcePool()
    return _pool_manager
