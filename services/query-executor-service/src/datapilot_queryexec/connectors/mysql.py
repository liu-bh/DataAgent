"""MySQL 连接器。

使用 aiomysql 创建异步连接池，支持参数化查询防止 SQL 注入。

用法::

    connector = MySQLConnector(
        datasource_id="ds-001",
        host="127.0.0.1",
        port=3306,
        database="mydb",
        username="root",
        password="secret",
    )
    await connector.connect()
    result = await connector.execute("SELECT * FROM users WHERE id = %(id)s", {"id": 1})
"""

from __future__ import annotations

import time
from typing import Any

import aiomysql
import structlog

from datapilot_queryexec.connectors.base import BaseConnector, ConnectorHealth, ExecuteResult

logger = structlog.get_logger(__name__)


class MySQLConnector(BaseConnector):
    """MySQL 异步连接器。

    基于 aiomysql 连接池实现，支持参数化查询。
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
        self._pool: aiomysql.Pool | None = None

    @property
    def dialect(self) -> str:
        """返回 MySQL 方言标识。"""
        return "mysql"

    async def connect(self) -> None:
        """创建 MySQL 连接池。"""
        if self._connected and self._pool is not None:
            logger.warning(
                "MySQL 连接池已存在，跳过重复创建",
                datasource_id=self._datasource_id,
            )
            return

        self._pool = await aiomysql.create_pool(
            host=self._host,
            port=self._port,
            db=self._database,
            user=self._username,
            password=self._password,
            maxsize=self._pool_size,
            minsize=1,
            autocommit=True,
            charset="utf8mb4",
        )
        self._connected = True
        logger.info(
            "MySQL 连接池创建成功",
            datasource_id=self._datasource_id,
            host=self._host,
            port=self._port,
            database=self._database,
            pool_size=self._pool_size,
        )

    async def disconnect(self) -> None:
        """关闭 MySQL 连接池。"""
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            self._connected = False
            logger.info(
                "MySQL 连接池已关闭",
                datasource_id=self._datasource_id,
            )

    async def _do_execute(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> ExecuteResult:
        """执行 SQL 查询。

        Args:
            sql: SQL 语句，使用 %(name)s 占位符进行参数化。
            params: 查询参数字典。

        Returns:
            执行结果。

        Raises:
            RuntimeError: 连接池未初始化。
        """
        if self._pool is None:
            raise RuntimeError(
                f"数据源 {self._datasource_id} 的 MySQL 连接池未初始化，请先调用 connect()"
            )

        async with self._pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            # 获取列名
            columns = [desc[0] for desc in cur.description] if cur.description else []
            # 确保行数据为字典列表
            row_dicts = [dict(row) for row in rows]

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

            async with self._pool.acquire() as conn, conn.cursor() as cur:
                await cur.execute("SELECT 1")
                await cur.fetchone()

            latency_ms = (time.perf_counter() - start_time) * 1000
            pool_size = self._pool.size if self._pool else 0
            pool_used = self._pool.size - self._pool.freesize if self._pool else 0

            return ConnectorHealth(
                healthy=True,
                latency_ms=latency_ms,
                pool_size=pool_size,
                pool_used=pool_used,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "MySQL 健康检查失败",
                datasource_id=self._datasource_id,
                error=str(exc),
                elapsed_ms=latency_ms,
            )
            return ConnectorHealth(
                healthy=False,
                latency_ms=latency_ms,
                error=str(exc),
            )
