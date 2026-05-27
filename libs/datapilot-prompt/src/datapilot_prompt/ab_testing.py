"""A/B 测试管理器。

使用 Redis 存储实时统计数据，支持流量分配、效果记录和统计查询。
每个场景同一时间只能有两个版本参与 A/B 测试（激活版本 + 实验版本）。
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)


@dataclass
class PromptStatistics:
    """单版本统计数据。

    Attributes:
        prompt_id: Prompt 版本 ID。
        total_requests: 总请求数。
        success_count: 成功次数。
        fail_count: 失败次数。
        total_latency_ms: 总延迟（毫秒）。
        user_edit_count: 用户编辑次数。
        user_satisfied_count: 用户满意次数。
        user_dissatisfied_count: 用户不满意次数。
    """

    prompt_id: UUID
    total_requests: int = 0
    success_count: int = 0
    fail_count: int = 0
    total_latency_ms: float = 0.0
    user_edit_count: int = 0
    user_satisfied_count: int = 0
    user_dissatisfied_count: int = 0

    @property
    def success_rate(self) -> float:
        """计算成功率。"""
        if self.total_requests == 0:
            return 0.0
        return self.success_count / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        """计算平均延迟。"""
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests

    @property
    def user_edit_rate(self) -> float:
        """计算用户编辑率。"""
        if self.total_requests == 0:
            return 0.0
        return self.user_edit_count / self.total_requests

    @property
    def satisfaction_rate(self) -> float:
        """计算用户满意度。"""
        total_feedback = self.user_satisfied_count + self.user_dissatisfied_count
        if total_feedback == 0:
            return 0.0
        return self.user_satisfied_count / total_feedback


class ABTestingManager:
    """A/B 测试管理器。

    通过 Redis 实时记录和查询各版本的统计数据。
    Redis Key 设计:
        ab:stats:{prompt_id}:total_requests   — 总请求数
        ab:stats:{prompt_id}:success_count   — 成功次数
        ab:stats:{prompt_id}:fail_count       — 失败次数
        ab:stats:{prompt_id}:total_latency_ms — 总延迟
        ab:stats:{prompt_id}:user_edit_count  — 用户编辑次数
        ab:stats:{prompt_id}:satisfied_count  — 满意次数
        ab:stats:{prompt_id}:dissatisfied_count — 不满意次数

    Args:
        redis: Redis 异步客户端实例。
    """

    # 最少样本数阈值，低于此数不给出推荐
    MIN_SAMPLE_SIZE: int = 1000
    # 置信度阈值 (p < 0.05)
    CONFIDENCE_THRESHOLD: float = 0.95
    # 最小显著差异（效果提升 < 2% 可视为无显著差异）
    MIN_SIGNIFICANT_DIFF: float = 0.02

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def _stats_key(self, prompt_id: UUID, metric: str) -> str:
        """构造 Redis 统计 key。"""
        return f"ab:stats:{prompt_id}:{metric}"

    # ------------------------------------------------------------------
    # 流量分配
    # ------------------------------------------------------------------

    async def traffic_distribution(self, scene: str) -> dict[str, float]:
        """获取指定场景的流量分配比例。

        从数据库查询参与 A/B 测试的版本及其流量比例。
        由于本类不直接依赖 DB session，此方法供上层 Service 调用后
        将结果传入 assign_version。

        Returns:
            字典 {prompt_id_str: traffic_ratio}，如 {"uuid1": 0.8, "uuid2": 0.2}。
        """
        # 此方法由 PromptManager 调用时传入预查询的版本列表
        # 在 ABTestingManager 内部不做 DB 查询
        logger.warning(
            "traffic_distribution 应由 PromptManager 调用并提供版本数据",
            scene=scene,
        )
        return {}

    async def assign_version(
        self,
        active_prompt_id: UUID,
        ab_versions: dict[UUID, float],
    ) -> UUID:
        """根据流量比例随机分配版本。

        Args:
            active_prompt_id: 当前激活版本 ID。
            ab_versions: 参与测试的版本及其流量比例 {prompt_id: traffic}。
                所有比例之和不应超过 1.0，剩余流量分配给 active_prompt_id。

        Returns:
            被选中的 prompt_id。
        """
        total_ab_traffic = sum(ab_versions.values())

        if total_ab_traffic <= 0:
            # 没有 A/B 测试版本，直接返回 active 版本
            return active_prompt_id

        rand = random.random()

        # active 版本获得剩余流量
        active_traffic = 1.0 - total_ab_traffic

        # 先判断是否命中 active 版本
        if rand < active_traffic:
            return active_prompt_id

        # 在 A/B 测试版本中随机选择
        remaining = rand - active_traffic
        cumulative = 0.0
        for prompt_id, traffic in ab_versions.items():
            cumulative += traffic
            if remaining <= cumulative:
                logger.debug(
                    "A/B 测试分流",
                    prompt_id=str(prompt_id),
                    traffic=traffic,
                )
                return prompt_id

        # 兜底返回最后一个测试版本
        return list(ab_versions.keys())[-1]

    # ------------------------------------------------------------------
    # 效果记录
    # ------------------------------------------------------------------

    async def record_outcome(
        self,
        prompt_id: UUID,
        success: bool,
        latency_ms: float = 0.0,
    ) -> None:
        """记录单次请求的效果数据。

        Args:
            prompt_id: Prompt 版本 ID。
            success: 是否成功（SQL 执行成功、用户认可等）。
            latency_ms: 请求延迟（毫秒）。
        """
        pipe = self._redis.pipeline()
        pid_str = str(prompt_id)

        pipe.incr(self._stats_key(prompt_id, "total_requests"))
        if success:
            pipe.incr(self._stats_key(prompt_id, "success_count"))
        else:
            pipe.incr(self._stats_key(prompt_id, "fail_count"))
        pipe.incrbyfloat(self._stats_key(prompt_id, "total_latency_ms"), latency_ms)

        await pipe.execute()

        logger.debug(
            "A/B 测试效果记录",
            prompt_id=pid_str,
            success=success,
            latency_ms=latency_ms,
        )

    async def record_user_feedback(
        self,
        prompt_id: UUID,
        edited: bool = False,
        satisfied: bool | None = None,
    ) -> None:
        """记录用户反馈数据。

        Args:
            prompt_id: Prompt 版本 ID。
            edited: 用户是否编辑了生成的 SQL。
            satisfied: 用户是否满意（None 表示未反馈）。
        """
        pipe = self._redis.pipeline()

        if edited:
            pipe.incr(self._stats_key(prompt_id, "user_edit_count"))

        if satisfied is True:
            pipe.incr(self._stats_key(prompt_id, "satisfied_count"))
        elif satisfied is False:
            pipe.incr(self._stats_key(prompt_id, "dissatisfied_count"))

        await pipe.execute()

    # ------------------------------------------------------------------
    # 统计查询
    # ------------------------------------------------------------------

    async def get_statistics(self, prompt_id: UUID) -> PromptStatistics:
        """获取指定版本的统计数据。

        Args:
            prompt_id: Prompt 版本 ID。

        Returns:
            PromptStatistics 统计结果。
        """
        keys = [
            self._stats_key(prompt_id, "total_requests"),
            self._stats_key(prompt_id, "success_count"),
            self._stats_key(prompt_id, "fail_count"),
            self._stats_key(prompt_id, "total_latency_ms"),
            self._stats_key(prompt_id, "user_edit_count"),
            self._stats_key(prompt_id, "satisfied_count"),
            self._stats_key(prompt_id, "dissatisfied_count"),
        ]
        values = await self._redis.mget(keys)

        # mget 返回 None 表示 key 不存在，转为 0
        def _to_int(val: Any) -> int:
            return int(val) if val is not None else 0

        def _to_float(val: Any) -> float:
            return float(val) if val is not None else 0.0

        return PromptStatistics(
            prompt_id=prompt_id,
            total_requests=_to_int(values[0]),
            success_count=_to_int(values[1]),
            fail_count=_to_int(values[2]),
            total_latency_ms=_to_float(values[3]),
            user_edit_count=_to_int(values[4]),
            user_satisfied_count=_to_int(values[5]),
            user_dissatisfied_count=_to_int(values[6]),
        )

    # ------------------------------------------------------------------
    # 显著性检验
    # ------------------------------------------------------------------

    def _z_test(
        self,
        p1: float,
        n1: int,
        p2: float,
        n2: int,
    ) -> tuple[float, bool]:
        """双比例 Z 检验，判断两个成功率是否存在显著差异。

        Args:
            p1: 版本 A 成功率。
            n1: 版本 A 样本数。
            p2: 版本 B 成功率。
            n2: 版本 B 样本数。

        Returns:
            (z_statistic, is_significant)：Z 统计量和是否显著（p < 0.05）。
        """
        if n1 == 0 or n2 == 0:
            return 0.0, False

        # 合并成功率
        p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
        if p_pool == 0 or p_pool == 1:
            return 0.0, False

        se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
        if se == 0:
            return 0.0, False

        z = (p2 - p1) / se
        # |z| > 1.96 对应 p < 0.05（双尾检验）
        is_significant = abs(z) > 1.96

        return z, is_significant

    def compare_versions(
        self,
        stats_a: PromptStatistics,
        stats_b: PromptStatistics,
        traffic_a: float,
        traffic_b: float,
    ) -> tuple[str, float]:
        """对比两个版本，给出推荐结论。

        Args:
            stats_a: 版本 A 统计数据。
            stats_b: 版本 B 统计数据。
            traffic_a: 版本 A 流量比例。
            traffic_b: 版本 B 流量比例。

        Returns:
            (recommendation, confidence)：
                recommendation: "version_a" / "version_b" / "no_significant_difference"
                confidence: 置信度 0~1。
        """
        # 样本数不足，无法得出结论
        if (
            stats_a.total_requests < self.MIN_SAMPLE_SIZE
            or stats_b.total_requests < self.MIN_SAMPLE_SIZE
        ):
            return "no_significant_difference", 0.0

        # Z 检验
        z_stat, is_significant = self._z_test(
            stats_a.success_rate,
            stats_a.total_requests,
            stats_b.success_rate,
            stats_b.total_requests,
        )

        if not is_significant:
            return "no_significant_difference", 0.0

        # 计算置信度（简化：基于 Z 值映射）
        confidence = min(1.0, 0.5 + abs(z_stat) / 10.0)

        # 判断效果提升是否超过最小显著差异
        rate_diff = stats_b.success_rate - stats_a.success_rate
        if abs(rate_diff) < self.MIN_SIGNIFICANT_DIFF:
            return "no_significant_difference", confidence

        # 推荐效果更好的版本
        if stats_b.success_rate > stats_a.success_rate:
            return "version_b", confidence
        else:
            return "version_a", confidence
