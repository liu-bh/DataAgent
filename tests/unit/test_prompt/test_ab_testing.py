"""A/B 测试分流逻辑单元测试。

测试 ABTestingManager 的流量分配、效果记录和统计对比逻辑。
使用 mock Redis 客户端。
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from uuid import uuid4, UUID

from datapilot_prompt.ab_testing import ABTestingManager, PromptStatistics


@pytest.fixture
def mock_redis() -> AsyncMock:
    """创建模拟 Redis 客户端。"""
    return AsyncMock()


@pytest.fixture
def ab_manager(mock_redis: AsyncMock) -> ABTestingManager:
    """创建 ABTestingManager 实例。"""
    return ABTestingManager(redis=mock_redis)


class TestABTestingAssignVersion:
    """assign_version 流量分配测试。"""

    @pytest.mark.asyncio
    async def test_no_ab_versions_returns_active(self, ab_manager: ABTestingManager) -> None:
        """没有 A/B 测试版本时直接返回 active 版本。"""
        active_id = uuid4()
        result = await ab_manager.assign_version(
            active_prompt_id=active_id,
            ab_versions={},
        )
        assert result == active_id

    @pytest.mark.asyncio
    async def test_zero_traffic_returns_active(self, ab_manager: ABTestingManager) -> None:
        """A/B 流量为 0 时返回 active 版本。"""
        active_id = uuid4()
        ab_id = uuid4()
        result = await ab_manager.assign_version(
            active_prompt_id=active_id,
            ab_versions={ab_id: 0.0},
        )
        assert result == active_id

    @pytest.mark.asyncio
    async def test_100_percent_ab_traffic(self, ab_manager: ABTestingManager) -> None:
        """100% 流量分配给 A/B 版本时，不会返回 active 版本。"""
        active_id = uuid4()
        ab_id = uuid4()

        # 执行多次确保全部命中 ab 版本
        results = []
        for _ in range(100):
            with patch("datapilot_prompt.ab_testing.random.random", return_value=0.99):
                result = await ab_manager.assign_version(
                    active_prompt_id=active_id,
                    ab_versions={ab_id: 1.0},
                )
                results.append(result)

        assert all(r == ab_id for r in results)

    @pytest.mark.asyncio
    async def test_partial_traffic_distribution(self, ab_manager: ABTestingManager) -> None:
        """验证部分流量分配。"""
        active_id = uuid4()
        ab_id = uuid4()

        # 模拟 rand = 0.85（落在 0.8~1.0 之间，应命中 ab 版本）
        with patch("datapilot_prompt.ab_testing.random.random", return_value=0.85):
            result = await ab_manager.assign_version(
                active_prompt_id=active_id,
                ab_versions={ab_id: 0.2},
            )
            assert result == ab_id

        # 模拟 rand = 0.5（落在 0~0.8 之间，应命中 active 版本）
        with patch("datapilot_prompt.ab_testing.random.random", return_value=0.5):
            result = await ab_manager.assign_version(
                active_prompt_id=active_id,
                ab_versions={ab_id: 0.2},
            )
            assert result == active_id

    @pytest.mark.asyncio
    async def test_multiple_ab_versions(self, ab_manager: ABTestingManager) -> None:
        """多个 A/B 版本分流测试。"""
        active_id = uuid4()
        ab_id_1 = uuid4()
        ab_id_2 = uuid4()

        # rand = 0.95 → active 获 0.7，剩余 0.25，ab_id_1 获 0.15（累计 0.15），ab_id_2 获 0.15
        # 0.95 - 0.7 = 0.25 > 0.15 (ab_id_1 的流量) → 命中 ab_id_2
        with patch("datapilot_prompt.ab_testing.random.random", return_value=0.95):
            result = await ab_manager.assign_version(
                active_prompt_id=active_id,
                ab_versions={ab_id_1: 0.15, ab_id_2: 0.15},
            )
            assert result == ab_id_2


class TestABTestingRecordOutcome:
    """record_outcome 效果记录测试。"""

    @pytest.mark.asyncio
    async def test_record_success(self, ab_manager: ABTestingManager, mock_redis: AsyncMock) -> None:
        """记录成功结果。"""
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock()
        # pipeline() 在 redis.asyncio 中是同步方法，返回 Pipeline 对象
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        prompt_id = uuid4()
        await ab_manager.record_outcome(prompt_id, success=True, latency_ms=150.0)

        mock_redis.pipeline.assert_called_once()
        # total_requests + success_count 共 2 次 incr
        assert mock_pipe.incr.call_count == 2
        assert mock_pipe.incrbyfloat.call_count == 1  # total_latency_ms

    @pytest.mark.asyncio
    async def test_record_failure(self, ab_manager: ABTestingManager, mock_redis: AsyncMock) -> None:
        """记录失败结果。"""
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        prompt_id = uuid4()
        await ab_manager.record_outcome(prompt_id, success=False, latency_ms=200.0)

        mock_redis.pipeline.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_user_feedback_edited(self, ab_manager: ABTestingManager, mock_redis: AsyncMock) -> None:
        """记录用户编辑反馈。"""
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        prompt_id = uuid4()
        await ab_manager.record_user_feedback(prompt_id, edited=True)

        mock_redis.pipeline.assert_called_once()
        mock_pipe.incr.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_user_feedback_satisfied(self, ab_manager: ABTestingManager, mock_redis: AsyncMock) -> None:
        """记录用户满意反馈。"""
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        prompt_id = uuid4()
        await ab_manager.record_user_feedback(prompt_id, satisfied=True)

        mock_redis.pipeline.assert_called_once()
        mock_pipe.incr.assert_called_once()


class TestABTestingStatistics:
    """get_statistics 统计查询测试。"""

    @pytest.mark.asyncio
    async def test_get_statistics_with_data(self, ab_manager: ABTestingManager, mock_redis: AsyncMock) -> None:
        """有数据时正确统计。"""
        prompt_id = uuid4()
        # mget 返回值顺序: total, success, fail, latency, edit, satisfied, dissatisfied
        mock_redis.mget.return_value = [
            "1000",  # total_requests
            "750",   # success_count
            "250",   # fail_count
            "50000.0",  # total_latency_ms
            "100",   # user_edit_count
            "600",   # satisfied_count
            "50",    # dissatisfied_count
        ]

        stats = await ab_manager.get_statistics(prompt_id)

        assert stats.total_requests == 1000
        assert stats.success_count == 750
        assert stats.fail_count == 250
        assert stats.total_latency_ms == 50000.0
        assert stats.user_edit_count == 100
        assert stats.user_satisfied_count == 600
        assert stats.user_dissatisfied_count == 50

    @pytest.mark.asyncio
    async def test_get_statistics_empty(self, ab_manager: ABTestingManager, mock_redis: AsyncMock) -> None:
        """无数据时返回零值。"""
        prompt_id = uuid4()
        mock_redis.mget.return_value = [None, None, None, None, None, None, None]

        stats = await ab_manager.get_statistics(prompt_id)

        assert stats.total_requests == 0
        assert stats.success_count == 0
        assert stats.success_rate == 0.0
        assert stats.avg_latency_ms == 0.0

    @pytest.mark.asyncio
    async def test_statistics_rate_calculation(self) -> None:
        """统计指标计算正确性。"""
        stats = PromptStatistics(
            prompt_id=uuid4(),
            total_requests=1000,
            success_count=750,
            fail_count=250,
            total_latency_ms=50000.0,
            user_edit_count=100,
            user_satisfied_count=600,
            user_dissatisfied_count=50,
        )

        assert stats.success_rate == 0.75
        assert stats.avg_latency_ms == 50.0
        assert stats.user_edit_rate == 0.1
        # satisfaction_rate = 600 / (600 + 50)
        assert stats.satisfaction_rate == pytest.approx(0.9231, rel=1e-3)


class TestABTestingCompareVersions:
    """compare_versions 版本对比测试。"""

    def test_insufficient_samples(self, ab_manager: ABTestingManager) -> None:
        """样本数不足时返回无显著差异。"""
        stats_a = PromptStatistics(prompt_id=uuid4(), total_requests=500)
        stats_b = PromptStatistics(prompt_id=uuid4(), total_requests=500)

        recommendation, confidence = ab_manager.compare_versions(
            stats_a, stats_b, traffic_a=0.8, traffic_b=0.2
        )

        assert recommendation == "no_significant_difference"
        assert confidence == 0.0

    def test_identical_performance(self, ab_manager: ABTestingManager) -> None:
        """性能完全相同时无显著差异。"""
        stats_a = PromptStatistics(prompt_id=uuid4(), total_requests=1000, success_count=750)
        stats_b = PromptStatistics(prompt_id=uuid4(), total_requests=1000, success_count=750)

        recommendation, _ = ab_manager.compare_versions(
            stats_a, stats_b, traffic_a=0.8, traffic_b=0.2
        )

        assert recommendation == "no_significant_difference"

    def test_b_significantly_better(self, ab_manager: ABTestingManager) -> None:
        """版本 B 显著优于 A。"""
        stats_a = PromptStatistics(prompt_id=uuid4(), total_requests=1000, success_count=700)
        stats_b = PromptStatistics(prompt_id=uuid4(), total_requests=1000, success_count=780)

        recommendation, confidence = ab_manager.compare_versions(
            stats_a, stats_b, traffic_a=0.8, traffic_b=0.2
        )

        assert recommendation == "version_b"
        assert confidence > 0.5

    def test_a_significantly_better(self, ab_manager: ABTestingManager) -> None:
        """版本 A 显著优于 B。"""
        stats_a = PromptStatistics(prompt_id=uuid4(), total_requests=1000, success_count=780)
        stats_b = PromptStatistics(prompt_id=uuid4(), total_requests=1000, success_count=700)

        recommendation, confidence = ab_manager.compare_versions(
            stats_a, stats_b, traffic_a=0.8, traffic_b=0.2
        )

        assert recommendation == "version_a"
        assert confidence > 0.5

    def test_below_min_significant_diff(self, ab_manager: ABTestingManager) -> None:
        """差异低于最小显著差异时返回无显著差异。"""
        # 70% vs 71% — 差异 1%，低于 2% 阈值
        stats_a = PromptStatistics(prompt_id=uuid4(), total_requests=2000, success_count=1400)
        stats_b = PromptStatistics(prompt_id=uuid4(), total_requests=2000, success_count=1420)

        recommendation, _ = ab_manager.compare_versions(
            stats_a, stats_b, traffic_a=0.5, traffic_b=0.5
        )

        # 差异 1% < 2%，应返回 no_significant_difference
        assert recommendation == "no_significant_difference"

    def test_z_test(self, ab_manager: ABTestingManager) -> None:
        """Z 检验基本逻辑。"""
        # 大差异、大样本 → 应显著
        z, significant = ab_manager._z_test(
            p1=0.70, n1=1000,
            p2=0.80, n2=1000,
        )
        assert significant is True
        assert z > 0

        # 零样本 → 不显著
        z, significant = ab_manager._z_test(
            p1=0.0, n1=0,
            p2=0.0, n2=0,
        )
        assert significant is False
