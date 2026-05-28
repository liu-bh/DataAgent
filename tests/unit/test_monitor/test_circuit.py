"""datapilot_queryexec.monitor.circuit 单元测试。

覆盖熔断器的状态转换和请求允许判断。
"""

from __future__ import annotations

import time

import pytest

from datapilot_queryexec.monitor.circuit import DataSourceCircuitBreaker
from datapilot_queryexec.monitor.models import CircuitState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def breaker() -> DataSourceCircuitBreaker:
    """创建熔断器实例，使用较低的阈值方便测试。"""
    return DataSourceCircuitBreaker(
        failure_threshold=3,
        recovery_timeout=1,
        half_open_max_calls=2,
    )


# ---------------------------------------------------------------------------
# 初始状态测试
# ---------------------------------------------------------------------------


class TestInitialState:
    """熔断器初始状态测试。"""

    def test_default_closed(self, breaker: DataSourceCircuitBreaker) -> None:
        """默认状态为 CLOSED。"""
        assert breaker.get_state("ds-1") == CircuitState.CLOSED

    def test_is_allowed_when_closed(self, breaker: DataSourceCircuitBreaker) -> None:
        """CLOSED 状态下允许请求。"""
        assert breaker.is_allowed("ds-1") is True


# ---------------------------------------------------------------------------
# CLOSED → OPEN 状态转换
# ---------------------------------------------------------------------------


class TestClosedToOpen:
    """CLOSED 到 OPEN 的状态转换测试。"""

    def test_failures_below_threshold(self, breaker: DataSourceCircuitBreaker) -> None:
        """失败次数未达阈值，保持 CLOSED。"""
        breaker.record_failure("ds-1")
        breaker.record_failure("ds-1")

        assert breaker.get_state("ds-1") == CircuitState.CLOSED
        assert breaker.is_allowed("ds-1") is True

    def test_failures_reach_threshold(self, breaker: DataSourceCircuitBreaker) -> None:
        """连续失败达到阈值，转为 OPEN。"""
        breaker.record_failure("ds-1")
        breaker.record_failure("ds-1")
        state = breaker.record_failure("ds-1")

        assert state == CircuitState.OPEN
        assert breaker.get_state("ds-1") == CircuitState.OPEN

    def test_is_allowed_when_open(self, breaker: DataSourceCircuitBreaker) -> None:
        """OPEN 状态下拒绝请求。"""
        for _ in range(3):
            breaker.record_failure("ds-1")

        assert breaker.is_allowed("ds-1") is False

    def test_success_resets_counter(self, breaker: DataSourceCircuitBreaker) -> None:
        """成功调用重置连续失败计数器。"""
        breaker.record_failure("ds-1")
        breaker.record_failure("ds-1")
        # 一次成功重置计数器
        breaker.record_success("ds-1")
        # 再次失败 2 次不应触发熔断
        breaker.record_failure("ds-1")
        breaker.record_failure("ds-1")

        assert breaker.get_state("ds-1") == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# OPEN → HALF_OPEN 状态转换
# ---------------------------------------------------------------------------


class TestOpenToHalfOpen:
    """OPEN 到 HALF_OPEN 的状态转换测试。"""

    def test_auto_transition_to_half_open(self, breaker: DataSourceCircuitBreaker) -> None:
        """超时后自动转为 HALF_OPEN。"""
        # 触发熔断
        for _ in range(3):
            breaker.record_failure("ds-1")

        assert breaker.get_state("ds-1") == CircuitState.OPEN

        # 等待超时（recovery_timeout = 1 秒）
        time.sleep(1.1)

        assert breaker.get_state("ds-1") == CircuitState.HALF_OPEN

    def test_not_transition_before_timeout(self, breaker: DataSourceCircuitBreaker) -> None:
        """超时前不转为 HALF_OPEN。"""
        for _ in range(3):
            breaker.record_failure("ds-1")

        # 不等待超时
        assert breaker.get_state("ds-1") == CircuitState.OPEN


# ---------------------------------------------------------------------------
# HALF_OPEN 行为测试
# ---------------------------------------------------------------------------


class TestHalfOpen:
    """HALF_OPEN 状态下的行为测试。"""

    def _trigger_half_open(self, breaker: DataSourceCircuitBreaker) -> None:
        """辅助方法：触发熔断并等待进入 HALF_OPEN。"""
        for _ in range(3):
            breaker.record_failure("ds-1")
        time.sleep(1.1)
        assert breaker.get_state("ds-1") == CircuitState.HALF_OPEN

    def test_half_open_allows_limited_calls(self, breaker: DataSourceCircuitBreaker) -> None:
        """HALF_OPEN 状态允许有限次数的探测请求。"""
        self._trigger_half_open(breaker)

        # half_open_max_calls = 2
        assert breaker.is_allowed("ds-1") is True
        assert breaker.is_allowed("ds-1") is True
        # 第三次被拒绝
        assert breaker.is_allowed("ds-1") is False

    def test_success_closes_circuit(self, breaker: DataSourceCircuitBreaker) -> None:
        """HALF_OPEN 状态下探测成功，恢复为 CLOSED。"""
        self._trigger_half_open(breaker)

        state = breaker.record_success("ds-1")
        assert state == CircuitState.CLOSED
        assert breaker.get_state("ds-1") == CircuitState.CLOSED
        # 恢复后应允许请求
        assert breaker.is_allowed("ds-1") is True

    def test_failure_reopens_circuit(self, breaker: DataSourceCircuitBreaker) -> None:
        """HALF_OPEN 状态下探测失败，重新熔断为 OPEN。"""
        self._trigger_half_open(breaker)

        state = breaker.record_failure("ds-1")
        assert state == CircuitState.OPEN
        assert breaker.get_state("ds-1") == CircuitState.OPEN
        # 重新熔断后应拒绝请求
        assert breaker.is_allowed("ds-1") is False

    def test_multiple_successes_in_half_open(self, breaker: DataSourceCircuitBreaker) -> None:
        """HALF_OPEN 状态下多次成功仍保持 CLOSED。"""
        self._trigger_half_open(breaker)
        breaker.record_success("ds-1")
        breaker.record_success("ds-1")
        assert breaker.get_state("ds-1") == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# 多数据源隔离测试
# ---------------------------------------------------------------------------


class TestIsolation:
    """多数据源状态隔离测试。"""

    def test_different_datasources_independent(self, breaker: DataSourceCircuitBreaker) -> None:
        """不同数据源的状态相互独立。"""
        # ds-1 熔断
        for _ in range(3):
            breaker.record_failure("ds-1")
        assert breaker.get_state("ds-1") == CircuitState.OPEN

        # ds-2 仍为 CLOSED
        assert breaker.get_state("ds-2") == CircuitState.CLOSED
        assert breaker.is_allowed("ds-2") is True
        assert breaker.is_allowed("ds-1") is False

    def test_success_one_does_not_affect_other(self, breaker: DataSourceCircuitBreaker) -> None:
        """一个数据源的成功不影响另一个数据源。"""
        breaker.record_failure("ds-1")
        breaker.record_failure("ds-1")
        breaker.record_success("ds-1")

        # ds-2 不受影响
        assert breaker.get_state("ds-2") == CircuitState.CLOSED
