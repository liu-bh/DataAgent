"""重试执行器。

支持指数退避和可重试异常判断。
"""

from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)


class RetryExecutor:
    """异步重试执行器。

    失败时以指数退避策略重试，支持随机抖动避免惊群效应。

    Args:
        max_retries: 最大重试次数（不含首次调用）。
        base_delay: 基础延迟（秒）。
        max_delay: 最大延迟上限（秒）。
        exponential_base: 指数底数。
        jitter: 是否添加随机抖动。
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._exponential_base = exponential_base
        self._jitter = jitter

    async def execute(
        self,
        func: Callable,
        *args: Any,
        retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
        **kwargs: Any,
    ) -> Any:
        """执行函数，失败时指数退避重试。

        退避公式::

            delay = min(base_delay * (exponential_base ** attempt) + jitter, max_delay)

        Args:
            func: 要执行的异步函数。
            *args: 函数位置参数。
            retryable_exceptions: 可重试的异常类型元组。
            **kwargs: 函数关键字参数。

        Returns:
            函数执行结果。

        Raises:
            Exception: 所有重试耗尽后抛出最后一次异常。
        """
        last_exception: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except retryable_exceptions as exc:
                last_exception = exc
                if attempt < self._max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        "重试执行",
                        attempt=attempt + 1,
                        max_retries=self._max_retries,
                        delay_seconds=round(delay, 3),
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "重试耗尽",
                        max_retries=self._max_retries,
                        error=str(exc),
                    )

        # 理论上不会走到这里，但为了类型安全
        raise last_exception  # type: ignore[misc]

    def _calculate_delay(self, attempt: int) -> float:
        """计算第 attempt 次重试的等待时间。

        Args:
            attempt: 当前重试次序（从 0 开始）。

        Returns:
            等待时间（秒）。
        """
        delay = self._base_delay * (self._exponential_base**attempt)
        if self._jitter:
            delay += random.uniform(0, self._base_delay)
        return min(delay, self._max_delay)
