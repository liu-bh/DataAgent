"""ClickHouse 连接器。

使用 asynch（异步 ClickHouse 驱动）创建连接池。

用法::

    connector = ClickHouseConnector(
        datasource_id="ds-004",
        host="127.0.0.1",
        port=9000,
        database="mydb",
        username="default",
        password="secret",
    )
    await connector.connect()
    result = await connector.execute("SELECT * FROM events LIMIT 10")
"""

from __future__ import annotations

import time
from typing import Any

import asynch
import structlog

from datapilot_queryexec.connectors.base import BaseConnector, ConnectorHealth, ExecuteResult

logger = structlog.get_logger(__name__)


class ClickHouseConnector(BaseConnector):
    """ClickHouse 异步连接器。

    基于 asynch 连接池实现，连接池大小默认 15。
    """

    def __init__(
        self,
        datasource_id: str,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        pool_size: int = 15,
    ) -> None:
        super().__init__(datasource_id, host, port, database, username, password, pool_size)
        self._pool: asynch.Pool | None = None

    @property
    def dialect(self) -> str:
        """返回 ClickHouse 方言标识。"""
        return "clickhouse"

    async def connect(self) -> None:
        """创建 ClickHouse 连接池。"""
        if self._connected and self._pool is not None:
            logger.warning(
                "ClickHouse 连接池已存在，跳过重复创建",
                datasource_id=self._datasource_id,
            )
            return

        self._pool = await asynch.create_pool(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._username,
            password=self._password,
            minsize=1,
            maxsize=self._pool_size,
        )
        self._connected = True
        logger.info(
            "ClickHouse 连接池创建成功",
            datasource_id=self._datasource_id,
            host=self._host,
            port=self._port,
            database=self._database,
            pool_size=self._pool_size,
        )

    async def disconnect(self) -> None:
        """关闭 ClickHouse 连接池。"""
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            self._connected = False
            logger.info(
                "ClickHouse 连接池已关闭",
                datasource_id=self._datasource_id,
            )

    async def _do_execute(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> ExecuteResult:
        """执行 SQL 查询。

        Args:
            sql: SQL 语句。
            params: 查询参数字典，asynch 使用 {param} 占位符。

        Returns:
            执行结果。

        Raises:
            RuntimeError: 连接池未初始化。
        """
        if self._pool is None:
            raise RuntimeError(
                f"数据源 {self._datasource_id} 的 ClickHouse 连接池未初始化，请先调用 connect()"
            )

        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            await cursor.execute(sql, params or {})

            # 获取列名
            columns = cursor.column_names if cursor.column_names else []

            # 获取所有行
            rows_raw = await cursor.fetchall()
            row_dicts = [dict(zip(columns, row, strict=True)) for row in rows_raw]

            return ExecuteResult(
                columns=list(columns),
                rows=row_dicts,
                row_count=len(row_dicts),
                execution_time_ms=0.0,
            )

    async def execute(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> ExecuteResult:
        """执行 SQL 并返回结果（带计时）。"""
        return await self._execute_with_timing(sql, params)

    async def health_check(self) -> ConnectorHealth:
        """执行 SELECT 1 健康检查。

        Returns:
            连接器健康状态。
        """
        start_time = time.perf_counter()
        try:
            if self._pool is None:
                return ConnectorHealth(
                    healthy=False,
                    error="连接池未初始化",
                )

            async with self._pool.acquire() as conn:
                cursor = await conn.cursor()
                await cursor.execute("SELECT 1")
                await cursor.fetchall()

            latency_ms = (time.perf_counter() - start_time) * 1000

            # asynch Pool 对象获取连接池信息
            pool_size = self._pool_size
            pool_used = 0  # asynch 未提供便捷的已用连接数 API

            return ConnectorHealth(
                healthy=True,
                latency_ms=latency_ms,
                pool_size=pool_size,
                pool_used=pool_used,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "ClickHouse 健康检查失败",
                datasource_id=self._datasource_id,
                error=str(exc),
                elapsed_ms=latency_ms,
            )
            return ConnectorHealth(
                healthy=False,
                latency_ms=latency_ms,
                error=str(exc),
            )
