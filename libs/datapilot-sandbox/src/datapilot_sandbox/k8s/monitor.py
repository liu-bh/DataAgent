"""Pod 池资源监控。

监控 Pod 池使用率、延迟、错误率，生成告警并给出扩缩容建议。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from datapilot_sandbox.k8s.pool import PodPool, PoolStats


@dataclass
class PoolAlert:
    """池告警信息。"""

    level: str  # info / warning / critical
    message: str
    timestamp: float
    pod_id: str = ""


class PoolMonitor:
    """Pod 池资源监控。

    监控指标：
    - 连接池使用率（(total - ready) / total_pods）
    - 平均执行延迟
    - 错误率
    - 自动扩缩策略
    """

    def __init__(self, pool: PodPool) -> None:
        """初始化监控器。

        Args:
            pool: Pod 池实例。
        """
        self._pool = pool
        self._alerts_history: list[PoolAlert] = []

    @property
    def alerts_history(self) -> list[PoolAlert]:
        """获取历史告警列表。"""
        return list(self._alerts_history)

    async def get_stats(self) -> PoolStats:
        """获取当前池统计信息。"""
        return await self._pool.get_stats()

    async def check_and_alert(self) -> list[PoolAlert]:
        """检查资源使用情况，返回告警列表。

        告警规则：
        - 使用率 > 80% -> warning
        - 使用率 > 95% -> critical，建议扩容
        - 使用率 < 20% -> info，建议缩容
        - 错误率 > 10% -> warning

        使用率计算：(total_pods - ready_pods) / total_pods
        """
        stats = await self._pool.get_stats()
        alerts: list[PoolAlert] = []
        now = time.time()

        # 计算使用率
        if stats.total_pods > 0:
            usage_rate = (stats.total_pods - stats.ready_pods) / stats.total_pods
        else:
            usage_rate = 0.0

        # 使用率过高
        if usage_rate > 0.95:
            alert = PoolAlert(
                level="critical",
                message=f"Pod 池使用率 {usage_rate:.1%}，超过 95% 阈值，建议立即扩容",
                timestamp=now,
            )
            alerts.append(alert)
        elif usage_rate > 0.80:
            alert = PoolAlert(
                level="warning",
                message=f"Pod 池使用率 {usage_rate:.1%}，超过 80% 阈值，建议扩容",
                timestamp=now,
            )
            alerts.append(alert)

        # 使用率过低
        if usage_rate < 0.20 and stats.total_pods > 0:
            alert = PoolAlert(
                level="info",
                message=f"Pod 池使用率 {usage_rate:.1%}，低于 20% 阈值，建议缩容",
                timestamp=now,
            )
            alerts.append(alert)

        # 错误率检查
        if stats.total_tasks_executed > 0:
            error_rate = stats.error_count / stats.total_tasks_executed
        else:
            error_rate = 0.0

        if error_rate > 0.10:
            alert = PoolAlert(
                level="warning",
                message=f"Pod 池错误率 {error_rate:.1%}，超过 10% 阈值，请检查执行环境",
                timestamp=now,
            )
            alerts.append(alert)

        # 记录告警历史
        self._alerts_history.extend(alerts)
        # 仅保留最近 200 条告警
        if len(self._alerts_history) > 200:
            self._alerts_history = self._alerts_history[-200:]

        return alerts

    async def should_scale_up(self) -> bool:
        """是否需要扩容。

        条件：使用率 > 80%。
        """
        stats = await self._pool.get_stats()
        if stats.total_pods == 0:
            return True
        usage_rate = (stats.total_pods - stats.ready_pods) / stats.total_pods
        return usage_rate > 0.80

    async def should_scale_down(self) -> bool:
        """是否需要缩容。

        条件：使用率 < 20% 且池中有超过 1 个 Pod。
        """
        stats = await self._pool.get_stats()
        if stats.total_pods <= 1:
            return False
        usage_rate = (stats.total_pods - stats.ready_pods) / stats.total_pods
        return usage_rate < 0.20
