"""多组件健康检查。

支持注册自定义检查函数，内置数据库、Redis、LLM 检查。
Phase1 阶段使用模拟实现。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

import structlog

logger = structlog.get_logger(__name__)


class HealthStatus(StrEnum):
    """组件健康状态。"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """单个组件健康检查结果。"""

    component: str
    status: HealthStatus
    latency_ms: float = 0.0
    message: str = ""
    details: dict = field(default_factory=dict)


class HealthChecker:
    """多组件健康检查器。

    使用方式::

        checker = HealthChecker()
        result = await checker.check_all()
    """

    def __init__(self) -> None:
        self._checks: dict[str, Callable[[], Awaitable[HealthCheckResult]]] = {}
        # 注册内置检查
        self._checks["database"] = self.check_database
        self._checks["redis"] = self.check_redis
        self._checks["llm"] = self.check_llm

    def register(self, name: str, check_fn: Callable[[], Awaitable[HealthCheckResult]]) -> None:
        """注册一个健康检查函数。

        Args:
            name: 组件名称，需唯一。
            check_fn: 异步检查函数，返回 HealthCheckResult。
        """
        self._checks[name] = check_fn

    def unregister(self, name: str) -> None:
        """移除指定组件的健康检查。

        Args:
            name: 组件名称。
        """
        self._checks.pop(name, None)

    async def check_all(self) -> dict[str, HealthCheckResult]:
        """执行所有健康检查，返回各组件状态。

        并发执行所有注册的检查函数，单个检查失败不影响其他检查。

        Returns:
            各组件名称到检查结果的映射。
        """
        results: dict[str, HealthCheckResult] = {}

        async def _safe_check(
            name: str, check_fn: Callable[[], Awaitable[HealthCheckResult]]
        ) -> tuple[str, HealthCheckResult]:
            try:
                result = await check_fn()
                return name, result
            except Exception as exc:
                logger.warning("健康检查异常", component=name, error=str(exc))
                return name, HealthCheckResult(
                    component=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"检查异常: {exc}",
                )

        tasks = [_safe_check(name, fn) for name, fn in self._checks.items()]
        gathered = await asyncio.gather(*tasks)
        results = dict(gathered)
        return results

    async def check_database(self) -> HealthCheckResult:
        """数据库健康检查（Phase1 模拟实现）。

        实际实现会连接数据库执行 SELECT 1，
        Phase1 阶段返回模拟结果。
        """
        start = time.perf_counter()
        try:
            # 模拟数据库查询延迟
            await asyncio.sleep(0.001)
            latency_ms = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                component="database",
                status=HealthStatus.HEALTHY,
                latency_ms=latency_ms,
                message="Phase1 模拟检查通过",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                component="database",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                message=f"数据库检查失败: {exc}",
            )

    async def check_redis(self) -> HealthCheckResult:
        """Redis 健康检查（Phase1 模拟实现）。

        实际实现会执行 PING 命令，
        Phase1 阶段返回模拟结果。
        """
        start = time.perf_counter()
        try:
            # 模拟 Redis PING 延迟
            await asyncio.sleep(0.001)
            latency_ms = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                component="redis",
                status=HealthStatus.HEALTHY,
                latency_ms=latency_ms,
                message="Phase1 模拟检查通过",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                component="redis",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                message=f"Redis 检查失败: {exc}",
            )

    async def check_llm(self) -> HealthCheckResult:
        """LLM 服务健康检查（Phase1 模拟实现）。

        实际实现会发送简单 prompt 测试连通性，
        Phase1 阶段返回模拟结果。
        """
        start = time.perf_counter()
        try:
            # 模拟 LLM API 调用延迟
            await asyncio.sleep(0.001)
            latency_ms = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                component="llm",
                status=HealthStatus.HEALTHY,
                latency_ms=latency_ms,
                message="Phase1 模拟检查通过",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                component="llm",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                message=f"LLM 检查失败: {exc}",
            )

    @staticmethod
    def get_overall_status(results: dict[str, HealthCheckResult]) -> HealthStatus:
        """根据各组件状态计算整体状态。

        规则：
        - 全部 healthy → healthy
        - 任一 unhealthy → unhealthy
        - 否则 → degraded

        Args:
            results: 各组件健康检查结果。

        Returns:
            整体健康状态。
        """
        if not results:
            return HealthStatus.UNHEALTHY

        statuses = {r.status for r in results.values()}

        if statuses == {HealthStatus.HEALTHY}:
            return HealthStatus.HEALTHY
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        return HealthStatus.DEGRADED
