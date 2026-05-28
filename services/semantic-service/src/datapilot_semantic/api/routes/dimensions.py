"""维度 CRUD API 路由。

提供维度的创建、列表和更新接口。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from datapilot_common.exceptions import NotFoundError
from datapilot_semantic.api.dependencies import get_db
from datapilot_semantic.models import Dimension
from datapilot_semantic.models.schemas import (
    DimensionCreate,
    DimensionResponse,
    DimensionUpdate,
    PaginatedResponse,
    PaginationMeta,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/dimensions", tags=["维度"])


# ---------------------------------------------------------------------------
# POST /api/v1/dimensions — 创建维度
# ---------------------------------------------------------------------------


@router.post("", response_model=DimensionResponse, status_code=201)
async def create_dimension(
    body: DimensionCreate,
    session: AsyncSession = Depends(get_db),
) -> DimensionResponse:
    """创建维度。

    Args:
        body: 创建请求体。
        session: 数据库会话。

    Returns:
        创建的维度。
    """
    dimension = Dimension(
        semantic_model_id=body.semantic_model_id,
        name=body.name,
        column_name=body.column_name,
        table_id=body.table_id,
        synonyms=body.synonyms,
        hierarchy=body.hierarchy,
        is_virtual=body.is_virtual,
        virtual_expression=body.virtual_expression,
    )
    session.add(dimension)
    await session.commit()
    await session.refresh(dimension)
    return DimensionResponse.model_validate(dimension)


# ---------------------------------------------------------------------------
# GET /api/v1/dimensions — 列表（支持 semantic_model_id 筛选）
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedResponse[DimensionResponse])
async def list_dimensions(
    session: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    semantic_model_id: str | None = Query(None, description="按语义模型 ID 筛选"),
) -> PaginatedResponse[DimensionResponse]:
    """获取维度列表。

    支持按语义模型 ID 筛选。

    Args:
        session: 数据库会话。
        page: 页码。
        page_size: 每页条数。
        semantic_model_id: 语义模型 ID 筛选。

    Returns:
        分页的维度列表。
    """
    # 构建 WHERE 条件
    where_clauses = [Dimension.deleted_at.is_(None)]
    if semantic_model_id is not None:
        where_clauses.append(Dimension.semantic_model_id == semantic_model_id)

    # 查询总数
    count_stmt = select(func.count()).select_from(Dimension).where(*where_clauses)
    total = (await session.execute(count_stmt)).scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    data_stmt = (
        select(Dimension)
        .where(*where_clauses)
        .order_by(Dimension.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await session.execute(data_stmt)).scalars().all()
    data = [DimensionResponse.model_validate(d) for d in rows]

    return PaginatedResponse[DimensionResponse](
        data=data,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if page_size > 0 else 0,
        ),
    )


# ---------------------------------------------------------------------------
# PUT /api/v1/dimensions/{dimension_id} — 更新
# ---------------------------------------------------------------------------


@router.put("/{dimension_id}", response_model=DimensionResponse)
async def update_dimension(
    dimension_id: str,
    body: DimensionUpdate,
    session: AsyncSession = Depends(get_db),
) -> DimensionResponse:
    """更新维度。

    仅更新请求体中非 None 的字段。

    Args:
        dimension_id: 维度 ID。
        body: 更新请求体。
        session: 数据库会话。

    Returns:
        更新后的维度。
    """
    stmt = select(Dimension).where(Dimension.id == dimension_id, Dimension.deleted_at.is_(None))
    dimension = (await session.execute(stmt)).scalar_one_or_none()

    if dimension is None:
        raise NotFoundError(resource="维度", resource_id=dimension_id)

    # 仅更新非 None 的字段
    update_data = body.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(dimension, field_name, value)

    session.add(dimension)
    await session.commit()
    await session.refresh(dimension)
    return DimensionResponse.model_validate(dimension)
