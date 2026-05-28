"""LLM 调用日志记录器。

异步记录每次 LLM 调用的详细信息，提供统计查询接口。
使用内存队列 + 后台任务实现非阻塞写入。
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class LLMCallRecord:
    """单次 LLM 调用记录。

    Attributes:
        model: 模型标识符。
        scene: 使用场景。
        prompt_tokens: 输入 token 数。
        completion_tokens: 输出 token 数。
        latency_ms: 请求耗时（毫秒）。
        cost: 调用成本（元）。
        success: 是否成功。
        error_message: 错误信息（失败时）。
        timestamp: 记录时间戳（epoch 秒）。
    """

    model: str
    scene: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cost: float
    success: bool
    error_message: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class LLMCallStats:
    """LLM 调用统计汇总。

    Attributes:
        total_calls: 总调用次数。
        success_calls: 成功调用次数。
        failed_calls: 失败调用次数。
        success_rate: 成功率。
        avg_latency_ms: 平均延迟（毫秒）。
        total_cost: 总成本（元）。
        total_prompt_tokens: 总输入 token 数。
        total_completion_tokens: 总输出 token 数。
    """

    total_calls: int = 0
    success_calls: int = 0
    failed_calls: int = 0
    avg_latency_ms: float = 0.0
    total_cost: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0

    @property
    def success_rate(self) -> float:
        """成功率（0.0 ~ 1.0）。"""
        if self.total_calls == 0:
            return 0.0
        return self.success_calls / self.total_calls


class LLMCallLogger:
    """LLM 调用日志记录器。

    使用异步队列实现非阻塞写入，后台消费者负责持久化。
    支持按时间范围、场景、模型维度汇总统计。

    用法::

        call_logger = get_call_logger()
        await call_logger.log(
            model="qwen-turbo",
            scene="intent",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=200.5,
            cost=0.000045,
            success=True,
        )
        stats = call_logger.get_stats(scene="intent")
    """

    def __init__(self, max_records: int = 10000) -> None:
        self._records: list[LLMCallRecord] = []
        self._max_records = max_records
        self._queue: asyncio.Queue[LLMCallRecord | None] = asyncio.Queue(maxsize=1000)
        self._consumer_task: asyncio.Task[None] | None = None

    def _start_consumer(self) -> None:
        """启动后台消费者任务（如果尚未启动）。"""
        if self._consumer_task is None or self._consumer_task.done():
            self._consumer_task = asyncio.create_task(self._consume())

    async def _consume(self) -> None:
        """后台消费者：从队列取出记录并存储。"""
        while True:
            record = await self._queue.get()
            if record is None:
                # 毒丸信号，停止消费
                break
            self._add_record(record)
            self._queue.task_done()

    def _add_record(self, record: LLMCallRecord) -> None:
        """添加记录到内存存储，超过上限时淘汰最旧的记录。"""
        self._records.append(record)
        if len(self._records) > self._max_records:
            # 淘汰最旧的一半记录
            self._records = self._records[len(self._records) // 2:]

    async def log(
        self,
        model: str,
        scene: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        cost: float,
        success: bool,
        error_message: str = "",
    ) -> None:
        """异步记录一次 LLM 调用。

        通过队列异步写入，不阻塞调用方。

        Args:
            model: 模型标识符。
            scene: 使用场景。
            prompt_tokens: 输入 token 数。
            completion_tokens: 输出 token 数。
            latency_ms: 请求耗时（毫秒）。
            cost: 调用成本（元）。
            success: 是否成功。
            error_message: 错误信息。
        """
        record = LLMCallRecord(
            model=model,
            scene=scene,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            cost=cost,
            success=success,
            error_message=error_message,
        )

        # 尝试放入队列，队列满时直接同步写入
        try:
            self._queue.put_nowait(record)
            self._start_consumer()
        except asyncio.QueueFull:
            # 队列满时降级为同步写入
            logger.debug("llm_call_logger_queue_full", fallback="sync")
            self._add_record(record)

    def get_stats(
        self,
        *,
        scene: str | None = None,
        model: str | None = None,
        since: float | None = None,
        until: float | None = None,
    ) -> LLMCallStats:
        """获取调用统计汇总。

        Args:
            scene: 按场景筛选，None 表示不限。
            model: 按模型筛选，None 表示不限。
            since: 起始时间戳（epoch 秒），None 表示不限。
            until: 结束时间戳（epoch 秒），None 表示不限。

        Returns:
            LLMCallStats 统计汇总结果。
        """
        filtered = self._filter_records(
            scene=scene, model=model, since=since, until=until
        )

        if not filtered:
            return LLMCallStats()

        total_calls = len(filtered)
        success_calls = sum(1 for r in filtered if r.success)
        failed_calls = total_calls - success_calls
        total_latency = sum(r.latency_ms for r in filtered)
        total_cost = sum(r.cost for r in filtered)
        total_prompt_tokens = sum(r.prompt_tokens for r in filtered)
        total_completion_tokens = sum(r.completion_tokens for r in filtered)

        return LLMCallStats(
            total_calls=total_calls,
            success_calls=success_calls,
            failed_calls=failed_calls,
            avg_latency_ms=round(total_latency / total_calls, 2),
            total_cost=round(total_cost, 6),
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
        )

    def get_stats_by_model(
        self,
        *,
        scene: str | None = None,
        since: float | None = None,
        until: float | None = None,
    ) -> dict[str, LLMCallStats]:
        """按模型维度获取统计汇总。

        Args:
            scene: 按场景筛选。
            since: 起始时间戳。
            until: 结束时间戳。

        Returns:
            模型标识符到统计结果的映射。
        """
        filtered = self._filter_records(
            scene=scene, since=since, until=until
        )

        model_records: dict[str, list[LLMCallRecord]] = defaultdict(list)
        for record in filtered:
            model_records[record.model].append(record)

        result: dict[str, LLMCallStats] = {}
        for model_id, records in model_records.items():
            total = len(records)
            success = sum(1 for r in records if r.success)
            result[model_id] = LLMCallStats(
                total_calls=total,
                success_calls=success,
                failed_calls=total - success,
                avg_latency_ms=round(
                    sum(r.latency_ms for r in records) / total, 2
                ),
                total_cost=round(sum(r.cost for r in records), 6),
                total_prompt_tokens=sum(r.prompt_tokens for r in records),
                total_completion_tokens=sum(r.completion_tokens for r in records),
            )

        return result

    def _filter_records(
        self,
        *,
        scene: str | None = None,
        model: str | None = None,
        since: float | None = None,
        until: float | None = None,
    ) -> list[LLMCallRecord]:
        """按条件筛选记录。"""
        result = self._records
        if scene is not None:
            result = [r for r in result if r.scene == scene]
        if model is not None:
            result = [r for r in result if r.model == model]
        if since is not None:
            result = [r for r in result if r.timestamp >= since]
        if until is not None:
            result = [r for r in result if r.timestamp <= until]
        return result

    @property
    def record_count(self) -> int:
        """当前存储的记录数。"""
        return len(self._records)

    async def close(self) -> None:
        """关闭日志记录器，等待队列消费完毕。"""
        await self._queue.put(None)  # 发送毒丸信号
        if self._consumer_task is not None and not self._consumer_task.done():
            await self._consumer_task
        logger.info(
            "llm_call_logger_closed",
            remaining_records=self.record_count,
        )


# 模块级单例
_call_logger: LLMCallLogger | None = None


def get_call_logger() -> LLMCallLogger:
    """获取 LLM 调用日志记录器单例。

    Returns:
        LLMCallLogger 全局单例实例。
    """
    global _call_logger
    if _call_logger is None:
        _call_logger = LLMCallLogger()
    return _call_logger


def reset_call_logger() -> None:
    """重置调用日志记录器（主要用于测试）。"""
    global _call_logger
    _call_logger = None
