"""数据源健康监控。

定期检查数据源的可用性，支持 TCP 端口探测和 Connector 级别探测，
并记录查询统计信息。
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import UTC, datetime
from typing import Any

import structlog

from .circuit import DataSourceCircuitBreaker
from .models import CircuitState, DataSourceStatus

logger = structlog.get_logger(__name__)

# 默认健康检查超时时间（秒）
_DEFAULT_CHECK_TIMEOUT = 5.0


class DataSourceMonitor:
    """定期健康检查数据源。

    内部使用 dict 存储数据源状态。如果注册时提供了 connector，
    则通过 connector 执行健康检查（如 SELECT 1）；
    否则仅做 TCP 端口探测。
    """

    def __init__(self, check_interval_seconds: int = 30) -> None:
        """初始化监控器。

        Args:
            check_interval_seconds: 定期检查间隔（秒）。
        """
        self._check_interval = check_interval_seconds
        self._datasources: dict[str, DataSourceStatus] = {}
        self._connectors: dict[str, Any] = {}
        self._circuit_breaker = DataSourceCircuitBreaker()
        self._periodic_task: asyncio.Task[None] | None = None

    def register(
        self,
        datasource_id: str,
        name: str,
        dialect: str,
        host: str,
        port: int,
        connector: Any = None,
    ) -> None:
        """注册数据源。

        Args:
            datasource_id: 数据源唯一标识。
            name: 数据源名称。
            dialect: 数据库方言（如 postgres, mysql）。
            host: 主机地址。
            port: 端口号。
            connector: 可选的连接器实例，用于执行健康检查。
        """
        status = DataSourceStatus(
            datasource_id=datasource_id,
            name=name,
            dialect=dialect,
            host=host,
            port=port,
            healthy=True,
            latency_ms=0.0,
            pool_size=0,
            pool_used=0,
            circuit_state=CircuitState.CLOSED,
            last_check_at=None,
            consecutive_failures=0,
            total_queries=0,
            error_queries=0,
            avg_latency_ms=0.0,
        )
        self._datasources[datasource_id] = status
        if connector is not None:
            self._connectors[datasource_id] = connector

        logger.info(
            "数据源注册到监控",
            datasource_id=datasource_id,
            name=name,
            dialect=dialect,
            has_connector=connector is not None,
        )

    def unregister(self, datasource_id: str) -> None:
        """注销数据源。

        Args:
            datasource_id: 数据源唯一标识。
        """
        self._datasources.pop(datasource_id, None)
        self._connectors.pop(datasource_id, None)
        logger.info("数据源从监控注销", datasource_id=datasource_id)

    async def check_one(self, datasource_id: str) -> DataSourceStatus:
        """检查单个数据源健康状态。

        如果有 connector 则通过 connector 执行健康检查，
        否则进行 TCP 端口探测。

        Args:
            datasource_id: 数据源唯一标识。

        Returns:
            更新后的数据源状态。

        Raises:
            KeyError: 数据源未注册。
        """
        status = self._datasources.get(datasource_id)
        if status is None:
            raise KeyError(f"数据源 {datasource_id} 未注册")

        connector = self._connectors.get(datasource_id)
        start = time.monotonic()

        try:
            if connector is not None:
                await self._check_via_connector(connector)
            else:
                await self._check_tcp_port(status.host, status.port)

            latency_ms = (time.monotonic() - start) * 1000

            # 更新状态
            status.healthy = True
            status.latency_ms = latency_ms
            status.last_check_at = datetime.now(UTC)
            status.consecutive_failures = 0

            # 通知熔断器
            self._circuit_breaker.record_success(datasource_id)

            logger.debug(
                "数据源健康检查通过",
                datasource_id=datasource_id,
                latency_ms=round(latency_ms, 2),
            )

        except Exception as exc:
            latency_ms = (time.monotonic() - start) * 1000

            status.healthy = False
            status.latency_ms = latency_ms
            status.last_check_at = datetime.now(UTC)
            status.consecutive_failures += 1

            # 通知熔断器
            self._circuit_breaker.record_failure(datasource_id)

            logger.warning(
                "数据源健康检查失败",
                datasource_id=datasource_id,
                error=str(exc),
                latency_ms=round(latency_ms, 2),
                consecutive_failures=status.consecutive_failures,
            )

        # 更新熔断器状态
        status.circuit_state = self._circuit_breaker.get_state(datasource_id).value

        return status

    async def check_all(self) -> list[DataSourceStatus]:
        """检查所有数据源健康状态。

        Returns:
            所有数据源的状态列表。
        """
        results: list[DataSourceStatus] = []
        for datasource_id in list(self._datasources.keys()):
            result = await self.check_one(datasource_id)
            results.append(result)
        return results

    def get_status(self, datasource_id: str) -> DataSourceStatus | None:
        """获取数据源当前状态（不执行检查）。

        Args:
            datasource_id: 数据源唯一标识。

        Returns:
            数据源状态，未注册时返回 None。
        """
        return self._datasources.get(datasource_id)

    def get_all_statuses(self) -> list[DataSourceStatus]:
        """获取所有数据源当前状态。

        Returns:
            所有数据源的状态列表。
        """
        return list(self._datasources.values())

    async def start_periodic_check(self) -> None:
        """启动定期检查（asyncio.create_task）。"""
        if self._periodic_task is not None and not self._periodic_task.done():
            logger.warning("定期健康检查已在运行中")
            return

        self._periodic_task = asyncio.create_task(self._periodic_loop())
        logger.info(
            "定期健康检查已启动",
            interval_seconds=self._check_interval,
        )

    async def stop_periodic_check(self) -> None:
        """停止定期检查。"""
        if self._periodic_task is not None:
            self._periodic_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._periodic_task
            self._periodic_task = None
            logger.info("定期健康检查已停止")

    def record_query(self, datasource_id: str, success: bool, latency_ms: float) -> None:
        """记录查询结果（用于统计）。

        Args:
            datasource_id: 数据源唯一标识。
            success: 查询是否成功。
            latency_ms: 查询延迟（毫秒）。
        """
        status = self._datasources.get(datasource_id)
        if status is None:
            logger.warning(
                "记录查询结果时数据源未注册",
                datasource_id=datasource_id,
            )
            return

        status.total_queries += 1
        if not success:
            status.error_queries += 1

        # 计算移动平均延迟
        n = status.total_queries
        status.avg_latency_ms = (status.avg_latency_ms * (n - 1) + latency_ms) / n

        # 通知熔断器
        if success:
            self._circuit_breaker.record_success(datasource_id)
        else:
            self._circuit_breaker.record_failure(datasource_id)

        # 更新熔断器状态
        status.circuit_state = self._circuit_breaker.get_state(datasource_id).value

    async def _periodic_loop(self) -> None:
        """定期检查循环。"""
        while True:
            await asyncio.sleep(self._check_interval)
            try:
                await self.check_all()
            except Exception:
                logger.exception("定期健康检查执行异常")

    @staticmethod
    async def _check_via_connector(connector: Any) -> None:
        """通过 connector 执行健康检查。

        要求 connector 实现 ``health_check()`` 异步方法。
        """
        if hasattr(connector, "health_check"):
            result = await connector.health_check()
            if not result:
                raise ConnectionError("connector 健康检查返回 False")
        else:
            raise AttributeError("connector 未实现 health_check() 方法")

    @staticmethod
    async def _check_tcp_port(host: str, port: int) -> None:
        """TCP 端口探测。

        Args:
            host: 主机地址。
            port: 端口号。

        Raises:
            ConnectionError: 连接失败。
        """
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=_DEFAULT_CHECK_TIMEOUT,
            )
            writer.close()
            await writer.wait_closed()
        except (OSError, TimeoutError) as exc:
            raise ConnectionError(f"TCP 端口探测失败: {host}:{port} - {exc}") from exc
