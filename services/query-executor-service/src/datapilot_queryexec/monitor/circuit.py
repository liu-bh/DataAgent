"""数据源熔断器。

实现熔断模式：连续失败达到阈值后熔断，等待超时后进入半开探测，
探测成功则恢复，失败则继续熔断。
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import structlog

from .models import CircuitState

logger = structlog.get_logger(__name__)


@dataclass
class _CircuitEntry:
    """单个数据源的熔断状态。"""

    state: str = CircuitState.CLOSED
    consecutive_failures: int = 0
    opened_at: float = 0.0  # 进入 OPEN 状态的时间戳
    half_open_calls: int = 0  # 半开状态下的探测次数


class DataSourceCircuitBreaker:
    """数据源熔断器，不可达自动摘除，半开探测恢复。

    状态机::

        CLOSED → (连续失败 >= threshold) → OPEN
        OPEN   → (等待 recovery_timeout) → HALF_OPEN
        HALF_OPEN → (探测成功) → CLOSED
        HALF_OPEN → (探测失败) → OPEN
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
    ) -> None:
        """初始化熔断器。

        Args:
            failure_threshold: 连续失败次数阈值，达到后触发熔断。
            recovery_timeout: 熔断后等待时间（秒），超时后进入半开状态。
            half_open_max_calls: 半开状态下最多允许的探测调用次数。
        """
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls
        self._entries: dict[str, _CircuitEntry] = {}

    def _get_entry(self, datasource_id: str) -> _CircuitEntry:
        """获取或创建熔断状态条目。"""
        if datasource_id not in self._entries:
            self._entries[datasource_id] = _CircuitEntry()
        return self._entries[datasource_id]

    def record_success(self, datasource_id: str) -> CircuitState:
        """记录成功调用。

        如果当前处于半开状态且探测成功，恢复为 CLOSED。

        Args:
            datasource_id: 数据源 ID。

        Returns:
            更新后的熔断状态。
        """
        entry = self._get_entry(datasource_id)
        entry.consecutive_failures = 0

        if entry.state == CircuitState.HALF_OPEN:
            entry.state = CircuitState.CLOSED
            entry.half_open_calls = 0
            logger.info(
                "数据源熔断恢复",
                datasource_id=datasource_id,
                new_state=CircuitState.CLOSED,
            )
        return CircuitState(entry.state)

    def record_failure(self, datasource_id: str) -> CircuitState:
        """记录失败调用。

        CLOSED 状态下连续失败达到阈值后转为 OPEN。
        HALF_OPEN 状态下直接转为 OPEN。

        Args:
            datasource_id: 数据源 ID。

        Returns:
            更新后的熔断状态。
        """
        entry = self._get_entry(datasource_id)
        entry.consecutive_failures += 1

        if entry.state == CircuitState.HALF_OPEN:
            # 半开状态下探测失败，重新熔断
            entry.state = CircuitState.OPEN
            entry.opened_at = time.monotonic()
            entry.half_open_calls = 0
            logger.warning(
                "数据源半开探测失败，重新熔断",
                datasource_id=datasource_id,
                consecutive_failures=entry.consecutive_failures,
            )
        elif (
            entry.state == CircuitState.CLOSED
            and entry.consecutive_failures >= self._failure_threshold
        ):
            entry.state = CircuitState.OPEN
            entry.opened_at = time.monotonic()
            logger.warning(
                "数据源熔断触发",
                datasource_id=datasource_id,
                consecutive_failures=entry.consecutive_failures,
                threshold=self._failure_threshold,
            )

        return CircuitState(entry.state)

    def get_state(self, datasource_id: str) -> CircuitState:
        """获取熔断状态。

        如果当前为 OPEN 状态且已超过 recovery_timeout，自动转为 HALF_OPEN。

        Args:
            datasource_id: 数据源 ID。

        Returns:
            当前熔断状态。
        """
        entry = self._get_entry(datasource_id)

        if entry.state == CircuitState.OPEN:
            elapsed = time.monotonic() - entry.opened_at
            if elapsed >= self._recovery_timeout:
                entry.state = CircuitState.HALF_OPEN
                entry.half_open_calls = 0
                logger.info(
                    "数据源进入半开状态",
                    datasource_id=datasource_id,
                    elapsed_seconds=elapsed,
                )

        return CircuitState(entry.state)

    def is_allowed(self, datasource_id: str) -> bool:
        """判断是否允许请求通过。

        CLOSED 状态允许；OPEN 状态拒绝；
        HALF_OPEN 状态允许有限次数的探测请求。

        Args:
            datasource_id: 数据源 ID。

        Returns:
            是否允许请求通过。
        """
        state = self.get_state(datasource_id)

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            return False

        # HALF_OPEN 状态：限制探测次数
        entry = self._get_entry(datasource_id)
        if entry.half_open_calls < self._half_open_max_calls:
            entry.half_open_calls += 1
            return True

        return False
