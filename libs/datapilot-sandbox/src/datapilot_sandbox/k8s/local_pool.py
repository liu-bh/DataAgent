"""本地模拟 Pod 池。

使用 PodLifecycle 管理虚拟 Pod 记录，不依赖 K8s 集群。
每个 "Pod" 对应一个 SandboxConfig + 唯一 ID，用于开发和测试环境。
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

from datapilot_sandbox.k8s.lifecycle import PodInfo, PodLifecycle, PodState
from datapilot_sandbox.k8s.pool import PodPool, PoolStats

if TYPE_CHECKING:
    from datapilot_sandbox.models import SandboxConfig


class LocalPodPool(PodPool):
    """本地模拟 Pod 池。

    实际上不创建 Pod，而是使用虚拟记录模拟
    Pod 的 acquire/release/warmup 等操作。
    每个 "Pod" 对应一个唯一 ID。

    用于开发和测试环境，不依赖 K8s。
    """

    def __init__(
        self,
        sandbox_executor: object | None = None,
        max_pods: int = 5,
        default_config: SandboxConfig | None = None,
    ) -> None:
        """初始化本地 Pod 池。

        Args:
            sandbox_executor: 沙箱执行器实例（本地模拟暂不使用）。
            max_pods: 池中最大 Pod 数量。
            default_config: 默认沙箱配置（本地模拟暂不使用）。
        """
        self._lifecycle = PodLifecycle()
        self._max_pods = max_pods
        self._sandbox_executor = sandbox_executor
        self._default_config = default_config
        self._total_tasks_executed = 0
        self._error_count = 0
        self._latencies: list[float] = []  # 最近获取延迟记录（毫秒）

    @property
    def lifecycle(self) -> PodLifecycle:
        """暴露底层生命周期管理器（测试用）。"""
        return self._lifecycle

    async def acquire(self) -> PodInfo:
        """获取一个 Pod。如果无空闲 Pod，抛出 RuntimeError。"""
        start = time.monotonic()

        # 优先获取 READY 状态的 Pod（按最后使用时间排序，最久未使用的优先）
        ready_pods = self._lifecycle.list_by_state(PodState.READY)
        if ready_pods:
            # 选择最久未使用的 Pod
            target = min(ready_pods, key=lambda p: p.last_used_at)
            self._lifecycle.transition(target.pod_id, PodState.BUSY)
            updated = self._lifecycle.get(target.pod_id)
            if updated is not None:
                # 记录延迟
                elapsed_ms = (time.monotonic() - start) * 1000
                self._latencies.append(elapsed_ms)
                if len(self._latencies) > 100:
                    self._latencies = self._latencies[-100:]
                return updated

        raise RuntimeError("没有可用的 Pod，所有 Pod 正在忙碌或池已满")

    async def release(self, pod_id: str) -> bool:
        """释放 Pod，将状态设为 READY。"""
        pod = self._lifecycle.get(pod_id)
        if pod is None:
            return False
        if pod.state != PodState.BUSY:
            return False

        # 通过状态转移回 READY
        success = self._lifecycle.transition(pod_id, PodState.READY)
        if success:
            # 直接更新内部记录的 last_used_at 和 task_count
            released = self._lifecycle.get(pod_id)
            if released is not None:
                self._lifecycle.remove(pod_id)
                # 直接写入内部字典（绕过 add 的 CREATING 校验）
                self._lifecycle._pods[pod_id] = PodInfo(
                    pod_id=released.pod_id,
                    state=PodState.READY,
                    python_version=released.python_version,
                    cpu_used=released.cpu_used,
                    memory_used_mb=released.memory_used_mb,
                    created_at=released.created_at,
                    last_used_at=time.time(),
                    task_count=released.task_count + 1,
                    error=released.error,
                )
        return success

    async def warmup(self, count: int = 3) -> int:
        """模拟预热（实际只创建空闲 Pod 记录）。"""
        # 仅统计非 TERMINATED 的 Pod
        active_pods = [
            p
            for p in self._lifecycle.pods.values()
            if p.state not in (PodState.TERMINATED, PodState.TERMINATING)
        ]
        actual = min(count, self._max_pods - len(active_pods))
        if actual <= 0:
            return 0

        created = 0
        for _ in range(actual):
            pod_id = f"local-pod-{uuid.uuid4().hex[:12]}"
            pod = PodInfo(
                pod_id=pod_id,
                state=PodState.CREATING,
                python_version="3.11",
                created_at=time.time(),
                last_used_at=time.time(),
            )
            self._lifecycle.add(pod)
            # 模拟创建过程：立即转为 READY
            self._lifecycle.transition(pod_id, PodState.READY)
            created += 1

        return created

    async def cleanup(self, max_idle_seconds: float = 300) -> int:
        """清理长时间未使用的 Pod 记录。

        清理规则：
        - READY 状态且空闲超过 max_idle_seconds 的 Pod
        - ERROR 状态的 Pod
        """
        now = time.time()
        cleaned = 0
        pods_to_clean: list[str] = []

        for pod_id, pod in self._lifecycle.pods.items():
            if pod.state == PodState.READY:
                idle_time = now - pod.last_used_at
                if idle_time > max_idle_seconds:
                    pods_to_clean.append((pod_id, PodState.READY))
            elif pod.state == PodState.ERROR:
                pods_to_clean.append((pod_id, PodState.ERROR))

        for pod_id, state in pods_to_clean:
            pod = self._lifecycle.get(pod_id)
            if pod is None:
                continue
            if state == PodState.ERROR:
                # ERROR 状态直接转到 TERMINATED（不经过 TERMINATING）
                if self._lifecycle.transition(pod_id, PodState.TERMINATED):
                    self._lifecycle.remove(pod_id)
                    cleaned += 1
            elif state == PodState.READY:
                if self._lifecycle.transition(pod_id, PodState.TERMINATING):
                    # 立即转为 TERMINATED
                    self._lifecycle.transition(pod_id, PodState.TERMINATED)
                    self._lifecycle.remove(pod_id)
                    cleaned += 1

        return cleaned

    async def get_stats(self) -> PoolStats:
        """获取池统计信息。"""
        all_pods = list(self._lifecycle.pods.values())

        ready_pods = [p for p in all_pods if p.state == PodState.READY]
        busy_pods = [p for p in all_pods if p.state == PodState.BUSY]
        creating_pods = [p for p in all_pods if p.state == PodState.CREATING]

        # 预热但未使用的 Pod：task_count == 0 且状态为 READY
        warm_pods = [p for p in ready_pods if p.task_count == 0]

        avg_latency = sum(self._latencies) / len(self._latencies) if self._latencies else 0.0

        return PoolStats(
            total_pods=len(all_pods),
            ready_pods=len(ready_pods),
            busy_pods=len(busy_pods),
            creating_pods=len(creating_pods),
            warm_pods=len(warm_pods),
            avg_latency_ms=avg_latency,
            total_tasks_executed=self._total_tasks_executed,
            error_count=self._error_count,
        )

    async def health_check(self) -> bool:
        """检查 Pod 池健康状态。

        条件：池中有至少一个非 TERMINATED 状态的 Pod。
        """
        active_pods = [
            p
            for p in self._lifecycle.pods.values()
            if p.state not in (PodState.TERMINATED, PodState.TERMINATING)
        ]
        return len(active_pods) > 0
