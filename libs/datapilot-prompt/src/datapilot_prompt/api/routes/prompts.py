"""Prompt 管理 API 路由。

提供 Prompt 版本的 CRUD、激活切换和 A/B 测试结果查询接口。

端点:
    POST   /api/v1/prompts              — 创建 Prompt 版本
    GET    /api/v1/prompts              — 按场景查询版本列表
    GET    /api/v1/prompts/{scene}/active — 获取当前激活版本
    PUT    /api/v1/prompts/{id}/activate — 激活指定版本
    GET    /api/v1/prompts/{id}/ab-results — A/B 测试结果
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends, Query

from ...schemas import (
    ABTestResults,
    PromptActivateResponse,
    PromptCreate,
    PromptResponse,
)
from ...service import PromptManager

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/prompts", tags=["prompts"])


def _get_db_session() -> AsyncSession:
    """获取数据库 session 依赖。

    在实际部署中，session 由 FastAPI 依赖注入提供。
    此处为独立运行时的占位实现。
    """
    raise NotImplementedError(
        "请通过 FastAPI 依赖注入提供 AsyncSession。示例: Depends(get_db_session)"
    )


async def _get_prompt_manager(
    session: AsyncSession = Depends(_get_db_session),
) -> PromptManager:
    """构造 PromptManager 依赖。

    TODO: 接入 Redis 后注入 ABTestingManager。
    """
    return PromptManager(db_session=session)


# ------------------------------------------------------------------
# POST /api/v1/prompts — 创建 Prompt 版本
# ------------------------------------------------------------------


@router.post(
    "",
    response_model=PromptResponse,
    status_code=201,
    summary="创建 Prompt 版本",
    description="创建新的 Prompt 版本，系统自动递增版本号。场景内第一个版本自动激活。",
)
async def create_prompt(
    body: PromptCreate,
    manager: PromptManager = Depends(_get_prompt_manager),
) -> PromptResponse:
    """创建新 Prompt 版本。

    Args:
        body: 创建请求体。
        manager: PromptManager 实例（依赖注入）。

    Returns:
        创建的 Prompt 版本。
    """
    return await manager.create_prompt(
        scene=body.scene,
        content=body.content,
        ab_test_traffic=body.ab_test_traffic,
        version_description=body.version_description,
    )


# ------------------------------------------------------------------
# GET /api/v1/prompts — 按场景查询版本列表
# ------------------------------------------------------------------


@router.get(
    "",
    response_model=list[PromptResponse],
    summary="查询 Prompt 版本列表",
    description="按场景查询该场景下所有 Prompt 版本，按版本号倒序排列。",
)
async def list_prompts(
    scene: str = Query(..., description="场景标识: nl2sql/intent/explanation/correction"),
    manager: PromptManager = Depends(_get_prompt_manager),
) -> list[PromptResponse]:
    """按场景查询版本列表。

    Args:
        scene: 场景标识。
        manager: PromptManager 实例（依赖注入）。

    Returns:
        版本列表。
    """
    return await manager.list_prompts(scene=scene)


# ------------------------------------------------------------------
# GET /api/v1/prompts/{scene}/active — 获取当前激活版本
# ------------------------------------------------------------------


@router.get(
    "/{scene}/active",
    response_model=PromptResponse,
    summary="获取当前激活版本",
    description="获取指定场景的当前激活 Prompt 版本。",
)
async def get_active_prompt(
    scene: str,
    manager: PromptManager = Depends(_get_prompt_manager),
) -> PromptResponse:
    """获取当前激活版本。

    Args:
        scene: 场景标识。
        manager: PromptManager 实例（依赖注入）。

    Returns:
        激活的 Prompt 版本。
    """
    return await manager.get_active_prompt(scene=scene)


# ------------------------------------------------------------------
# PUT /api/v1/prompts/{id}/activate — 激活指定版本
# ------------------------------------------------------------------


@router.put(
    "/{prompt_id}/activate",
    response_model=PromptActivateResponse,
    summary="激活指定版本",
    description="激活指定的 Prompt 版本，同一场景同时只能有一个激活版本。",
)
async def activate_prompt(
    prompt_id: UUID,
    manager: PromptManager = Depends(_get_prompt_manager),
) -> PromptActivateResponse:
    """激活指定 Prompt 版本。

    Args:
        prompt_id: Prompt 版本 ID。
        manager: PromptManager 实例（依赖注入）。

    Returns:
        激活操作结果。
    """
    return await manager.activate_prompt(prompt_id=prompt_id)


# ------------------------------------------------------------------
# GET /api/v1/prompts/{id}/ab-results — A/B 测试结果
# ------------------------------------------------------------------


@router.get(
    "/{prompt_id}/ab-results",
    response_model=ABTestResults,
    summary="获取 A/B 测试结果",
    description="获取指定 Prompt 版本的 A/B 测试结果对比。",
)
async def get_ab_test_results(
    prompt_id: UUID,
    manager: PromptManager = Depends(_get_prompt_manager),
) -> ABTestResults:
    """获取 A/B 测试结果。

    根据指定 Prompt ID 查找其所属场景，返回该场景的 A/B 测试对比结果。

    Args:
        prompt_id: Prompt 版本 ID。
        manager: PromptManager 实例（依赖注入）。

    Returns:
        A/B 测试结果对比。

    Raises:
        404: Prompt 版本不存在。
        400: 该场景没有参与 A/B 测试的版本。
    """
    # 先查询 prompt 所属的 scene，再获取 A/B 测试结果
    prompt = await manager.get_prompt_by_id(prompt_id=prompt_id)
    return await manager.get_ab_test_results(scene=prompt.scene)
