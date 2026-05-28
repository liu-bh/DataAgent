"""PostgreSQL 连接器。

使用 asyncpg 创建异步连接池，支持参数化查询防止 SQL 注入。

用法::

    connector = PostgreSQLConnector(
        datasource_id="ds-002",
        host="127.0.0.1",
        port=5432,
        database="mydb",
        username="postgres",
        password="secret",
    )
    await connector.connect()
    result = await connector.execute("SELECT * FROM users WHERE id = $1", {"id": 1})
"""

from __future__ import annotations

import time
from typing import Any

import asyncpg
import structlog

from datapilot_queryexec.connectors.base import BaseConnector, ConnectorHealth, ExecuteResult

logger = structlog.get_logger(__name__)


class PostgreSQLConnector(BaseConnector):
    """PostgreSQL 异步连接器。

    基于 asyncpg 连接池实现，支持参数化查询。
    asyncpg 使用 $1, $2 占位符语法。
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
        super().__init__(datasource_id, host, port, database, username, password, pool_size)
        self._pool: asyncpg.Pool | None = None

    @property
    def dialect(self) -> str:
        """返回 PostgreSQL 方言标识。"""
        return "postgresql"

    async def connect(self) -> None:
        """创建 PostgreSQL 连接池。"""
        if self._connected and self._pool is not None:
            logger.warning(
                "PostgreSQL 连接池已存在，跳过重复创建",
                datasource_id=self._datasource_id,
            )
            return

        self._pool = await asyncpg.create_pool(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._username,
            password=self._password,
            min_size=1,
            max_size=self._pool_size,
        )
        self._connected = True
        logger.info(
            "PostgreSQL 连接池创建成功",
            datasource_id=self._datasource_id,
            host=self._host,
            port=self._port,
            database=self._database,
            pool_size=self._pool_size,
        )

    async def disconnect(self) -> None:
        """关闭 PostgreSQL 连接池。"""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._connected = False
            logger.info(
                "PostgreSQL 连接池已关闭",
                datasource_id=self._datasource_id,
            )

    async def _do_execute(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> ExecuteResult:
        """执行 SQL 查询。

        Args:
            sql: SQL 语句。asyncpg 原生使用 $1, $2 占位符。
                 如果传入 params，则通过 dict cursor 方式执行。
            params: 查询参数字典。asyncpg 需要 positional args，
                    这里将 dict 值按 key 排序后转为 list。

        Returns:
            执行结果。

        Raises:
            RuntimeError: 连接池未初始化。
        """
        if self._pool is None:
            raise RuntimeError(
                f"数据源 {self._datasource_id} 的 PostgreSQL 连接池未初始化，请先调用 connect()"
            )

        async with self._pool.acquire() as conn:
            # 将 params 字典转为有序的 positional 参数列表
            if params:
                # 按 key 排序以确保参数顺序一致
                sorted_keys = sorted(params.keys())
                args = [params[k] for k in sorted_keys]
            else:
                args = []

            # 使用 Record 对象获取列名和行数据
            rows_data = await conn.fetch(sql, *args)

            if rows_data:
                columns = list(rows_data[0].keys())
                row_dicts = [dict(row) for row in rows_data]
            else:
                columns: list[str] = []
                row_dicts: list[dict[str, Any]] = []

            return ExecuteResult(
                columns=columns,
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
                await conn.fetchval("SELECT 1")

            latency_ms = (time.perf_counter() - start_time) * 1000
            pool_size = self._pool._maxsize if self._pool else 0  # noqa: SLF001
            pool_idle = self._pool._idle.size if self._pool else 0  # noqa: SLF001
            pool_used = pool_size - pool_idle

            return ConnectorHealth(
                healthy=True,
                latency_ms=latency_ms,
                pool_size=pool_size,
                pool_used=pool_used,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "PostgreSQL 健康检查失败",
                datasource_id=self._datasource_id,
                error=str(exc),
                elapsed_ms=latency_ms,
            )
            return ConnectorHealth(
                healthy=False,
                latency_ms=latency_ms,
                error=str(exc),
            )
