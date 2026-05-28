"""LLM 调用日志记录器单元测试。"""

from __future__ import annotations

import asyncio
import time

import pytest

from datapilot_llm.logger import (
    LLMCallLogger,
    LLMCallRecord,
    LLMCallStats,
    get_call_logger,
    reset_call_logger,
)


class TestLLMCallRecord:
    """LLMCallRecord 数据模型测试。"""

    def test_default_values(self) -> None:
        record = LLMCallRecord(
            model="qwen-turbo",
            scene="intent",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=200.0,
            cost=0.00003,
            success=True,
        )
        assert record.error_message == ""
        assert record.timestamp > 0

    def test_error_record(self) -> None:
        record = LLMCallRecord(
            model="deepseek-v3",
            scene="nl2sql",
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=5000.0,
            cost=0.0,
            success=False,
            error_message="HTTP 500: Internal Server Error",
        )
        assert record.success is False
        assert "500" in record.error_message


class TestLLMCallStats:
    """LLMCallStats 数据模型测试。"""

    def test_empty_stats(self) -> None:
        stats = LLMCallStats()
        assert stats.total_calls == 0
        assert stats.success_calls == 0
        assert stats.failed_calls == 0
        assert stats.success_rate == 0.0
        assert stats.avg_latency_ms == 0.0
        assert stats.total_cost == 0.0

    def test_success_rate(self) -> None:
        stats = LLMCallStats(total_calls=10, success_calls=8)
        assert stats.success_rate == 0.8

    def test_success_rate_zero_calls(self) -> None:
        stats = LLMCallStats()
        assert stats.success_rate == 0.0

    def test_success_rate_all_success(self) -> None:
        stats = LLMCallStats(total_calls=5, success_calls=5)
        assert stats.success_rate == 1.0

    def test_success_rate_all_failure(self) -> None:
        stats = LLMCallStats(total_calls=3, success_calls=0)
        assert stats.success_rate == 0.0


class TestLLMCallLogger:
    """LLMCallLogger 单元测试。"""

    def _make_logger(self, max_records: int = 10000) -> LLMCallLogger:
        return LLMCallLogger(max_records=max_records)

    @pytest.mark.asyncio
    async def test_log_single_record(self) -> None:
        """记录单条调用日志。"""
        logger = self._make_logger()
        await logger.log(
            model="qwen-turbo",
            scene="intent",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=200.0,
            cost=0.00003,
            success=True,
        )
        await asyncio.sleep(0)  # 让后台消费者处理队列
        assert logger.record_count == 1

    @pytest.mark.asyncio
    async def test_log_multiple_records(self) -> None:
        """记录多条调用日志。"""
        logger = self._make_logger()
        for i in range(5):
            await logger.log(
                model="qwen-turbo",
                scene="intent",
                prompt_tokens=100,
                completion_tokens=50,
                latency_ms=200.0 + i * 10,
                cost=0.00003,
                success=True,
            )
        await asyncio.sleep(0)  # 让后台消费者处理队列
        assert logger.record_count == 5

    @pytest.mark.asyncio
    async def test_get_stats_all(self) -> None:
        """获取全部统计。"""
        logger = self._make_logger()
        await logger.log("qwen-turbo", "intent", 100, 50, 200, 0.00003, True)
        await logger.log("qwen-turbo", "intent", 100, 50, 300, 0.00003, True)
        await logger.log("deepseek-v3", "nl2sql", 500, 200, 1000, 0.0009, False)
        await asyncio.sleep(0)  # 让后台消费者处理队列

        stats = logger.get_stats()
        assert stats.total_calls == 3
        assert stats.success_calls == 2
        assert stats.failed_calls == 1
        assert abs(stats.success_rate - 2 / 3) < 1e-9
        assert stats.total_prompt_tokens == 700
        assert stats.total_completion_tokens == 300

    @pytest.mark.asyncio
    async def test_get_stats_by_scene(self) -> None:
        """按场景筛选统计。"""
        logger = self._make_logger()
        await logger.log("qwen-turbo", "intent", 100, 50, 200, 0.00003, True)
        await logger.log("deepseek-v3", "nl2sql", 500, 200, 1000, 0.0009, True)
        await logger.log("qwen-plus", "explanation", 200, 100, 500, 0.00036, True)
        await asyncio.sleep(0)  # 让后台消费者处理队列

        stats = logger.get_stats(scene="intent")
        assert stats.total_calls == 1
        assert stats.success_calls == 1

    @pytest.mark.asyncio
    async def test_get_stats_by_model(self) -> None:
        """按模型筛选统计。"""
        logger = self._make_logger()
        await logger.log("qwen-turbo", "intent", 100, 50, 200, 0.00003, True)
        await logger.log("qwen-turbo", "chitchat", 80, 30, 150, 0.000027, True)
        await logger.log("deepseek-v3", "nl2sql", 500, 200, 1000, 0.0009, True)
        await asyncio.sleep(0)  # 让后台消费者处理队列

        stats = logger.get_stats(model="qwen-turbo")
        assert stats.total_calls == 2
        assert stats.total_prompt_tokens == 180

    @pytest.mark.asyncio
    async def test_get_stats_by_time_range(self) -> None:
        """按时间范围筛选统计。"""
        logger = self._make_logger()
        now = time.time()

        # 直接插入带时间戳的记录
        logger._records.append(
            LLMCallRecord(
                model="qwen-turbo", scene="intent", prompt_tokens=100,
                completion_tokens=50, latency_ms=200, cost=0.00003,
                success=True, timestamp=now - 100,
            )
        )
        logger._records.append(
            LLMCallRecord(
                model="qwen-turbo", scene="intent", prompt_tokens=100,
                completion_tokens=50, latency_ms=300, cost=0.00003,
                success=True, timestamp=now,
            )
        )

        stats = logger.get_stats(since=now - 50)
        assert stats.total_calls == 1

    @pytest.mark.asyncio
    async def test_get_stats_by_model_dimension(self) -> None:
        """按模型维度分组统计。"""
        logger = self._make_logger()
        await logger.log("qwen-turbo", "intent", 100, 50, 200, 0.00003, True)
        await logger.log("qwen-turbo", "chitchat", 80, 30, 150, 0.000027, True)
        await logger.log("deepseek-v3", "nl2sql", 500, 200, 1000, 0.0009, True)
        await asyncio.sleep(0)  # 让后台消费者处理队列

        stats_by_model = logger.get_stats_by_model()
        assert "qwen-turbo" in stats_by_model
        assert "deepseek-v3" in stats_by_model
        assert stats_by_model["qwen-turbo"].total_calls == 2
        assert stats_by_model["deepseek-v3"].total_calls == 1

    @pytest.mark.asyncio
    async def test_empty_stats(self) -> None:
        """空日志返回零值统计。"""
        logger = self._make_logger()
        stats = logger.get_stats()
        assert stats.total_calls == 0
        assert stats.success_rate == 0.0

    @pytest.mark.asyncio
    async def test_avg_latency(self) -> None:
        """平均延迟计算正确。"""
        logger = self._make_logger()
        await logger.log("qwen-turbo", "intent", 0, 0, 200, 0, True)
        await logger.log("qwen-turbo", "intent", 0, 0, 400, 0, True)
        await asyncio.sleep(0)  # 让后台消费者处理队列

        stats = logger.get_stats()
        assert stats.avg_latency_ms == 300.0

    @pytest.mark.asyncio
    async def test_max_records_limit(self) -> None:
        """超过最大记录数时自动淘汰旧记录。"""
        logger = self._make_logger(max_records=10)
        for i in range(20):
            await logger.log(
                model="qwen-turbo",
                scene="intent",
                prompt_tokens=100,
                completion_tokens=50,
                latency_ms=200.0,
                cost=0.00003,
                success=True,
            )
            await asyncio.sleep(0)  # 让后台消费者处理队列
        # 超过 max_records 后会淘汰旧记录
        assert logger.record_count <= 10

    def test_get_call_logger_singleton(self) -> None:
        """get_call_logger 返回单例。"""
        reset_call_logger()
        logger1 = get_call_logger()
        logger2 = get_call_logger()
        assert logger1 is logger2

    def test_reset_call_logger(self) -> None:
        """reset_call_logger 重置单例。"""
        reset_call_logger()
        logger1 = get_call_logger()
        reset_call_logger()
        logger2 = get_call_logger()
        assert logger1 is not logger2
