"""Pod 清理器。

定时检查 Pod 状态，清理僵尸 Pod：
- 30s 超时的 BUSY Pod 强制销毁
- 超过 max_idle_seconds 的 READY Pod 回收
- 处于 ERROR 状态的 Pod 自动清理
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING

from datapilot_sandbox.k8s.lifecycle import PodState

if TYPE_CHECKING:
    from datapilot_sandbox.k8s.pool import PodPool


class PodReaper:
    """定时清理僵尸 Pod。

    功能：
    - 30s 超时的 BUSY Pod 强制销毁
    - 超过 max_idle_seconds 的 READY Pod 回收
    - 处于 ERROR 状态的 Pod 自动清理
    """

    def __init__(
        self,
        pool: PodPool,
        busy_timeout: float = 30.0,
        idle_timeout: float = 300.0,
        cleanup_interval: float = 10.0,
    ) -> None:
        """初始化清理器。

        Args:
            pool: Pod 池实例（需要暴露 lifecycle 属性用于清理操作）。
            busy_timeout: BUSY 状态超时时间（秒），超时后强制终止。
            idle_timeout: READY 状态空闲超时时间（秒），超时后回收。
            cleanup_interval: 定期清理间隔（秒）。
        """
        self._pool = pool
        self._busy_timeout = busy_timeout
        self._idle_timeout = idle_timeout
        self._cleanup_interval = cleanup_interval
        self._task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """清理任务是否正在运行。"""
        return self._running

    async def start(self) -> None:
        """启动定期清理任务（asyncio.create_task）。"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """停止清理任务。"""
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None

    async def _cleanup_loop(self) -> None:
        """定期清理循环。"""
        while self._running:
            with contextlib.suppress(Exception):
                await self.reap_once()
            await asyncio.sleep(self._cleanup_interval)

    async def reap_once(self) -> int:
        """执行一次清理，返回清理的 Pod 数量。

        注意：此方法需要 pool 暴露 lifecycle 属性，
        通过 pool.lifecycle 获取底层 Pod 信息进行清理。
        """
        # 通过 pool 的 cleanup 方法执行基础清理
        # 对于 LocalPodPool，cleanup 已包含 ERROR 状态和空闲 READY Pod 的清理
        cleaned = await self._pool.cleanup(self._idle_timeout)

        # 额外处理 BUSY 超时的 Pod
        # 需要访问 pool 的内部 lifecycle
        lifecycle = getattr(self._pool, "lifecycle", None)
        if lifecycle is not None:
            now = time.time()
            busy_pods = lifecycle.list_by_state(PodState.BUSY)
            for pod in busy_pods:
                # 检查 BUSY 状态持续时间
                busy_duration = now - pod.last_used_at
                if busy_duration > self._busy_timeout:
                    # 强制标记为 ERROR 再清理
                    lifecycle.transition(pod.pod_id, PodState.ERROR)
                    lifecycle.transition(pod.pod_id, PodState.TERMINATED)
                    lifecycle.remove(pod.pod_id)
                    cleaned += 1

        return cleaned
