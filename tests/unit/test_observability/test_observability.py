"""可观测性模块单元测试。

覆盖健康检查、请求指标、请求追踪中间件、电路断路器和重试执行器。
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from datapilot_agent.observability.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)
from datapilot_agent.observability.health import HealthCheckResult, HealthChecker, HealthStatus
from datapilot_agent.observability.metrics import RequestMetrics
from datapilot_agent.observability.middleware import RequestTraceMiddleware
from datapilot_agent.observability.retry import RetryExecutor


# ============================================================
# HealthStatus 枚举测试
# ============================================================


class TestHealthStatus:
    """HealthStatus 枚举测试。"""

    def test_enum_values(self) -> None:
        """验证枚举值正确。"""
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.UNHEALTHY == "unhealthy"

    def test_enum_members_count(self) -> None:
        """验证枚举成员数量。"""
        assert len(HealthStatus) == 3

    def test_enum_is_str_enum(self) -> None:
        """验证 StrEnum 支持字符串比较。"""
        assert HealthStatus.HEALTHY == "healthy"
        assert isinstance(HealthStatus.HEALTHY, str)


# ============================================================
# HealthCheckResult 数据类测试
# ============================================================


class TestHealthCheckResult:
    """HealthCheckResult 数据类测试。"""

    def test_default_values(self) -> None:
        """验证默认值。"""
        result = HealthCheckResult(component="test", status=HealthStatus.HEALTHY)
        assert result.component == "test"
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms == 0.0
        assert result.message == ""
        assert result.details == {}

    def test_custom_values(self) -> None:
        """验证自定义值。"""
        result = HealthCheckResult(
            component="db",
            status=HealthStatus.DEGRADED,
            latency_ms=42.5,
            message="响应较慢",
            details={"pool_size": 5},
        )
        assert result.component == "db"
        assert result.status == HealthStatus.DEGRADED
        assert result.latency_ms == 42.5
        assert result.message == "响应较慢"
        assert result.details == {"pool_size": 5}

    def test_details_mutable_isolation(self) -> None:
        """验证两个实例的 details 不共享引用。"""
        r1 = HealthCheckResult(component="a", status=HealthStatus.HEALTHY)
        r2 = HealthCheckResult(component="b", status=HealthStatus.HEALTHY)
        r1.details["key"] = "value"
        assert "key" not in r2.details


# ============================================================
# HealthChecker 测试
# ============================================================


class TestHealthChecker:
    """HealthChecker 多组件健康检查器测试。"""

    @pytest.fixture
    def checker(self) -> HealthChecker:
        """创建不带内置检查的 HealthChecker 实例。"""
        hc = HealthChecker()
        # 清除内置检查，使用纯净实例
        hc._checks.clear()
        return hc

    @pytest.mark.asyncio
    async def test_register_and_check_custom(self, checker: HealthChecker) -> None:
        """注册自定义检查并执行。"""
        async def mock_check() -> HealthCheckResult:
            return HealthCheckResult(component="custom", status=HealthStatus.HEALTHY)

        checker.register("custom", mock_check)
        results = await checker.check_all()
        assert "custom" in results
        assert results["custom"].status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_unregister(self, checker: HealthChecker) -> None:
        """注销检查后不再执行。"""
        async def mock_check() -> HealthCheckResult:
            return HealthCheckResult(component="temp", status=HealthStatus.HEALTHY)

        checker.register("temp", mock_check)
        checker.unregister("temp")
        results = await checker.check_all()
        assert "temp" not in results

    @pytest.mark.asyncio
    async def test_unregister_nonexistent(self, checker: HealthChecker) -> None:
        """注销不存在的组件不报错。"""
        checker.unregister("nonexistent")  # 不应抛出异常

    @pytest.mark.asyncio
    async def test_check_all_with_exception(self, checker: HealthChecker) -> None:
        """检查函数抛异常时返回 UNHEALTHY。"""
        async def failing_check() -> HealthCheckResult:
            raise RuntimeError("连接超时")

        checker.register("bad_component", failing_check)
        results = await checker.check_all()
        assert results["bad_component"].status == HealthStatus.UNHEALTHY
        assert "连接超时" in results["bad_component"].message

    @pytest.mark.asyncio
    async def test_check_database(self) -> None:
        """数据库健康检查返回 HEALTHY。"""
        checker = HealthChecker()
        result = await checker.check_database()
        assert result.component == "database"
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_check_redis(self) -> None:
        """Redis 健康检查返回 HEALTHY。"""
        checker = HealthChecker()
        result = await checker.check_redis()
        assert result.component == "redis"
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_check_llm(self) -> None:
        """LLM 健康检查返回 HEALTHY。"""
        checker = HealthChecker()
        result = await checker.check_llm()
        assert result.component == "llm"
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_get_overall_status_all_healthy(self) -> None:
        """全部 HEALTHY → HEALTHY。"""
        results = {
            "db": HealthCheckResult(component="db", status=HealthStatus.HEALTHY),
            "redis": HealthCheckResult(component="redis", status=HealthStatus.HEALTHY),
        }
        assert HealthChecker.get_overall_status(results) == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_get_overall_status_has_unhealthy(self) -> None:
        """任一 UNHEALTHY → UNHEALTHY。"""
        results = {
            "db": HealthCheckResult(component="db", status=HealthStatus.HEALTHY),
            "redis": HealthCheckResult(component="redis", status=HealthStatus.UNHEALTHY),
        }
        assert HealthChecker.get_overall_status(results) == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_get_overall_status_has_degraded(self) -> None:
        """有 DEGRADED 但无 UNHEALTHY → DEGRADED。"""
        results = {
            "db": HealthCheckResult(component="db", status=HealthStatus.HEALTHY),
            "llm": HealthCheckResult(component="llm", status=HealthStatus.DEGRADED),
        }
        assert HealthChecker.get_overall_status(results) == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_get_overall_status_empty(self) -> None:
        """空结果集返回 UNHEALTHY。"""
        assert HealthChecker.get_overall_status({}) == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_all_default_builtins(self) -> None:
        """默认注册了 database/redis/llm 三个内置检查。"""
        checker = HealthChecker()
        results = await checker.check_all()
        assert "database" in results
        assert "redis" in results
        assert "llm" in results

    @pytest.mark.asyncio
    async def test_check_all_concurrent(self, checker: HealthChecker) -> None:
        """check_all 并发执行所有检查。"""
        call_order: list[str] = []

        async def slow_check_a() -> HealthCheckResult:
            call_order.append("a_start")
            await asyncio.sleep(0.05)
            call_order.append("a_end")
            return HealthCheckResult(component="a", status=HealthStatus.HEALTHY)

        async def slow_check_b() -> HealthCheckResult:
            call_order.append("b_start")
            await asyncio.sleep(0.05)
            call_order.append("b_end")
            return HealthCheckResult(component="b", status=HealthStatus.HEALTHY)

        checker.register("a", slow_check_a)
        checker.register("b", slow_check_b)
        start = time.perf_counter()
        await checker.check_all()
        elapsed = (time.perf_counter() - start) * 1000

        # 并发执行应约 50ms，而非串行 100ms
        assert elapsed < 150
        # 两者应并行启动
        assert call_order.index("a_start") < call_order.index("a_end")
        assert call_order.index("b_start") < call_order.index("b_end")


# ============================================================
# RequestMetrics 测试
# ============================================================


class TestRequestMetrics:
    """RequestMetrics 请求指标收集器测试。"""

    def test_record_request_success(self) -> None:
        """记录成功请求。"""
        metrics = RequestMetrics()
        metrics.record_request("/api/chat", "POST", 200, 50.0)
        summary = metrics.get_summary()

        assert summary["total_requests"] == 1
        ep = summary["endpoints"]["POST:/api/chat"]
        assert ep["request_count"] == 1
        assert ep["error_count"] == 0
        assert ep["avg_latency_ms"] == 50.0

    def test_record_request_error(self) -> None:
        """记录错误请求（状态码 >= 400）。"""
        metrics = RequestMetrics()
        metrics.record_request("/api/chat", "POST", 500, 100.0)
        summary = metrics.get_summary()

        ep = summary["endpoints"]["POST:/api/chat"]
        assert ep["error_count"] == 1
        assert ep["error_rate"] == 1.0

    def test_record_multiple_requests(self) -> None:
        """记录多个请求，验证计数。"""
        metrics = RequestMetrics()
        for _ in range(10):
            metrics.record_request("/api/health", "GET", 200, 10.0)
        for _ in range(3):
            metrics.record_request("/api/health", "GET", 500, 50.0)

        summary = metrics.get_summary()
        ep = summary["endpoints"]["GET:/api/health"]
        assert ep["request_count"] == 13
        assert ep["error_count"] == 3
        assert ep["error_rate"] == round(3 / 13, 4)

    def test_percentiles(self) -> None:
        """验证延迟百分位数计算。"""
        metrics = RequestMetrics()
        # 100 个请求，延迟 1~100
        for i in range(1, 101):
            metrics.record_request("/api/test", "GET", 200, float(i))

        summary = metrics.get_summary()
        ep = summary["endpoints"]["GET:/api/test"]
        assert ep["p50_latency_ms"] == 50.0
        assert ep["min_latency_ms"] == 1.0
        assert ep["max_latency_ms"] == 100.0

    def test_summary_no_requests(self) -> None:
        """无请求时摘要为空。"""
        metrics = RequestMetrics()
        summary = metrics.get_summary()
        assert summary["total_requests"] == 0
        assert summary["active_requests"] == 0
        assert summary["endpoints"] == {}

    def test_increment_decrement_active(self) -> None:
        """活跃请求计数增减。"""
        metrics = RequestMetrics()
        assert metrics.get_summary()["active_requests"] == 0

        metrics.increment_active()
        assert metrics.get_summary()["active_requests"] == 1

        metrics.increment_active()
        assert metrics.get_summary()["active_requests"] == 2

        metrics.decrement_active()
        assert metrics.get_summary()["active_requests"] == 1

    def test_method_normalization(self) -> None:
        """HTTP 方法自动转为大写。"""
        metrics = RequestMetrics()
        metrics.record_request("/api/test", "get", 200)
        summary = metrics.get_summary()
        assert "GET:/api/test" in summary["endpoints"]

    def test_different_endpoints_separate(self) -> None:
        """不同端点独立计数。"""
        metrics = RequestMetrics()
        metrics.record_request("/api/a", "GET", 200)
        metrics.record_request("/api/b", "GET", 200)

        summary = metrics.get_summary()
        assert len(summary["endpoints"]) == 2
        assert summary["total_requests"] == 2


# ============================================================
# CircuitState 枚举测试
# ============================================================


class TestCircuitState:
    """CircuitState 枚举测试。"""

    def test_enum_values(self) -> None:
        """验证枚举值。"""
        assert CircuitState.CLOSED == "closed"
        assert CircuitState.OPEN == "open"
        assert CircuitState.HALF_OPEN == "half_open"

    def test_enum_members_count(self) -> None:
        """验证枚举成员数量。"""
        assert len(CircuitState) == 3


# ============================================================
# CircuitBreaker 测试
# ============================================================


class TestCircuitBreaker:
    """CircuitBreaker 电路断路器测试。"""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker:
        """创建低阈值的断路器便于测试。"""
        return CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=0.1)

    @pytest.mark.asyncio
    async def test_initial_state_closed(self, breaker: CircuitBreaker) -> None:
        """初始状态为 CLOSED。"""
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_success_in_closed(self, breaker: CircuitBreaker) -> None:
        """CLOSED 状态下成功调用。"""
        func = AsyncMock(return_value="ok")
        result = await breaker.call(func)
        assert result == "ok"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_closed_to_open_on_failures(self, breaker: CircuitBreaker) -> None:
        """连续失败达到阈值后转为 OPEN。"""
        func = AsyncMock(side_effect=RuntimeError("fail"))

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(func)

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_rejects_calls(self, breaker: CircuitBreaker) -> None:
        """OPEN 状态下拒绝调用并抛出 CircuitOpenError。"""
        func = AsyncMock(side_effect=RuntimeError("fail"))

        # 触发 OPEN
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(func)

        assert breaker.state == CircuitState.OPEN

        # 以下调用应被拒绝
        with pytest.raises(CircuitOpenError):
            await breaker.call(AsyncMock())

    @pytest.mark.asyncio
    async def test_open_to_half_open_after_timeout(self, breaker: CircuitBreaker) -> None:
        """OPEN 超时后自动转为 HALF_OPEN。"""
        func = AsyncMock(side_effect=RuntimeError("fail"))

        # 触发 OPEN
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(func)

        assert breaker.state == CircuitState.OPEN

        # 等待恢复超时
        await asyncio.sleep(0.15)

        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_to_closed_on_success(
        self, breaker: CircuitBreaker
    ) -> None:
        """HALF_OPEN 下成功调用后恢复 CLOSED。"""
        fail_func = AsyncMock(side_effect=RuntimeError("fail"))

        # 触发 OPEN
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(fail_func)

        # 等待恢复超时
        await asyncio.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN

        # half_open_max_calls 默认 3，连续成功 3 次
        success_func = AsyncMock(return_value="ok")
        for _ in range(3):
            result = await breaker.call(success_func)
            assert result == "ok"

        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_to_open_on_failure(self, breaker: CircuitBreaker) -> None:
        """HALF_OPEN 下失败回到 OPEN。"""
        fail_func = AsyncMock(side_effect=RuntimeError("fail"))

        # 触发 OPEN
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(fail_func)

        # 等待恢复超时
        await asyncio.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN

        # HALF_OPEN 下失败
        with pytest.raises(RuntimeError):
            await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_reset(self, breaker: CircuitBreaker) -> None:
        """reset 重置为 CLOSED。"""
        func = AsyncMock(side_effect=RuntimeError("fail"))

        # 触发 OPEN
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(func)

        assert breaker.state == CircuitState.OPEN

        breaker.reset()
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_get_stats(self, breaker: CircuitBreaker) -> None:
        """验证 get_stats 返回结构。"""
        stats = breaker.get_stats()
        assert stats["name"] == "test"
        assert stats["state"] == CircuitState.CLOSED
        assert stats["failure_count"] == 0
        assert stats["total_calls"] == 0
        assert "failure_threshold" in stats
        assert "recovery_timeout" in stats

    @pytest.mark.asyncio
    async def test_stats_after_failures(self, breaker: CircuitBreaker) -> None:
        """失败后统计信息更新。"""
        func = AsyncMock(side_effect=RuntimeError("fail"))

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(func)

        stats = breaker.get_stats()
        assert stats["total_calls"] == 2
        assert stats["total_failures"] == 2
        assert stats["failure_count"] == 2

    @pytest.mark.asyncio
    async def test_rejected_count(self, breaker: CircuitBreaker) -> None:
        """OPEN 状态下拒绝次数递增。"""
        func = AsyncMock(side_effect=RuntimeError("fail"))

        # 触发 OPEN
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(func)

        # 被拒绝的调用
        for _ in range(5):
            with pytest.raises(CircuitOpenError):
                await breaker.call(AsyncMock())

        stats = breaker.get_stats()
        assert stats["total_rejected"] == 5

    @pytest.mark.asyncio
    async def test_closed_success_resets_failure_count(self, breaker: CircuitBreaker) -> None:
        """CLOSED 下成功重置失败计数。"""
        fail_func = AsyncMock(side_effect=RuntimeError("fail"))
        success_func = AsyncMock(return_value="ok")

        # 失败 2 次
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(fail_func)

        assert breaker.get_stats()["failure_count"] == 2

        # 成功 1 次 → 重置
        await breaker.call(success_func)
        assert breaker.get_stats()["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_custom_threshold(self) -> None:
        """自定义阈值。"""
        breaker = CircuitBreaker(failure_threshold=2)
        func = AsyncMock(side_effect=RuntimeError("fail"))

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(func)

        assert breaker.state == CircuitState.OPEN


# ============================================================
# RequestTraceMiddleware 测试
# ============================================================


class TestRequestTraceMiddleware:
    """RequestTraceMiddleware 请求追踪中间件测试。"""

    def _create_app(self) -> Starlette:
        """创建测试用 Starlette 应用。"""
        async def homepage(request: Request) -> JSONResponse:
            return JSONResponse({"hello": "world"})

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(RequestTraceMiddleware)
        return app

    def test_response_has_request_id(self) -> None:
        """响应头包含 X-Request-ID。"""
        app = self._create_app()
        client = TestClient(app)
        response = client.get("/")
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) == 8

    def test_request_id_unique(self) -> None:
        """不同请求的 X-Request-ID 不同。"""
        app = self._create_app()
        client = TestClient(app)
        ids = set()
        for _ in range(10):
            response = client.get("/")
            ids.add(response.headers["X-Request-ID"])
        assert len(ids) == 10

    def test_request_state_has_request_id(self) -> None:
        """request.state.request_id 被正确设置。"""
        captured_id: str | None = None

        async def check_id(request: Request) -> JSONResponse:
            nonlocal captured_id
            captured_id = request.state.request_id
            return JSONResponse({"ok": True})

        app = Starlette(routes=[Route("/check", check_id)])
        app.add_middleware(RequestTraceMiddleware)
        client = TestClient(app)
        response = client.get("/check")

        assert captured_id is not None
        assert response.headers["X-Request-ID"] == captured_id

    def test_returns_correct_response_body(self) -> None:
        """中间件不影响响应体。"""
        app = self._create_app()
        client = TestClient(app)
        response = client.get("/")
        assert response.json() == {"hello": "world"}
        assert response.status_code == 200


# ============================================================
# RetryExecutor 测试
# ============================================================


class TestRetryExecutor:
    """RetryExecutor 重试执行器测试。"""

    @pytest.mark.asyncio
    async def test_immediate_success(self) -> None:
        """首次调用成功，不重试。"""
        executor = RetryExecutor(max_retries=3)
        func = AsyncMock(return_value="ok")

        result = await executor.execute(func)

        assert result == "ok"
        assert func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_then_success(self) -> None:
        """第 2 次调用成功。"""
        executor = RetryExecutor(max_retries=3, base_delay=0.01, max_delay=0.1)
        func = AsyncMock(side_effect=[RuntimeError("fail"), "ok"])

        result = await executor.execute(func)

        assert result == "ok"
        assert func.call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_fail(self) -> None:
        """所有重试耗尽，抛出最后一次异常。"""
        executor = RetryExecutor(max_retries=2, base_delay=0.01, max_delay=0.1)
        func = AsyncMock(side_effect=RuntimeError("persistent"))

        with pytest.raises(RuntimeError, match="persistent"):
            await executor.execute(func)

        assert func.call_count == 3  # 1 + 2 retries

    @pytest.mark.asyncio
    async def test_zero_retries(self) -> None:
        """max_retries=0 时只调用一次。"""
        executor = RetryExecutor(max_retries=0)
        func = AsyncMock(side_effect=RuntimeError("fail"))

        with pytest.raises(RuntimeError):
            await executor.execute(func)

        assert func.call_count == 1

    @pytest.mark.asyncio
    async def test_retryable_exception_filter(self) -> None:
        """只重试指定类型的异常。"""
        executor = RetryExecutor(max_retries=3, base_delay=0.01, max_delay=0.1)
        func = AsyncMock(side_effect=ValueError("not retryable"))

        # 不把 ValueError 列为可重试异常
        with pytest.raises(ValueError):
            await executor.execute(func, retryable_exceptions=(RuntimeError,))

        assert func.call_count == 1

    @pytest.mark.asyncio
    async def test_retryable_exception_matches(self) -> None:
        """匹配的异常类型会触发重试。"""
        executor = RetryExecutor(max_retries=2, base_delay=0.01, max_delay=0.1)
        func = AsyncMock(side_effect=[RuntimeError("retry"), "ok"])

        result = await executor.execute(func, retryable_exceptions=(RuntimeError,))

        assert result == "ok"
        assert func.call_count == 2

    def test_calculate_delay_exponential(self) -> None:
        """退避延迟指数增长（无抖动）。"""
        executor = RetryExecutor(
            max_retries=5,
            base_delay=1.0,
            max_delay=100.0,
            exponential_base=2.0,
            jitter=False,
        )
        assert executor._calculate_delay(0) == 1.0
        assert executor._calculate_delay(1) == 2.0
        assert executor._calculate_delay(2) == 4.0
        assert executor._calculate_delay(3) == 8.0

    def test_calculate_delay_capped_by_max(self) -> None:
        """延迟不超过 max_delay。"""
        executor = RetryExecutor(
            max_retries=5,
            base_delay=1.0,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=False,
        )
        assert executor._calculate_delay(10) == 5.0
        assert executor._calculate_delay(100) == 5.0

    def test_calculate_delay_with_jitter(self) -> None:
        """带抖动的延迟在合理范围内。"""
        executor = RetryExecutor(
            max_retries=5,
            base_delay=1.0,
            max_delay=100.0,
            jitter=True,
        )
        # 多次采样，延迟应 >= 基础值且 <= max
        for _ in range(20):
            delay = executor._calculate_delay(0)
            assert 1.0 <= delay < 100.0

    @pytest.mark.asyncio
    async def test_kwargs_passed_to_func(self) -> None:
        """关键字参数正确传递给函数。"""
        executor = RetryExecutor(max_retries=0)
        func = AsyncMock(return_value="done")

        await executor.execute(func, retryable_exceptions=(Exception,), arg1="a", arg2="b")

        func.assert_called_once_with(arg1="a", arg2="b")

    @pytest.mark.asyncio
    async def test_args_passed_to_func(self) -> None:
        """位置参数正确传递给函数。"""
        executor = RetryExecutor(max_retries=0)
        func = AsyncMock(return_value="done")

        await executor.execute(func, "pos1", "pos2", retryable_exceptions=(Exception,))

        func.assert_called_once_with("pos1", "pos2")
