"""Pod 池管理抽象接口。

定义 PodPool 接口和 PoolStats 数据结构。
所有 Pod 池实现（本地模拟 / K8s 真实池）都应继承 PodPool。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from datapilot_sandbox.k8s.lifecycle import PodInfo


@dataclass
class PoolStats:
    """Pod 池统计信息。"""

    total_pods: int = 0
    ready_pods: int = 0
    busy_pods: int = 0
    creating_pods: int = 0
    warm_pods: int = 0  # 预热但未使用的 Pod
    avg_latency_ms: float = 0.0
    total_tasks_executed: int = 0
    error_count: int = 0


class PodPool(ABC):
    """Pod 池管理接口。"""

    @abstractmethod
    async def acquire(self) -> PodInfo:
        """获取一个可用 Pod（优先复用空闲 Pod）。

        Raises:
            RuntimeError: 没有可用 Pod 时抛出异常。
        """

    @abstractmethod
    async def release(self, pod_id: str) -> bool:
        """释放 Pod 回池中，返回是否成功。"""

    @abstractmethod
    async def warmup(self, count: int = 3) -> int:
        """预热指定数量的 Pod，返回实际预热的数量。"""

    @abstractmethod
    async def cleanup(self, max_idle_seconds: float = 300) -> int:
        """清理空闲超过指定时间的 Pod，返回清理数量。"""

    @abstractmethod
    async def get_stats(self) -> PoolStats:
        """获取池统计信息。"""

    @abstractmethod
    async def health_check(self) -> bool:
        """检查 Pod 池健康状态。"""
