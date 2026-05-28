"""Pod 池资源监控单元测试。

测试告警规则、扩缩容建议。
"""

from __future__ import annotations

import time

import pytest

from datapilot_sandbox.k8s.lifecycle import PodInfo, PodState
from datapilot_sandbox.k8s.local_pool import LocalPodPool
from datapilot_sandbox.k8s.monitor import PoolAlert, PoolMonitor


# ---------- 辅助函数 ----------


def _add_pods_to_pool(pool: LocalPodPool, ready: int = 0, busy: int = 0) -> None:
    """向池中注入指定状态的 Pod。

    Args:
        pool: 本地 Pod 池。
        ready: READY 状态的 Pod 数量。
        busy: BUSY 状态的 Pod 数量。
    """
    for i in range(ready):
        pool.lifecycle.add(
            PodInfo(
                pod_id=f"ready-{i}",
                state=PodState.CREATING,
                python_version="3.11",
                created_at=time.time(),
                last_used_at=time.time(),
            )
        )
        pool.lifecycle.transition(f"ready-{i}", PodState.READY)

    for i in range(busy):
        pool.lifecycle.add(
            PodInfo(
                pod_id=f"busy-{i}",
                state=PodState.CREATING,
                python_version="3.11",
                created_at=time.time(),
                last_used_at=time.time(),
            )
        )
        pool.lifecycle.transition(f"busy-{i}", PodState.READY)
        pool.lifecycle.transition(f"busy-{i}", PodState.BUSY)


# ---------- 测试：告警规则 ----------


class TestAlertRules:
    """告警规则测试。"""

    @pytest.mark.asyncio
    async def test_high_usage_warning(self) -> None:
        """使用率 > 80% 但 <= 95% 应触发 warning。"""
        # 1 ready + 5 busy = 6 total, usage = 5/6 = 83.3% > 80%
        pool = LocalPodPool(max_pods=10)
        _add_pods_to_pool(pool, ready=1, busy=5)

        monitor = PoolMonitor(pool)
        alerts = await monitor.check_and_alert()

        assert len(alerts) >= 1
        warning_alerts = [a for a in alerts if a.level == "warning"]
        assert any("80%" in a.message for a in warning_alerts)

    @pytest.mark.asyncio
    async def test_high_usage_critical(self) -> None:
        """使用率 > 95% 应触发 critical。"""
        # 0 ready + 5 busy = 5 total, usage = 100% > 95%
        pool = LocalPodPool(max_pods=10)
        _add_pods_to_pool(pool, ready=0, busy=5)

        monitor = PoolMonitor(pool)
        alerts = await monitor.check_and_alert()

        critical_alerts = [a for a in alerts if a.level == "critical"]
        assert len(critical_alerts) >= 1
        assert any("95%" in a.message for a in critical_alerts)

    @pytest.mark.asyncio
    async def test_low_usage_info(self) -> None:
        """使用率 < 20% 应触发 info。"""
        # 4 ready + 0 busy = 4 total, usage = 0% < 20%
        pool = LocalPodPool(max_pods=10)
        _add_pods_to_pool(pool, ready=4, busy=0)

        monitor = PoolMonitor(pool)
        alerts = await monitor.check_and_alert()

        info_alerts = [a for a in alerts if a.level == "info"]
        assert len(info_alerts) >= 1
        assert any("缩容" in a.message for a in info_alerts)

    @pytest.mark.asyncio
    async def test_normal_usage_no_alerts(self) -> None:
        """使用率在 20%-80% 之间不应触发使用率告警。"""
        # 3 ready + 1 busy = 4 total, usage = 1/4 = 25% -> 不在 > 80% 或 < 20%
        pool = LocalPodPool(max_pods=10)
        _add_pods_to_pool(pool, ready=3, busy=1)

        monitor = PoolMonitor(pool)
        alerts = await monitor.check_and_alert()

        usage_alerts = [a for a in alerts if "使用率" in a.message]
        assert len(usage_alerts) == 0

    @pytest.mark.asyncio
    async def test_high_error_rate_warning(self) -> None:
        """错误率 > 10% 应触发 warning。"""
        pool = LocalPodPool(max_pods=10)
        _add_pods_to_pool(pool, ready=3, busy=0)

        # 手动设置统计信息中的错误计数
        pool._total_tasks_executed = 100
        pool._error_count = 15  # 15% 错误率

        monitor = PoolMonitor(pool)
        alerts = await monitor.check_and_alert()

        error_alerts = [a for a in alerts if "错误率" in a.message]
        assert len(error_alerts) >= 1
        assert any("warning" == a.level for a in error_alerts)

    @pytest.mark.asyncio
    async def test_zero_pools_no_alerts(self) -> None:
        """空池不应触发使用率告警。"""
        pool = LocalPodPool(max_pods=10)

        monitor = PoolMonitor(pool)
        alerts = await monitor.check_and_alert()

        usage_alerts = [a for a in alerts if "使用率" in a.message]
        assert len(usage_alerts) == 0


# ---------- 测试：扩缩容建议 ----------


class TestScaleSuggestions:
    """扩缩容建议测试。"""

    @pytest.mark.asyncio
    async def test_should_scale_up_when_high_usage(self) -> None:
        """使用率 > 80% 时应建议扩容。"""
        # 1 ready + 5 busy = 6 total, usage = 5/6 = 83.3% > 80%
        pool = LocalPodPool(max_pods=10)
        _add_pods_to_pool(pool, ready=1, busy=5)

        monitor = PoolMonitor(pool)
        assert await monitor.should_scale_up() is True

    @pytest.mark.asyncio
    async def test_should_not_scale_up_when_low_usage(self) -> None:
        """使用率 < 80% 时不应建议扩容。"""
        pool = LocalPodPool(max_pods=10)
        _add_pods_to_pool(pool, ready=4, busy=0)

        monitor = PoolMonitor(pool)
        assert await monitor.should_scale_up() is False

    @pytest.mark.asyncio
    async def test_should_scale_down_when_low_usage(self) -> None:
        """使用率 < 20% 且 Pod > 1 时应建议缩容。"""
        pool = LocalPodPool(max_pods=10)
        _add_pods_to_pool(pool, ready=4, busy=0)  # 使用率 0%

        monitor = PoolMonitor(pool)
        assert await monitor.should_scale_down() is True

    @pytest.mark.asyncio
    async def test_should_not_scale_down_with_one_pod(self) -> None:
        """只有 1 个 Pod 时不应建议缩容。"""
        pool = LocalPodPool(max_pods=10)
        _add_pods_to_pool(pool, ready=1, busy=0)

        monitor = PoolMonitor(pool)
        assert await monitor.should_scale_down() is False

    @pytest.mark.asyncio
    async def test_should_not_scale_down_when_high_usage(self) -> None:
        """使用率 >= 20% 时不应建议缩容。"""
        pool = LocalPodPool(max_pods=10)
        _add_pods_to_pool(pool, ready=3, busy=1)  # 25%

        monitor = PoolMonitor(pool)
        assert await monitor.should_scale_down() is False

    @pytest.mark.asyncio
    async def test_should_scale_up_when_empty(self) -> None:
        """空池应建议扩容。"""
        pool = LocalPodPool(max_pods=10)

        monitor = PoolMonitor(pool)
        assert await monitor.should_scale_up() is True


# ---------- 测试：告警历史 ----------


class TestAlertHistory:
    """告警历史记录测试。"""

    @pytest.mark.asyncio
    async def test_alerts_are_recorded(self) -> None:
        """告警应被记录到历史中。"""
        pool = LocalPodPool(max_pods=10)
        _add_pods_to_pool(pool, ready=0, busy=5)

        monitor = PoolMonitor(pool)
        assert len(monitor.alerts_history) == 0

        await monitor.check_and_alert()
        assert len(monitor.alerts_history) > 0

    @pytest.mark.asyncio
    async def test_alert_history_capped_at_200(self) -> None:
        """告警历史不应超过 200 条。"""
        pool = LocalPodPool(max_pods=10)
        _add_pods_to_pool(pool, ready=0, busy=5)

        monitor = PoolMonitor(pool)
        # 多次检查以产生大量告警
        for _ in range(100):
            await monitor.check_and_alert()

        assert len(monitor.alerts_history) <= 200

    @pytest.mark.asyncio
    async def test_alert_history_truncates_older(self) -> None:
        """超过 200 条时，应截断保留最近的 200 条。"""
        pool = LocalPodPool(max_pods=10)
        _add_pods_to_pool(pool, ready=0, busy=5)

        monitor = PoolMonitor(pool)
        # 每次产生 1 个 critical 告警，调用 210 次
        for _ in range(210):
            await monitor.check_and_alert()

        assert len(monitor.alerts_history) == 200
        # 最旧告警应已被截断，最早的应该是第 11 次产生的
        oldest = monitor.alerts_history[0]
        assert oldest.level == "critical"

    @pytest.mark.asyncio
    async def test_alert_has_timestamp(self) -> None:
        """告警应包含时间戳。"""
        pool = LocalPodPool(max_pods=10)
        _add_pods_to_pool(pool, ready=0, busy=5)

        monitor = PoolMonitor(pool)
        alerts = await monitor.check_and_alert()

        before = time.time()
        for alert in alerts:
            assert alert.timestamp > 0
            assert alert.timestamp <= before + 1  # 允许微小的时间误差

    @pytest.mark.asyncio
    async def test_alert_level_values(self) -> None:
        """告警级别应为 info / warning / critical 之一。"""
        pool = LocalPodPool(max_pods=10)
        _add_pods_to_pool(pool, ready=0, busy=5)

        monitor = PoolMonitor(pool)
        alerts = await monitor.check_and_alert()

        valid_levels = {"info", "warning", "critical"}
        for alert in alerts:
            assert alert.level in valid_levels

    @pytest.mark.asyncio
    async def test_no_alerts_for_healthy_pool(self) -> None:
        """健康的池不应产生任何告警。"""
        # 3 ready + 1 busy = 4 total, usage = 25%, 无错误
        pool = LocalPodPool(max_pods=10)
        _add_pods_to_pool(pool, ready=3, busy=1)

        monitor = PoolMonitor(pool)
        alerts = await monitor.check_and_alert()
        assert len(alerts) == 0
