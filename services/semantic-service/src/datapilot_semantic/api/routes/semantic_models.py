"""语义模型 CRUD API 路由。

提供语义模型的创建、列表、详情和更新接口。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from datapilot_common.exceptions import NotFoundError, ValidationError
from datapilot_semantic.api.dependencies import get_db
from datapilot_semantic.models import SemanticModel
from datapilot_semantic.models.schemas import (
    DimensionResponse,
    MetricResponse,
    PaginatedResponse,
    PaginationMeta,
    SemanticModelCreate,
    SemanticModelResponse,
    SemanticModelUpdate,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/semantic-models", tags=["语义模型"])


# ---------------------------------------------------------------------------
# POST /api/v1/semantic-models — 创建语义模型
# ---------------------------------------------------------------------------


@router.post("", response_model=SemanticModelResponse, status_code=201)
async def create_semantic_model(
    body: SemanticModelCreate,
    session: AsyncSession = Depends(get_db),
) -> SemanticModelResponse:
    """创建语义模型。

    Args:
        body: 创建请求体。
        session: 数据库会话。

    Returns:
        创建的语义模型。
    """
    model = SemanticModel(
        name=body.name,
        description=body.description,
        domain=body.domain,
        data_source_ids=body.data_source_ids,
    )
    session.add(model)
    await session.commit()
    await session.refresh(model)
    return SemanticModelResponse.model_validate(model)


# ---------------------------------------------------------------------------
# GET /api/v1/semantic-models — 列表（分页，支持 domain 筛选）
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedResponse[SemanticModelResponse])
async def list_semantic_models(
    session: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    domain: str | None = Query(None, description="按业务域筛选"),
) -> PaginatedResponse[SemanticModelResponse]:
    """获取语义模型列表。

    支持按 domain 筛选和分页。

    Args:
        session: 数据库会话。
        page: 页码。
        page_size: 每页条数。
        domain: 业务域筛选。

    Returns:
        分页的语义模型列表。
    """
    allowed_domains = ("电商", "运营", "财务", "通用")

    # 构建 WHERE 条件
    where_clauses = [SemanticModel.deleted_at.is_(None)]
    if domain is not None:
        if domain not in allowed_domains:
            raise ValidationError(
                message=f"domain 必须为 {allowed_domains} 之一，收到: {domain}",
            )
        where_clauses.append(SemanticModel.domain == domain)

    # 查询总数
    count_stmt = select(func.count()).select_from(SemanticModel).where(*where_clauses)
    total = (await session.execute(count_stmt)).scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    data_stmt = (
        select(SemanticModel)
        .where(*where_clauses)
        .order_by(SemanticModel.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await session.execute(data_stmt)).scalars().all()
    data = [SemanticModelResponse.model_validate(m) for m in rows]

    return PaginatedResponse[SemanticModelResponse](
        data=data,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if page_size > 0 else 0,
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/semantic-models/{model_id} — 详情（含关联的 metrics 和 dimensions）
# ---------------------------------------------------------------------------


@router.get("/{model_id}", response_model=SemanticModelResponse)
async def get_semantic_model(
    model_id: str,
    session: AsyncSession = Depends(get_db),
) -> SemanticModelResponse:
    """获取语义模型详情。

    包含关联的指标和维度列表。

    Args:
        model_id: 语义模型 ID。
        session: 数据库会话。

    Returns:
        语义模型详情。
    """
    stmt = (
        select(SemanticModel)
        .options(
            selectinload(SemanticModel.metrics),
            selectinload(SemanticModel.dimensions),
        )
        .where(SemanticModel.id == model_id, SemanticModel.deleted_at.is_(None))
    )
    model = (await session.execute(stmt)).scalar_one_or_none()

    if model is None:
        raise NotFoundError(resource="语义模型", resource_id=model_id)

    response = SemanticModelResponse.model_validate(model)
    # 填充关联的指标和维度
    response.metrics = [MetricResponse.model_validate(m) for m in model.metrics]
    response.dimensions = [DimensionResponse.model_validate(d) for d in model.dimensions]
    return response


# ---------------------------------------------------------------------------
# PUT /api/v1/semantic-models/{model_id} — 更新
# ---------------------------------------------------------------------------


@router.put("/{model_id}", response_model=SemanticModelResponse)
async def update_semantic_model(
    model_id: str,
    body: SemanticModelUpdate,
    session: AsyncSession = Depends(get_db),
) -> SemanticModelResponse:
    """更新语义模型。

    仅更新请求体中非 None 的字段。

    Args:
        model_id: 语义模型 ID。
        body: 更新请求体。
        session: 数据库会话。

    Returns:
        更新后的语义模型。
    """
    stmt = select(SemanticModel).where(
        SemanticModel.id == model_id, SemanticModel.deleted_at.is_(None)
    )
    model = (await session.execute(stmt)).scalar_one_or_none()

    if model is None:
        raise NotFoundError(resource="语义模型", resource_id=model_id)

    # 仅更新非 None 的字段
    update_data = body.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(model, field_name, value)

    session.add(model)
    await session.commit()
    await session.refresh(model)
    return SemanticModelResponse.model_validate(model)
