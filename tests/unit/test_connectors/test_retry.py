"""差异化重试策略单元测试。

测试 RetryPolicy 的 should_retry 错误分类和 wait 指数退避逻辑。
"""

from __future__ import annotations

import asyncio

import pytest

from datapilot_queryexec.connectors.retry import RetryPolicy

# ---------- 辅助：模拟数据库驱动异常 ----------


class ProgrammingError(Exception):
    """模拟数据库 ProgrammingError（语法错误）。"""


class OperationalError(Exception):
    """模拟数据库 OperationalError。"""


class InternalError(Exception):
    """模拟数据库 InternalError。"""


# ---------- should_retry 错误分类测试 ----------


class TestShouldRetryTransientErrors:
    """临时错误应该重试。"""

    def setup_method(self) -> None:
        self.policy = RetryPolicy(max_retries=3, base_delay=1.0)

    def test_connection_error(self) -> None:
        """ConnectionError 应该重试。"""
        assert self.policy.should_retry(ConnectionError("连接被拒绝")) is True

    def test_timeout_error(self) -> None:
        """TimeoutError 应该重试。"""
        assert self.policy.should_retry(TimeoutError("操作超时")) is True

    def test_os_error(self) -> None:
        """OSError 应该重试。"""
        assert self.policy.should_retry(OSError("网络不可达")) is True

    def test_operational_error_deadlock(self) -> None:
        """OperationalError 包含 deadlock 关键词应该重试。"""
        err = OperationalError("Deadlock found when trying to get lock")
        assert self.policy.should_retry(err) is True

    def test_operational_error_timeout(self) -> None:
        """OperationalError 包含 timeout 关键词应该重试。"""
        err = OperationalError("Lock wait timeout exceeded")
        assert self.policy.should_retry(err) is True

    def test_operational_error_timed_out(self) -> None:
        """OperationalError 包含 timed out 关键词应该重试。"""
        err = OperationalError("Query execution was timed out")
        assert self.policy.should_retry(err) is True

    def test_operational_error_too_many_connections(self) -> None:
        """OperationalError 包含 too many connections 应该重试。"""
        err = OperationalError("Too many connections")
        assert self.policy.should_retry(err) is True

    def test_operational_error_gone_away(self) -> None:
        """OperationalError 包含 server has gone away 应该重试。"""
        err = OperationalError("MySQL server has gone away")
        assert self.policy.should_retry(err) is True

    def test_operational_error_broken_pipe(self) -> None:
        """OperationalError 包含 broken pipe 应该重试。"""
        err = OperationalError("Broken pipe")
        assert self.policy.should_retry(err) is True

    def test_operational_error_connection_reset(self) -> None:
        """OperationalError 包含 connection reset 应该重试。"""
        err = OperationalError("Connection reset by peer")
        assert self.policy.should_retry(err) is True

    def test_unknown_error_with_transient_keyword(self) -> None:
        """未知错误类型但包含临时错误关键词应该重试（兜底逻辑）。"""
        err = InternalError("temporary failure in the cluster")
        assert self.policy.should_retry(err) is True

    def test_custom_error_with_transient_keyword(self) -> None:
        """自定义异常包含临时错误关键词应该重试。"""
        err = RuntimeError("Lock wait timeout exceeded")
        assert self.policy.should_retry(err) is True


class TestShouldRetryPermanentErrors:
    """永久错误不应该重试。"""

    def setup_method(self) -> None:
        self.policy = RetryPolicy(max_retries=3, base_delay=1.0)

    def test_syntax_error(self) -> None:
        """SyntaxError 不应该重试。"""
        assert self.policy.should_retry(SyntaxError("invalid syntax")) is False

    def test_value_error(self) -> None:
        """ValueError 不应该重试。"""
        assert self.policy.should_retry(ValueError("invalid parameter")) is False

    def test_programming_error(self) -> None:
        """ProgrammingError（SQL 语法错误）不应该重试。"""
        err = ProgrammingError("You have an error in your SQL syntax")
        assert self.policy.should_retry(err) is False

    def test_operational_error_unknown_table(self) -> None:
        """OperationalError 不包含临时错误关键词不应该重试。"""
        err = OperationalError("Table 'unknown_db.unknown_table' doesn't exist")
        assert self.policy.should_retry(err) is False

    def test_operational_error_access_denied(self) -> None:
        """OperationalError 权限不足不应该重试。"""
        err = OperationalError("Access denied for user")
        assert self.policy.should_retry(err) is False


class TestShouldRetryUnknownErrors:
    """未知错误默认不重试。"""

    def setup_method(self) -> None:
        self.policy = RetryPolicy(max_retries=3, base_delay=1.0)

    def test_runtime_error(self) -> None:
        """普通 RuntimeError 不应该重试。"""
        assert self.policy.should_retry(RuntimeError("未知错误")) is False

    def test_key_error(self) -> None:
        """KeyError 不应该重试。"""
        assert self.policy.should_retry(KeyError("missing_key")) is False

    def test_type_error(self) -> None:
        """TypeError 不应该重试。"""
        assert self.policy.should_retry(TypeError("类型不匹配")) is False

    def test_internal_error_no_keyword(self) -> None:
        """InternalError 不包含临时错误关键词不应该重试。"""
        err = InternalError("internal error code 1001")
        assert self.policy.should_retry(err) is False


# ---------- wait 指数退避测试 ----------


class TestWaitExponentialBackoff:
    """指数退避等待时间测试。"""

    def test_default_params(self) -> None:
        """默认参数测试。"""
        policy = RetryPolicy()
        assert policy.max_retries == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 30.0

    def test_custom_params(self) -> None:
        """自定义参数测试。"""
        policy = RetryPolicy(max_retries=5, base_delay=0.5, max_delay=10.0)
        assert policy.max_retries == 5
        assert policy.base_delay == 0.5
        assert policy.max_delay == 10.0

    @pytest.mark.asyncio
    async def test_wait_attempt_0(self) -> None:
        """第 0 次重试延迟: base_delay * 2^0 + jitter ~= base_delay。"""
        policy = RetryPolicy(base_delay=0.01, max_delay=1.0)
        start = asyncio.get_event_loop().time()
        await policy.wait(0)
        elapsed = asyncio.get_event_loop().time() - start
        # base_delay * 2^0 = 0.01, 加上 jitter <= 0.01 * 0.5 = 0.005
        # 总延迟约 0.01~0.015，放宽范围以适应 Windows 定时器抖动
        assert 0.005 <= elapsed < 0.05

    @pytest.mark.asyncio
    async def test_wait_attempt_1(self) -> None:
        """第 1 次重试延迟: base_delay * 2^1 + jitter ~= 2 * base_delay。"""
        policy = RetryPolicy(base_delay=0.01, max_delay=1.0)
        start = asyncio.get_event_loop().time()
        await policy.wait(1)
        elapsed = asyncio.get_event_loop().time() - start
        # base_delay * 2^1 = 0.02, 加上 jitter <= 0.005
        assert 0.01 <= elapsed < 0.06

    @pytest.mark.asyncio
    async def test_wait_attempt_2(self) -> None:
        """第 2 次重试延迟: base_delay * 2^2 + jitter ~= 4 * base_delay。"""
        policy = RetryPolicy(base_delay=0.01, max_delay=1.0)
        start = asyncio.get_event_loop().time()
        await policy.wait(2)
        elapsed = asyncio.get_event_loop().time() - start
        # base_delay * 2^2 = 0.04, 加上 jitter
        assert 0.03 <= elapsed < 0.08

    @pytest.mark.asyncio
    async def test_wait_max_delay_capped(self) -> None:
        """延迟不会超过 max_delay。"""
        policy = RetryPolicy(base_delay=1.0, max_delay=0.05)
        start = asyncio.get_event_loop().time()
        await policy.wait(10)  # 尝试 10 次，指数值会非常大
        elapsed = asyncio.get_event_loop().time() - start
        # 应该被 max_delay=0.05 截断
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_wait_has_jitter(self) -> None:
        """多次等待的时间不完全相同（jitter 随机性）。"""
        policy = RetryPolicy(base_delay=0.01, max_delay=1.0)
        times: list[float] = []
        for _ in range(5):
            start = asyncio.get_event_loop().time()
            await policy.wait(0)
            elapsed = asyncio.get_event_loop().time() - start
            times.append(elapsed)
        # 由于 jitter，至少有一个时间与其他不同
        assert len(set(round(t, 4) for t in times)) > 1


# ---------- RetryPolicy 初始化测试 ----------


class TestRetryPolicyInit:
    """RetryPolicy 初始化测试。"""

    def test_zero_retries(self) -> None:
        """max_retries=0 表示不重试。"""
        policy = RetryPolicy(max_retries=0)
        assert policy.max_retries == 0

    def test_large_retries(self) -> None:
        """允许较大的重试次数。"""
        policy = RetryPolicy(max_retries=10)
        assert policy.max_retries == 10

    def test_zero_base_delay(self) -> None:
        """base_delay=0 时退避时间仅由 jitter 构成。"""
        policy = RetryPolicy(base_delay=0.0)
        assert policy.base_delay == 0.0
