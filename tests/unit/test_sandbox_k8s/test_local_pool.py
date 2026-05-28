"""本地模拟 Pod 池单元测试。

测试 acquire、release、warmup、cleanup、stats 等核心操作。
"""

from __future__ import annotations

import time

import pytest

from datapilot_sandbox.k8s.lifecycle import PodInfo, PodLifecycle, PodState
from datapilot_sandbox.k8s.local_pool import LocalPodPool
from datapilot_sandbox.k8s.pool import PoolStats


# ---------- 辅助函数 ----------


def _inject_ready_pod(
    pool: LocalPodPool,
    pod_id: str = "ready-pod",
    idle_seconds: float = 0.0,
) -> None:
    """向池中注入一个 READY 状态的 Pod（通过合法路径创建）。"""
    pool.lifecycle.add(
        PodInfo(
            pod_id=pod_id,
            state=PodState.CREATING,
            python_version="3.11",
            created_at=time.time() - 600,
            last_used_at=time.time() - idle_seconds,
        )
    )
    pool.lifecycle.transition(pod_id, PodState.READY)


def _inject_busy_pod(
    pool: LocalPodPool,
    pod_id: str = "busy-pod",
    busy_duration: float = 0.0,
) -> None:
    """向池中注入一个 BUSY 状态的 Pod（通过合法路径创建）。"""
    pool.lifecycle.add(
        PodInfo(
            pod_id=pod_id,
            state=PodState.CREATING,
            python_version="3.11",
            created_at=time.time() - 600,
            last_used_at=time.time() - busy_duration,
        )
    )
    pool.lifecycle.transition(pod_id, PodState.READY)
    pool.lifecycle.transition(pod_id, PodState.BUSY)


def _inject_error_pod(
    pool: LocalPodPool,
    pod_id: str = "error-pod",
) -> None:
    """向池中注入一个 ERROR 状态的 Pod（通过合法路径创建）。"""
    pool.lifecycle.add(
        PodInfo(
            pod_id=pod_id,
            state=PodState.CREATING,
            python_version="3.11",
            created_at=time.time() - 600,
            last_used_at=time.time() - 600,
        )
    )
    pool.lifecycle.transition(pod_id, PodState.ERROR)


# ---------- 测试：初始化 ----------


class TestLocalPoolInit:
    """池初始化测试。"""

    @pytest.mark.asyncio
    async def test_empty_pool_stats(self) -> None:
        """空池的统计信息全为零。"""
        pool = LocalPodPool(max_pods=5)
        stats = await pool.get_stats()
        assert stats.total_pods == 0
        assert stats.ready_pods == 0
        assert stats.busy_pods == 0
        assert stats.creating_pods == 0
        assert stats.warm_pods == 0

    @pytest.mark.asyncio
    async def test_empty_pool_health_check(self) -> None:
        """空池健康检查应为 False。"""
        pool = LocalPodPool(max_pods=5)
        assert await pool.health_check() is False

    @pytest.mark.asyncio
    async def test_empty_pool_acquire_raises(self) -> None:
        """空池 acquire 应抛出 RuntimeError。"""
        pool = LocalPodPool(max_pods=5)
        with pytest.raises(RuntimeError, match="没有可用的 Pod"):
            await pool.acquire()

    @pytest.mark.asyncio
    async def test_lifecycle_property_exposed(self) -> None:
        """池应暴露 lifecycle 属性。"""
        pool = LocalPodPool(max_pods=5)
        assert isinstance(pool.lifecycle, PodLifecycle)


# ---------- 测试：预热 ----------


class TestWarmup:
    """预热功能测试。"""

    @pytest.mark.asyncio
    async def test_warmup_creates_pods(self) -> None:
        """预热应创建指定数量的 Pod。"""
        pool = LocalPodPool(max_pods=5)
        created = await pool.warmup(3)
        assert created == 3

        stats = await pool.get_stats()
        assert stats.total_pods == 3
        assert stats.ready_pods == 3

    @pytest.mark.asyncio
    async def test_warmup_respects_max_pods(self) -> None:
        """预热不应超过最大 Pod 数量。"""
        pool = LocalPodPool(max_pods=2)
        created = await pool.warmup(5)
        assert created == 2

        stats = await pool.get_stats()
        assert stats.total_pods == 2

    @pytest.mark.asyncio
    async def test_warmup_pods_are_ready(self) -> None:
        """预热后的 Pod 应为 READY 状态。"""
        pool = LocalPodPool(max_pods=5)
        await pool.warmup(2)

        ready_pods = pool.lifecycle.list_by_state(PodState.READY)
        assert len(ready_pods) == 2

    @pytest.mark.asyncio
    async def test_warmup_pods_are_warm(self) -> None:
        """预热但未使用的 Pod 应统计为 warm_pods。"""
        pool = LocalPodPool(max_pods=5)
        await pool.warmup(3)

        stats = await pool.get_stats()
        assert stats.warm_pods == 3

    @pytest.mark.asyncio
    async def test_warmup_zero_when_pool_full(self) -> None:
        """池满后再预热应返回 0。"""
        pool = LocalPodPool(max_pods=2)
        await pool.warmup(2)
        created = await pool.warmup(1)
        assert created == 0

    @pytest.mark.asyncio
    async def test_warmup_default_count(self) -> None:
        """warmup 默认预热 3 个 Pod。"""
        pool = LocalPodPool(max_pods=10)
        created = await pool.warmup()
        assert created == 3


# ---------- 测试：获取和释放 ----------


class TestAcquireAndRelease:
    """Pod 获取和释放测试。"""

    @pytest.mark.asyncio
    async def test_acquire_ready_pod(self) -> None:
        """获取一个 READY Pod，状态变为 BUSY。"""
        pool = LocalPodPool(max_pods=5)
        await pool.warmup(1)

        pod = await pool.acquire()
        assert pod.state == PodState.BUSY

        stats = await pool.get_stats()
        assert stats.ready_pods == 0
        assert stats.busy_pods == 1

    @pytest.mark.asyncio
    async def test_acquire_least_recently_used(self) -> None:
        """优先获取最久未使用的 Pod。"""
        pool = LocalPodPool(max_pods=5)
        # 手动注入两个 READY Pod，设置不同的 last_used_at
        _inject_ready_pod(pool, "old-pod", idle_seconds=100)
        _inject_ready_pod(pool, "new-pod", idle_seconds=5)

        acquired = await pool.acquire()
        assert acquired.pod_id == "old-pod"

    @pytest.mark.asyncio
    async def test_acquire_when_all_busy_raises(self) -> None:
        """所有 Pod 忙碌时 acquire 应抛出异常。"""
        pool = LocalPodPool(max_pods=2)
        await pool.warmup(2)
        await pool.acquire()  # 第一个
        await pool.acquire()  # 第二个

        with pytest.raises(RuntimeError, match="没有可用的 Pod"):
            await pool.acquire()

    @pytest.mark.asyncio
    async def test_release_busy_pod(self) -> None:
        """释放 BUSY Pod 回 READY 状态。"""
        pool = LocalPodPool(max_pods=5)
        await pool.warmup(1)
        pod = await pool.acquire()

        result = await pool.release(pod.pod_id)
        assert result is True

        released = pool.lifecycle.get(pod.pod_id)
        assert released is not None
        assert released.state == PodState.READY

    @pytest.mark.asyncio
    async def test_release_increments_task_count(self) -> None:
        """释放 Pod 后 task_count 应自增。"""
        pool = LocalPodPool(max_pods=5)
        await pool.warmup(1)
        pod = await pool.acquire()

        await pool.release(pod.pod_id)

        released = pool.lifecycle.get(pod.pod_id)
        assert released is not None
        assert released.task_count == 1

        # 多次执行
        pod2 = await pool.acquire()
        assert pod2.pod_id == pod.pod_id
        await pool.release(pod2.pod_id)
        released2 = pool.lifecycle.get(pod.pod_id)
        assert released2 is not None
        assert released2.task_count == 2

    @pytest.mark.asyncio
    async def test_release_nonexistent_pod(self) -> None:
        """释放不存在的 Pod 返回 False。"""
        pool = LocalPodPool(max_pods=5)
        assert await pool.release("nonexistent") is False

    @pytest.mark.asyncio
    async def test_release_ready_pod_fails(self) -> None:
        """释放非 BUSY 状态的 Pod 应返回 False。"""
        pool = LocalPodPool(max_pods=5)
        await pool.warmup(1)
        pods = pool.lifecycle.list_by_state(PodState.READY)
        assert await pool.release(pods[0].pod_id) is False


# ---------- 测试：清理 ----------


class TestCleanup:
    """清理功能测试。"""

    @pytest.mark.asyncio
    async def test_cleanup_idle_pods(self) -> None:
        """清理长时间空闲的 READY Pod。"""
        pool = LocalPodPool(max_pods=5)
        _inject_ready_pod(pool, "old-pod", idle_seconds=600)
        _inject_ready_pod(pool, "new-pod", idle_seconds=10)

        cleaned = await pool.cleanup(max_idle_seconds=300)
        assert cleaned == 1

        stats = await pool.get_stats()
        assert stats.total_pods == 1
        assert pool.lifecycle.get("old-pod") is None
        assert pool.lifecycle.get("new-pod") is not None

    @pytest.mark.asyncio
    async def test_cleanup_error_pods(self) -> None:
        """清理 ERROR 状态的 Pod。"""
        pool = LocalPodPool(max_pods=5)
        _inject_error_pod(pool, "error-1")
        _inject_ready_pod(pool, "healthy-1")

        cleaned = await pool.cleanup(max_idle_seconds=300)
        assert cleaned == 1

        stats = await pool.get_stats()
        assert stats.total_pods == 1
        assert pool.lifecycle.get("error-1") is None
        assert pool.lifecycle.get("healthy-1") is not None

    @pytest.mark.asyncio
    async def test_cleanup_no_pods_to_clean(self) -> None:
        """没有需要清理的 Pod 时返回 0。"""
        pool = LocalPodPool(max_pods=5)
        await pool.warmup(2)

        cleaned = await pool.cleanup(max_idle_seconds=300)
        assert cleaned == 0

    @pytest.mark.asyncio
    async def test_cleanup_does_not_touch_busy_pods(self) -> None:
        """清理不应影响 BUSY 状态的 Pod。"""
        pool = LocalPodPool(max_pods=5)
        _inject_busy_pod(pool, "busy-1", busy_duration=600)

        cleaned = await pool.cleanup(max_idle_seconds=300)
        assert cleaned == 0
        assert pool.lifecycle.get("busy-1") is not None


# ---------- 测试：统计 ----------


class TestStats:
    """统计信息测试。"""

    @pytest.mark.asyncio
    async def test_stats_after_warmup_and_acquire(self) -> None:
        """预热并获取后的统计信息。"""
        pool = LocalPodPool(max_pods=5)
        await pool.warmup(3)
        await pool.acquire()

        stats = await pool.get_stats()
        assert stats.total_pods == 3
        assert stats.ready_pods == 2
        assert stats.busy_pods == 1
        assert stats.creating_pods == 0
        assert stats.warm_pods == 2  # 未使用的 READY Pod

    @pytest.mark.asyncio
    async def test_stats_returns_poolstats_instance(self) -> None:
        """get_stats 应返回 PoolStats 实例。"""
        pool = LocalPodPool(max_pods=5)
        stats = await pool.get_stats()
        assert isinstance(stats, PoolStats)

    @pytest.mark.asyncio
    async def test_health_check_with_active_pods(self) -> None:
        """有活跃 Pod 时健康检查应为 True。"""
        pool = LocalPodPool(max_pods=5)
        await pool.warmup(1)
        assert await pool.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_with_busy_pod(self) -> None:
        """BUSY 状态的 Pod 也视为活跃，健康检查应为 True。"""
        pool = LocalPodPool(max_pods=5)
        await pool.warmup(1)
        await pool.acquire()
        assert await pool.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_after_cleanup(self) -> None:
        """清理所有 Pod 后健康检查应为 False。"""
        pool = LocalPodPool(max_pods=5)
        _inject_ready_pod(pool, "old-pod", idle_seconds=600)

        await pool.cleanup(max_idle_seconds=300)
        assert await pool.health_check() is False

    @pytest.mark.asyncio
    async def test_stats_warm_pods_excludes_used(self) -> None:
        """warm_pods 不包含已执行过任务的 Pod。"""
        pool = LocalPodPool(max_pods=5)
        await pool.warmup(2)
        pod = await pool.acquire()
        await pool.release(pod.pod_id)

        stats = await pool.get_stats()
        # 释放后 task_count 为 1，不再是 warm pod
        assert stats.warm_pods == 1
