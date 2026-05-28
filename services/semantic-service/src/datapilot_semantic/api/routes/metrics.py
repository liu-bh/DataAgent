"""指标 CRUD API 路由。

提供指标的创建、列表、更新和关联维度查询接口。
支持版本管理：创建时 version=1，更新时自动 version+1。
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from datapilot_common.exceptions import NotFoundError
from datapilot_semantic.api.dependencies import get_db
from datapilot_semantic.models import Dimension, Metric, MetricDimension
from datapilot_semantic.models.schemas import (
    DimensionResponse,
    MetricCreate,
    MetricResponse,
    MetricUpdate,
    PaginatedResponse,
    PaginationMeta,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/metrics", tags=["指标"])


# ---------------------------------------------------------------------------
# POST /api/v1/metrics — 创建指标（自动 version=1）
# ---------------------------------------------------------------------------


@router.post("", response_model=MetricResponse, status_code=201)
async def create_metric(
    body: MetricCreate,
    session: AsyncSession = Depends(get_db),
) -> MetricResponse:
    """创建指标。

    创建时自动设置 version=1 和 effective_time 为当前时间。

    Args:
        body: 创建请求体。
        session: 数据库会话。

    Returns:
        创建的指标。
    """
    metric = Metric(
        semantic_model_id=body.semantic_model_id,
        name=body.name,
        description=body.description,
        calculation=body.calculation,
        unit=body.unit,
        version=1,
        effective_time=datetime.now(UTC),
        parent_metric_id=body.parent_metric_id,
        tags=body.tags,
    )
    session.add(metric)
    await session.commit()
    await session.refresh(metric)
    return MetricResponse.model_validate(metric)


# ---------------------------------------------------------------------------
# GET /api/v1/metrics — 列表（支持 name 搜索, semantic_model_id 筛选）
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedResponse[MetricResponse])
async def list_metrics(
    session: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    name: str | None = Query(None, description="按指标名称模糊搜索"),
    semantic_model_id: str | None = Query(None, description="按语义模型 ID 筛选"),
) -> PaginatedResponse[MetricResponse]:
    """获取指标列表。

    支持按名称模糊搜索和语义模型 ID 精确筛选。

    Args:
        session: 数据库会话。
        page: 页码。
        page_size: 每页条数。
        name: 名称搜索关键字。
        semantic_model_id: 语义模型 ID 筛选。

    Returns:
        分页的指标列表。
    """
    # 构建 WHERE 条件
    where_clauses = [Metric.deleted_at.is_(None)]
    if name is not None:
        where_clauses.append(Metric.name.ilike(f"%{name}%"))
    if semantic_model_id is not None:
        where_clauses.append(Metric.semantic_model_id == semantic_model_id)

    # 查询总数
    count_stmt = select(func.count()).select_from(Metric).where(*where_clauses)
    total = (await session.execute(count_stmt)).scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    data_stmt = (
        select(Metric)
        .where(*where_clauses)
        .order_by(Metric.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await session.execute(data_stmt)).scalars().all()
    data = [MetricResponse.model_validate(m) for m in rows]

    return PaginatedResponse[MetricResponse](
        data=data,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if page_size > 0 else 0,
        ),
    )


# ---------------------------------------------------------------------------
# PUT /api/v1/metrics/{metric_id} — 更新（创建新版本 version+1）
# ---------------------------------------------------------------------------


@router.put("/{metric_id}", response_model=MetricResponse)
async def update_metric(
    metric_id: str,
    body: MetricUpdate,
    session: AsyncSession = Depends(get_db),
) -> MetricResponse:
    """更新指标。

    更新时自动创建新版本：version+1，effective_time 更新为当前时间。

    Args:
        metric_id: 指标 ID。
        body: 更新请求体。
        session: 数据库会话。

    Returns:
        更新后的指标（新版本）。
    """
    stmt = select(Metric).where(Metric.id == metric_id, Metric.deleted_at.is_(None))
    metric = (await session.execute(stmt)).scalar_one_or_none()

    if metric is None:
        raise NotFoundError(resource="指标", resource_id=metric_id)

    # 更新字段
    update_data = body.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(metric, field_name, value)

    # 自动递增版本号
    metric.version += 1
    metric.effective_time = datetime.now(UTC)

    session.add(metric)
    await session.commit()
    await session.refresh(metric)
    return MetricResponse.model_validate(metric)


# ---------------------------------------------------------------------------
# GET /api/v1/metrics/{metric_id}/dimensions — 指标关联的维度
# ---------------------------------------------------------------------------


@router.get("/{metric_id}/dimensions", response_model=list[DimensionResponse])
async def get_metric_dimensions(
    metric_id: str,
    session: AsyncSession = Depends(get_db),
) -> list[DimensionResponse]:
    """获取指标关联的维度列表。

    通过 metric_dimensions 关联表查询。

    Args:
        metric_id: 指标 ID。
        session: 数据库会话。

    Returns:
        关联的维度列表。
    """
    # 先验证指标存在
    metric_stmt = select(Metric).where(Metric.id == metric_id, Metric.deleted_at.is_(None))
    metric = (await session.execute(metric_stmt)).scalar_one_or_none()

    if metric is None:
        raise NotFoundError(resource="指标", resource_id=metric_id)

    # 通过关联表查询维度
    stmt = (
        select(Dimension)
        .join(MetricDimension, MetricDimension.dimension_id == Dimension.id)
        .where(MetricDimension.metric_id == metric_id)
        .order_by(Dimension.name)
    )
    dimensions = (await session.execute(stmt)).scalars().all()
    return [DimensionResponse.model_validate(d) for d in dimensions]
