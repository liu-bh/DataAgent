"""电路断路器。

三态模型：CLOSED → OPEN → HALF_OPEN → CLOSED

- CLOSED: 正常调用，失败计数，达到阈值后转 OPEN
- OPEN: 拒绝调用，等待恢复超时后转 HALF_OPEN
- HALF_OPEN: 允许有限调用，成功恢复 CLOSED，失败回到 OPEN
"""

from __future__ import annotations

import asyncio
import time
from enum import StrEnum
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)


class CircuitState(StrEnum):
    """断路器状态枚举。"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """断路器打开时的异常。"""

    pass


class CircuitBreaker:
    """电路断路器。

    保护下游服务不被过载请求压垮，提供故障恢复机制。

    Args:
        name: 断路器名称，用于日志标识。
        failure_threshold: CLOSED 状态下连续失败次数阈值。
        recovery_timeout: OPEN 状态持续时长（秒），超时后转 HALF_OPEN。
        half_open_max_calls: HALF_OPEN 状态下允许的最大试探调用次数。
    """

    def __init__(
        self,
        name: str = "",
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        # 内部状态
        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls: int = 0

        # 统计
        self._total_calls: int = 0
        self._total_successes: int = 0
        self._total_failures: int = 0
        self._total_rejected: int = 0

    @property
    def state(self) -> CircuitState:
        """返回当前断路器状态。

        如果处于 OPEN 状态且超过恢复超时时间，自动转为 HALF_OPEN。

        Returns:
            当前断路器状态。
        """
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                logger.info(
                    "断路器状态转换",
                    name=self._name,
                    from_state="open",
                    to_state="half_open",
                )
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """通过断路器调用函数。

        CLOSED: 正常调用，失败计数
        OPEN: 直接抛出 CircuitOpenError
        HALF_OPEN: 允许有限调用，成功恢复 CLOSED，失败回到 OPEN

        Args:
            func: 要调用的异步函数。
            *args: 函数位置参数。
            **kwargs: 函数关键字参数。

        Returns:
            函数调用结果。

        Raises:
            CircuitOpenError: �路器处于 OPEN 状态。
            Exception: 函数本身抛出的异常。
        """
        current_state = self.state

        if current_state == CircuitState.OPEN:
            self._total_rejected += 1
            raise CircuitOpenError(
                f"断路器 [{self._name}] 处于 OPEN 状态，拒绝调用"
            )

        self._total_calls += 1

        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as exc:
            self._record_failure()
            raise

    def _record_success(self) -> None:
        """记录一次成功调用。"""
        self._total_successes += 1
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            # HALF_OPEN 下达到最大试探次数且都成功 → CLOSED
            if self._half_open_calls >= self._half_open_max_calls:
                logger.info(
                    "断路器状态转换",
                    name=self._name,
                    from_state="half_open",
                    to_state="closed",
                )
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
        elif self._state == CircuitState.CLOSED:
            # CLOSED 下成功，重置失败计数
            self._failure_count = 0
            self._success_count += 1

    def _record_failure(self) -> None:
        """记录一次失败调用。"""
        self._total_failures += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            # HALF_OPEN 下失败 → 回到 OPEN
            logger.warning(
                "断路器状态转换",
                name=self._name,
                from_state="half_open",
                to_state="open",
            )
            self._state = CircuitState.OPEN
            self._half_open_calls = 0
        elif self._state == CircuitState.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self._failure_threshold:
                # 达到阈值 → OPEN
                logger.warning(
                    "断路器状态转换",
                    name=self._name,
                    from_state="closed",
                    to_state="open",
                    failure_count=self._failure_count,
                    threshold=self._failure_threshold,
                )
                self._state = CircuitState.OPEN

    def get_stats(self) -> dict[str, Any]:
        """返回断路器统计信息。

        Returns:
            包含状态、计数等信息的字典。
        """
        return {
            "name": self._name,
            "state": self.state,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self._failure_threshold,
            "recovery_timeout": self._recovery_timeout,
            "half_open_max_calls": self._half_open_max_calls,
            "last_failure_time": self._last_failure_time,
            "total_calls": self._total_calls,
            "total_successes": self._total_successes,
            "total_failures": self._total_failures,
            "total_rejected": self._total_rejected,
        }

    def reset(self) -> None:
        """重置断路器状态为 CLOSED。"""
        logger.info("断路器重置", name=self._name)
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time = 0.0
