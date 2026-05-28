"""Prompt 管理服务。

提供 Prompt 版本的 CRUD、激活切换和 A/B 测试结果查询。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from datapilot_common.exceptions import NotFoundError, ValidationError

from .ab_testing import ABTestingManager
from .models import PromptVersion, VALID_SCENES
from .schemas import (
    PromptResponse,
    PromptActivateResponse,
    ABTestResults,
    ABTestVersionMetrics,
)

logger = structlog.get_logger(__name__)


class PromptManager:
    """Prompt 版本管理器。

    负责 Prompt 的创建、查询、激活和 A/B 测试结果聚合。

    Args:
        db_session: SQLAlchemy 异步 session。
        ab_testing_manager: A/B 测试管理器实例。
    """

    def __init__(
        self,
        db_session: AsyncSession,
        ab_testing_manager: ABTestingManager | None = None,
    ) -> None:
        self._session = db_session
        self._ab_testing = ab_testing_manager

    # ------------------------------------------------------------------
    # 创建 Prompt 版本
    # ------------------------------------------------------------------

    async def create_prompt(
        self,
        scene: str,
        content: str,
        ab_test_traffic: float = 0.0,
        version_description: str | None = None,
    ) -> PromptResponse:
        """创建新 Prompt 版本。

        自动递增 version 号。如果该场景没有任何版本，
        则第一个版本自动激活。

        Args:
            scene: 场景标识。
            content: Prompt 模板内容。
            ab_test_traffic: A/B 测试流量比例，默认 0。
            version_description: 版本描述说明。

        Returns:
            创建的 Prompt 版本响应。

        Raises:
            ValidationError: scene 不合法或 ab_test_traffic 超出范围。
        """
        # 校验场景
        if scene not in VALID_SCENES:
            raise ValidationError(
                message=f"无效的场景标识: {scene}，有效值: {', '.join(VALID_SCENES)}",
                details={"field": "scene", "value": scene},
            )

        # 校验流量比例
        if not 0.0 <= ab_test_traffic <= 1.0:
            raise ValidationError(
                message=f"ab_test_traffic 必须在 0.00 ~ 1.00 之间，当前值: {ab_test_traffic}",
                details={"field": "ab_test_traffic", "value": ab_test_traffic},
            )

        # 查询当前最大版本号
        max_version_result = await self._session.execute(
            select(func.coalesce(func.max(PromptVersion.version), 0)).where(
                PromptVersion.scene == scene
            )
        )
        next_version = max_version_result.scalar_one() + 1

        # 检查是否为该场景第一个版本
        count_result = await self._session.execute(
            select(func.count(PromptVersion.id)).where(PromptVersion.scene == scene)
        )
        is_first_version = count_result.scalar_one() == 0

        prompt = PromptVersion(
            id=str(uuid.uuid4()),
            scene=scene,
            version=next_version,
            content=content,
            is_active=is_first_version,
            ab_test_traffic=ab_test_traffic,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._session.add(prompt)
        await self._session.flush()
        await self._session.refresh(prompt)

        logger.info(
            "创建 Prompt 版本",
            scene=scene,
            version=next_version,
            is_active=is_first_version,
        )

        return self._to_response(prompt)

    # ------------------------------------------------------------------
    # 获取激活版本
    # ------------------------------------------------------------------

    async def get_active_prompt(self, scene: str) -> PromptResponse:
        """获取指定场景的当前激活版本。

        Args:
            scene: 场景标识。

        Returns:
            激活的 Prompt 版本响应。

        Raises:
            NotFoundError: 该场景没有激活版本。
        """
        result = await self._session.execute(
            select(PromptVersion).where(
                PromptVersion.scene == scene,
                PromptVersion.is_active.is_(True),
            )
        )
        prompt = result.scalar_one_or_none()

        if prompt is None:
            raise NotFoundError(
                resource=f"Prompt({scene})",
                details={"scene": scene, "reason": "该场景没有激活版本"},
            )

        return self._to_response(prompt)

    # ------------------------------------------------------------------
    # 激活指定版本
    # ------------------------------------------------------------------

    async def activate_prompt(self, prompt_id: UUID) -> PromptActivateResponse:
        """激活指定 Prompt 版本。

        同一场景同时只能有一个激活版本。
        激活新版本时自动取消该场景原激活版本。

        Args:
            prompt_id: 要激活的 Prompt 版本 ID。

        Returns:
            激活操作响应。

        Raises:
            NotFoundError: 指定 ID 不存在。
        """
        # 查询目标版本
        result = await self._session.execute(
            select(PromptVersion).where(PromptVersion.id == str(prompt_id))
        )
        prompt = result.scalar_one_or_none()

        if prompt is None:
            raise NotFoundError(
                resource="Prompt",
                resource_id=str(prompt_id),
            )

        # 取消该场景所有激活状态
        await self._session.execute(
            select(PromptVersion).where(
                PromptVersion.scene == prompt.scene,
                PromptVersion.is_active.is_(True),
                PromptVersion.id != str(prompt_id),
            )
        )
        deactivate_result = await self._session.execute(
            select(PromptVersion).where(
                PromptVersion.scene == prompt.scene,
                PromptVersion.is_active.is_(True),
            )
        )
        active_prompts = deactivate_result.scalars().all()
        for active_prompt in active_prompts:
            active_prompt.is_active = False

        # 激活目标版本
        prompt.is_active = True
        await self._session.flush()

        logger.info(
            "激活 Prompt 版本",
            prompt_id=str(prompt_id),
            scene=prompt.scene,
            version=prompt.version,
            deactivated_count=len(active_prompts),
        )

        return PromptActivateResponse(
            prompt_id=prompt.id,  # type: ignore[arg-type]
            scene=prompt.scene,
            version=prompt.version,
            message=f"已激活 {prompt.scene} 场景的版本 {prompt.version}",
        )

    # ------------------------------------------------------------------
    # 列出场景版本
    # ------------------------------------------------------------------

    async def list_prompts(self, scene: str) -> list[PromptResponse]:
        """列出指定场景的所有 Prompt 版本。

        Args:
            scene: 场景标识。

        Returns:
            版本列表，按版本号倒序排列。
        """
        result = await self._session.execute(
            select(PromptVersion)
            .where(PromptVersion.scene == scene)
            .order_by(PromptVersion.version.desc())
        )
        prompts = result.scalars().all()
        return [self._to_response(p) for p in prompts]

    # ------------------------------------------------------------------
    # A/B 测试结果
    # ------------------------------------------------------------------

    async def get_ab_test_results(self, scene: str) -> ABTestResults:
        """获取指定场景的 A/B 测试结果。

        对比激活版本和参与 A/B 测试的版本，给出推荐结论。

        Args:
            scene: 场景标识。

        Returns:
            A/B 测试结果对比。

        Raises:
            NotFoundError: 该场景没有激活版本。
            ValidationError: 该场景没有参与 A/B 测试的版本。
        """
        if self._ab_testing is None:
            raise ValidationError(
                message="A/B 测试管理器未初始化，无法获取测试结果",
            )

        # 获取激活版本
        active_prompt = await self._get_active_model(scene)

        # 获取参与 A/B 测试的版本
        result = await self._session.execute(
            select(PromptVersion).where(
                PromptVersion.scene == scene,
                PromptVersion.ab_test_traffic > 0,
                PromptVersion.is_active.is_(False),
            )
        )
        ab_prompt = result.scalar_one_or_none()

        if ab_prompt is None:
            raise ValidationError(
                message=f"场景 {scene} 没有参与 A/B 测试的版本",
                details={"scene": scene},
            )

        # 获取统计数据
        stats_active = await self._ab_testing.get_statistics(
            UUID(str(active_prompt.id))
        )
        stats_ab = await self._ab_testing.get_statistics(
            UUID(str(ab_prompt.id))
        )

        # 对比
        recommendation, confidence = self._ab_testing.compare_versions(
            stats_a=stats_active,
            stats_b=stats_ab,
            traffic_a=1.0 - float(ab_prompt.ab_test_traffic),
            traffic_b=float(ab_prompt.ab_test_traffic),
        )

        version_a_metrics = ABTestVersionMetrics(
            prompt_id=UUID(str(active_prompt.id)),
            traffic=1.0 - float(ab_prompt.ab_test_traffic),
            execution_accuracy=stats_active.success_rate,
            avg_latency_ms=stats_active.avg_latency_ms,
            user_edit_rate=stats_active.user_edit_rate,
            satisfaction_rate=stats_active.satisfaction_rate,
            sample_count=stats_active.total_requests,
        )
        version_b_metrics = ABTestVersionMetrics(
            prompt_id=UUID(str(ab_prompt.id)),
            traffic=float(ab_prompt.ab_test_traffic),
            execution_accuracy=stats_ab.success_rate,
            avg_latency_ms=stats_ab.avg_latency_ms,
            user_edit_rate=stats_ab.user_edit_rate,
            satisfaction_rate=stats_ab.satisfaction_rate,
            sample_count=stats_ab.total_requests,
        )

        return ABTestResults(
            version_a=version_a_metrics,
            version_b=version_b_metrics,
            recommendation=recommendation,  # type: ignore[arg-type]
            confidence=confidence,
        )

    # ------------------------------------------------------------------
    # A/B 测试分流
    # ------------------------------------------------------------------

    async def _select_by_ab_test(self, scene: str) -> PromptResponse:
        """根据 A/B 测试配置随机选择版本。

        如果没有参与 A/B 测试的版本，直接返回激活版本。

        Args:
            scene: 场景标识。

        Returns:
            选中的 Prompt 版本响应。
        """
        active_prompt = await self._get_active_model(scene)

        if self._ab_testing is None:
            return self._to_response(active_prompt)

        # 查询参与 A/B 测试的版本
        result = await self._session.execute(
            select(PromptVersion).where(
                PromptVersion.scene == scene,
                PromptVersion.ab_test_traffic > 0,
                PromptVersion.is_active.is_(False),
            )
        )
        ab_prompts = result.scalars().all()

        if not ab_prompts:
            return self._to_response(active_prompt)

        # 构建流量分配
        ab_versions: dict[UUID, float] = {}
        for p in ab_prompts:
            ab_versions[UUID(str(p.id))] = float(p.ab_test_traffic)

        # 随机选择
        selected_id = await self._ab_testing.assign_version(
            active_prompt_id=UUID(str(active_prompt.id)),
            ab_versions=ab_versions,
        )

        # 返回选中版本
        if selected_id == UUID(str(active_prompt.id)):
            return self._to_response(active_prompt)

        for p in ab_prompts:
            if UUID(str(p.id)) == selected_id:
                return self._to_response(p)

        return self._to_response(active_prompt)

    # ------------------------------------------------------------------
    # 根据 ID 查询
    # ------------------------------------------------------------------

    async def get_prompt_by_id(self, prompt_id: UUID) -> PromptResponse:
        """根据 ID 获取 Prompt 版本。

        Args:
            prompt_id: Prompt 版本 ID。

        Returns:
            Prompt 版本响应。

        Raises:
            NotFoundError: 指定 ID 不存在。
        """
        result = await self._session.execute(
            select(PromptVersion).where(PromptVersion.id == str(prompt_id))
        )
        prompt = result.scalar_one_or_none()
        if prompt is None:
            raise NotFoundError(
                resource="Prompt",
                resource_id=str(prompt_id),
            )
        return self._to_response(prompt)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _get_active_model(self, scene: str) -> PromptVersion:
        """获取激活版本的 ORM 对象。

        Args:
            scene: 场景标识。

        Returns:
            PromptVersion ORM 对象。

        Raises:
            NotFoundError: 该场景没有激活版本。
        """
        result = await self._session.execute(
            select(PromptVersion).where(
                PromptVersion.scene == scene,
                PromptVersion.is_active.is_(True),
            )
        )
        prompt = result.scalar_one_or_none()
        if prompt is None:
            raise NotFoundError(
                resource=f"Prompt({scene})",
                details={"scene": scene, "reason": "该场景没有激活版本"},
            )
        return prompt

    @staticmethod
    def _to_response(prompt: PromptVersion) -> PromptResponse:
        """将 ORM 模型转为响应 Schema。"""
        return PromptResponse(
            id=UUID(str(prompt.id)),
            scene=prompt.scene,
            version=prompt.version,
            content=prompt.content,
            is_active=prompt.is_active,
            effectiveness_score=prompt.effectiveness_score,
            ab_test_traffic=prompt.ab_test_traffic,  # type: ignore[arg-type]
            created_at=prompt.created_at,  # type: ignore[arg-type]
        )
