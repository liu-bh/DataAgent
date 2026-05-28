"""Pod 清理器单元测试。

测试超时清理、空闲清理、定期任务启动/停止。
"""

from __future__ import annotations

import asyncio
import time

import pytest

from datapilot_sandbox.k8s.lifecycle import PodInfo, PodState
from datapilot_sandbox.k8s.local_pool import LocalPodPool
from datapilot_sandbox.k8s.reaper import PodReaper


# ---------- 辅助函数 ----------


def _inject_busy_pod(
    pool: LocalPodPool,
    pod_id: str = "busy-pod",
    busy_duration: float = 0.0,
) -> None:
    """向池中注入一个 BUSY 状态的 Pod。

    Args:
        pool: 本地 Pod 池。
        pod_id: Pod ID。
        busy_duration: 模拟已忙碌的时间（秒），0 表示当前时间。
    """
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


def _inject_ready_pod(
    pool: LocalPodPool,
    pod_id: str = "ready-pod",
    idle_seconds: float = 0.0,
) -> None:
    """向池中注入一个 READY 状态的 Pod。"""
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


def _inject_error_pod(
    pool: LocalPodPool,
    pod_id: str = "error-pod",
) -> None:
    """向池中注入一个 ERROR 状态的 Pod。"""
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


# ---------- 测试：BUSY 超时清理 ----------


class TestBusyTimeout:
    """BUSY Pod 超时清理测试。"""

    @pytest.mark.asyncio
    async def test_reap_busy_timeout_pod(self) -> None:
        """超过 busy_timeout 的 BUSY Pod 应被清理。"""
        pool = LocalPodPool(max_pods=10)
        _inject_busy_pod(pool, "busy-1", busy_duration=60.0)
        _inject_ready_pod(pool, "ready-1")

        reaper = PodReaper(pool, busy_timeout=30.0, idle_timeout=300.0)
        cleaned = await reaper.reap_once()

        assert cleaned == 1
        assert pool.lifecycle.get("busy-1") is None
        assert pool.lifecycle.get("ready-1") is not None

    @pytest.mark.asyncio
    async def test_not_reap_recent_busy_pod(self) -> None:
        """未超时的 BUSY Pod 不应被清理。"""
        pool = LocalPodPool(max_pods=10)
        _inject_busy_pod(pool, "busy-1", busy_duration=10.0)

        reaper = PodReaper(pool, busy_timeout=30.0, idle_timeout=300.0)
        cleaned = await reaper.reap_once()

        assert cleaned == 0
        assert pool.lifecycle.get("busy-1") is not None


# ---------- 测试：空闲清理 ----------


class TestIdleCleanup:
    """空闲 Pod 清理测试。"""

    @pytest.mark.asyncio
    async def test_reap_idle_ready_pod(self) -> None:
        """超过 idle_timeout 的 READY Pod 应被清理。"""
        pool = LocalPodPool(max_pods=10)
        _inject_ready_pod(pool, "old-ready", idle_seconds=400.0)
        _inject_ready_pod(pool, "new-ready", idle_seconds=10.0)

        reaper = PodReaper(pool, busy_timeout=30.0, idle_timeout=300.0)
        cleaned = await reaper.reap_once()

        assert cleaned == 1
        assert pool.lifecycle.get("old-ready") is None
        assert pool.lifecycle.get("new-ready") is not None

    @pytest.mark.asyncio
    async def test_not_reap_recent_ready_pod(self) -> None:
        """未超时的 READY Pod 不应被清理。"""
        pool = LocalPodPool(max_pods=10)
        _inject_ready_pod(pool, "ready-1", idle_seconds=100.0)

        reaper = PodReaper(pool, busy_timeout=30.0, idle_timeout=300.0)
        cleaned = await reaper.reap_once()

        assert cleaned == 0


# ---------- 测试：ERROR 清理 ----------


class TestErrorCleanup:
    """ERROR Pod 清理测试。"""

    @pytest.mark.asyncio
    async def test_reap_error_pod(self) -> None:
        """ERROR 状态的 Pod 应被自动清理。"""
        pool = LocalPodPool(max_pods=10)
        _inject_error_pod(pool, "error-1")
        _inject_ready_pod(pool, "ready-1")

        reaper = PodReaper(pool, busy_timeout=30.0, idle_timeout=300.0)
        cleaned = await reaper.reap_once()

        assert cleaned == 1
        assert pool.lifecycle.get("error-1") is None
        assert pool.lifecycle.get("ready-1") is not None


# ---------- 测试：综合清理 ----------


class TestCombinedCleanup:
    """多种清理条件综合测试。"""

    @pytest.mark.asyncio
    async def test_reap_multiple_types(self) -> None:
        """一次清理同时处理多种类型的僵尸 Pod。"""
        pool = LocalPodPool(max_pods=10)
        _inject_busy_pod(pool, "busy-timeout", busy_duration=60.0)
        _inject_ready_pod(pool, "idle-timeout", idle_seconds=400.0)
        _inject_error_pod(pool, "error-pod")
        _inject_ready_pod(pool, "healthy-1", idle_seconds=10.0)
        _inject_busy_pod(pool, "busy-active", busy_duration=5.0)

        reaper = PodReaper(pool, busy_timeout=30.0, idle_timeout=300.0)
        cleaned = await reaper.reap_once()

        # busy-timeout + idle-timeout + error-pod = 3
        assert cleaned == 3
        assert pool.lifecycle.get("busy-timeout") is None
        assert pool.lifecycle.get("idle-timeout") is None
        assert pool.lifecycle.get("error-pod") is None
        assert pool.lifecycle.get("healthy-1") is not None
        assert pool.lifecycle.get("busy-active") is not None

    @pytest.mark.asyncio
    async def test_reap_empty_pool(self) -> None:
        """空池清理返回 0。"""
        pool = LocalPodPool(max_pods=10)
        reaper = PodReaper(pool)
        cleaned = await reaper.reap_once()
        assert cleaned == 0


# ---------- 测试：定期清理任务 ----------


class TestPeriodicCleanup:
    """定期清理任务测试。"""

    @pytest.mark.asyncio
    async def test_start_and_stop(self) -> None:
        """启动和停止清理任务。"""
        pool = LocalPodPool(max_pods=10)
        reaper = PodReaper(pool, cleanup_interval=0.1)

        assert reaper.is_running is False

        await reaper.start()
        assert reaper.is_running is True

        await reaper.stop()
        assert reaper.is_running is False

    @pytest.mark.asyncio
    async def test_double_start_is_idempotent(self) -> None:
        """重复启动清理任务不会创建多个任务。"""
        pool = LocalPodPool(max_pods=10)
        reaper = PodReaper(pool, cleanup_interval=1.0)

        await reaper.start()
        await reaper.start()
        assert reaper.is_running is True

        await reaper.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start(self) -> None:
        """未启动时停止不应报错。"""
        pool = LocalPodPool(max_pods=10)
        reaper = PodReaper(pool)
        await reaper.stop()
        assert reaper.is_running is False

    @pytest.mark.asyncio
    async def test_periodic_cleanup_runs(self) -> None:
        """定期清理任务应在指定间隔后执行清理。"""
        pool = LocalPodPool(max_pods=10)
        _inject_error_pod(pool, "error-pod")

        reaper = PodReaper(pool, cleanup_interval=0.05)
        await reaper.start()

        # 等待清理任务至少执行一次
        await asyncio.sleep(0.2)

        await reaper.stop()

        # ERROR Pod 应已被清理
        assert pool.lifecycle.get("error-pod") is None

    @pytest.mark.asyncio
    async def test_cleanup_interval_controls_frequency(self) -> None:
        """cleanup_interval 控制清理频率，短间隔应更快触发清理。"""
        pool = LocalPodPool(max_pods=10)
        _inject_error_pod(pool, "error-pod")

        reaper = PodReaper(pool, cleanup_interval=0.01)
        await reaper.start()

        # 短间隔下，0.05 秒足够多次清理
        await asyncio.sleep(0.05)

        await reaper.stop()

        assert pool.lifecycle.get("error-pod") is None
