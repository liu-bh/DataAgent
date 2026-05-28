"""差异化重试策略。

针对数据库查询中不同类型的错误进行分类处理：
- 临时错误（连接超时、死锁等）允许重试，使用指数退避策略。
- 永久错误（语法错误、权限不足等）直接终止，不重试。

用法::

    from datapilot_queryexec.connectors.retry import RetryPolicy

    policy = RetryPolicy(max_retries=3, base_delay=1.0)

    for attempt in range(policy.max_retries + 1):
        try:
            result = await connector.execute(sql)
            break
        except Exception as exc:
            if not policy.should_retry(exc) or attempt >= policy.max_retries:
                raise
            await policy.wait(attempt)
"""

from __future__ import annotations

import asyncio
import random

import structlog

logger = structlog.get_logger(__name__)

# 临时错误关键词，匹配到这些关键词时允许重试
_TRANSIENT_ERROR_KEYWORDS = frozenset(
    {
        "deadlock",
        "timeout",
        "timed out",
        "connection refused",
        "connection reset",
        "too many connections",
        "lock wait timeout",
        "server has gone away",
        "broken pipe",
        "network is unreachable",
        "temporary failure",
    }
)

# 永久错误类型，匹配到这些类型时直接终止
_PERMANENT_ERROR_TYPES = (
    SyntaxError,
    ValueError,  # 参数格式错误
)


class RetryPolicy:
    """差异化重试策略。

    Attributes:
        max_retries: 最大重试次数。
        base_delay: 基础延迟时间（秒）。
        max_delay: 最大延迟时间（秒）。
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
    ) -> None:
        """初始化重试策略。

        Args:
            max_retries: 最大重试次数。
            base_delay: 基础延迟时间（秒），指数退避的起始值。
            max_delay: 最大延迟时间（秒），防止退避时间过长。
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def should_retry(self, error: Exception) -> bool:
        """判断错误是否应该重试。

        分类规则：
        - 临时错误：ConnectionError、TimeoutError、数据库 OperationalError
          中的死锁/超时等，允许重试。
        - 永久错误：SyntaxError、ValueError、数据库 ProgrammingError
          （语法错误），不重试。
        - 其他未知错误默认不重试。

        Args:
            error: 捕获的异常对象。

        Returns:
            True 表示应该重试，False 表示直接终止。
        """
        # 1. 检查永久错误类型（Python 原生异常）
        if isinstance(error, _PERMANENT_ERROR_TYPES):
            logger.debug(
                "永久错误，不重试",
                error_type=type(error).__name__,
                error_message=str(error),
            )
            return False

        # 2. 检查临时错误类型（Python 原生异常）
        if isinstance(error, (ConnectionError, TimeoutError, OSError)):
            logger.debug(
                "临时错误，允许重试",
                error_type=type(error).__name__,
                error_message=str(error),
            )
            return True

        # 3. 检查数据库驱动异常（通过类名匹配）
        error_class_name = type(error).__name__
        error_message = str(error).lower()

        # ProgrammingError 通常是语法错误，不重试
        if error_class_name == "ProgrammingError":
            logger.debug(
                "SQL 语法错误，不重试",
                error_type=error_class_name,
                error_message=str(error),
            )
            return False

        # OperationalError 中检查是否为临时性错误
        if error_class_name == "OperationalError":
            for keyword in _TRANSIENT_ERROR_KEYWORDS:
                if keyword in error_message:
                    logger.debug(
                        "数据库临时错误，允许重试",
                        error_type=error_class_name,
                        keyword=keyword,
                    )
                    return True
            # 其他 OperationalError 不重试
            logger.debug(
                "数据库操作错误（非临时），不重试",
                error_type=error_class_name,
                error_message=str(error),
            )
            return False

        # 4. 通过错误消息关键词检测临时性错误（兜底逻辑）
        for keyword in _TRANSIENT_ERROR_KEYWORDS:
            if keyword in error_message:
                logger.debug(
                    "通过关键词识别为临时错误，允许重试",
                    keyword=keyword,
                )
                return True

        # 5. 默认不重试
        logger.debug(
            "未知错误类型，默认不重试",
            error_type=error_class_name,
            error_message=str(error),
        )
        return False

    async def wait(self, attempt: int) -> None:
        """指数退避等待。

        等待时间公式: base_delay * (2 ** attempt) + random jitter
        jitter 范围: [0, base_delay * 0.5)

        Args:
            attempt: 当前重试次数（从 0 开始）。
        """
        # 计算指数退避时间
        delay = self.base_delay * (2**attempt)

        # 添加随机抖动，防止多个客户端同时重试（惊群效应）
        jitter = random.uniform(0, self.base_delay * 0.5)
        total_delay = min(delay + jitter, self.max_delay)

        logger.debug(
            "重试等待",
            attempt=attempt,
            delay=delay,
            jitter=jitter,
            total_delay=total_delay,
        )
        await asyncio.sleep(total_delay)
