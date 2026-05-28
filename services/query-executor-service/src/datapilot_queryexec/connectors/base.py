"""连接器抽象基类。

定义所有数据源连接器的统一接口，包括连接管理、SQL 执行和健康检查。
每个具体连接器（MySQL、PostgreSQL 等）必须继承 BaseConnector 并实现所有抽象方法。

用法::

    class MyConnector(BaseConnector):
        @property
        def dialect(self) -> str:
            return "mysql"

        async def connect(self) -> None:
            ...

        async def disconnect(self) -> None:
            ...

        async def execute(self, sql: str, params: dict[str, Any] | None = None) -> ExecuteResult:
            ...

        async def health_check(self) -> ConnectorHealth:
            ...
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ExecuteResult:
    """SQL 执行结果。

    Attributes:
        columns: 查询结果列名列表。
        rows: 查询结果行列表，每行为列名到值的映射。
        row_count: 影响行数或返回行数。
        execution_time_ms: 执行耗时（毫秒）。
        error: 错误信息，为空字符串表示执行成功。
    """

    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_time_ms: float
    error: str = ""


@dataclass
class ConnectorHealth:
    """连接器健康状态。

    Attributes:
        healthy: 是否健康。
        latency_ms: 健康检查延迟（毫秒）。
        pool_size: 连接池总大小。
        pool_used: 连接池已使用连接数。
        error: 错误信息。
    """

    healthy: bool
    latency_ms: float = 0.0
    pool_size: int = 0
    pool_used: int = 0
    error: str = ""


class BaseConnector(abc.ABC):
    """数据源连接器抽象基类。

    Args:
        datasource_id: 数据源唯一标识。
        host: 数据库主机地址。
        port: 数据库端口。
        database: 数据库名称。
        username: 用户名。
        password: 密码。
        pool_size: 连接池大小。
    """

    def __init__(
        self,
        datasource_id: str,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        pool_size: int = 10,
    ) -> None:
        self._datasource_id = datasource_id
        self._host = host
        self._port = port
        self._database = database
        self._username = username
        self._password = password
        self._pool_size = pool_size
        self._connected = False
        logger.info(
            "连接器初始化",
            datasource_id=datasource_id,
            host=host,
            port=port,
            database=database,
            pool_size=pool_size,
        )

    @property
    def datasource_id(self) -> str:
        """数据源唯一标识。"""
        return self._datasource_id

    @property
    def host(self) -> str:
        """数据库主机地址。"""
        return self._host

    @property
    def port(self) -> int:
        """数据库端口。"""
        return self._port

    @property
    def database(self) -> str:
        """数据库名称。"""
        return self._database

    @property
    def connected(self) -> bool:
        """是否已连接。"""
        return self._connected

    @property
    @abc.abstractmethod
    def dialect(self) -> str:
        """数据源方言标识。"""
        ...

    @abc.abstractmethod
    async def connect(self) -> None:
        """建立连接池。"""
        ...

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """关闭连接池。"""
        ...

    @abc.abstractmethod
    async def execute(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> ExecuteResult:
        """执行 SQL 并返回结果。

        Args:
            sql: 要执行的 SQL 语句。
            params: 参数化查询参数。

        Returns:
            执行结果。
        """
        ...

    @abc.abstractmethod
    async def health_check(self) -> ConnectorHealth:
        """执行健康检查。

        Returns:
            连接器健康状态。
        """
        ...

    async def _execute_with_timing(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> ExecuteResult:
        """带计时的 SQL 执行包装方法。

        子类可在 execute 方法中调用此方法以自动记录执行时间。

        Args:
            sql: SQL 语句。
            params: 查询参数。

        Returns:
            执行结果。
        """
        start_time = time.perf_counter()
        try:
            result = await self._do_execute(sql, params)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            result.execution_time_ms = elapsed_ms
            logger.debug(
                "SQL 执行完成",
                datasource_id=self._datasource_id,
                dialect=self.dialect,
                row_count=result.row_count,
                elapsed_ms=elapsed_ms,
            )
            return result
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "SQL 执行失败",
                datasource_id=self._datasource_id,
                dialect=self.dialect,
                elapsed_ms=elapsed_ms,
                error=str(exc),
            )
            return ExecuteResult(
                columns=[],
                rows=[],
                row_count=0,
                execution_time_ms=elapsed_ms,
                error=str(exc),
            )

    async def _do_execute(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> ExecuteResult:
        """实际执行 SQL 的方法，由子类实现。

        Args:
            sql: SQL 语句。
            params: 查询参数。

        Returns:
            执行结果（不含 timing 信息，由调用方填充）。
        """
        raise NotImplementedError("子类必须实现 _do_execute 或覆盖 execute 方法")
