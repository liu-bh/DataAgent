"""语义模型管理服务。

将原本分散在 api/routes/semantic_models.py 中的业务逻辑抽取到 Service 层，
实现 Controller-Service 分层。Service 层不直接处理 HTTP 请求/响应，
通过抛出自定义异常（AppError、NotFoundError、ValidationError）与路由层交互。
"""

from __future__ import annotations

import math
from datetime import UTC
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from datapilot_common.exceptions import NotFoundError
from datapilot_semantic.models.schemas import (
    DimensionResponse,
    MetricResponse,
    PaginatedResponse,
    PaginationMeta,
    SemanticModelCreate,
    SemanticModelResponse,
    SemanticModelUpdate,
)
from datapilot_semantic.models.semantic_model import SemanticModel

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class SemanticModelService:
    """语义模型管理服务。

    封装语义模型 CRUD 业务逻辑，包括关联指标和维度的查询。
    由于没有真实的数据库连接，Service 方法使用 mock 实现。

    Args:
        session_factory: 可选的数据库会话工厂，用于创建会话。
    """

    def __init__(self, session_factory: Callable[[], AsyncSession] | None = None) -> None:
        """初始化 SemanticModelService。

        Args:
            session_factory: 可选的数据库会话工厂函数。
        """
        self._session_factory = session_factory

    async def create_model(
        self,
        data: SemanticModelCreate,
        db: AsyncSession,
    ) -> SemanticModelResponse:
        """创建语义模型。

        Args:
            data: 创建请求体。
            db: 数据库会话。

        Returns:
            创建的语义模型响应。
        """
        model = SemanticModel(
            name=data.name,
            description=data.description,
            domain=data.domain,
            data_source_ids=data.data_source_ids,
        )
        db.add(model)
        await db.commit()
        await db.refresh(model)

        logger.info(
            "语义模型创建成功",
            model_id=str(model.id),
            name=data.name,
            domain=data.domain,
        )
        return SemanticModelResponse.model_validate(model)

    async def get_model(
        self,
        model_id: str,
        db: AsyncSession,
    ) -> SemanticModelResponse:
        """获取语义模型详情。

        包含关联的指标和维度列表。

        Args:
            model_id: 语义模型 ID。
            db: 数据库会话。

        Returns:
            语义模型详情响应。

        Raises:
            NotFoundError: 语义模型不存在。
        """
        stmt = (
            select(SemanticModel)
            .options(
                selectinload(SemanticModel.metrics),
                selectinload(SemanticModel.dimensions),
            )
            .where(SemanticModel.id == model_id, SemanticModel.deleted_at.is_(None))
        )
        model = (await db.execute(stmt)).scalar_one_or_none()

        if model is None:
            raise NotFoundError(resource="语义模型", resource_id=model_id)

        response = SemanticModelResponse.model_validate(model)
        # 填充关联的指标和维度
        response.metrics = [MetricResponse.model_validate(m) for m in model.metrics]
        response.dimensions = [DimensionResponse.model_validate(d) for d in model.dimensions]
        return response

    async def list_models(
        self,
        db: AsyncSession,
        *,
        domain: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[SemanticModelResponse]:
        """获取语义模型列表。

        支持按 domain 筛选和分页。

        Args:
            db: 数据库会话。
            domain: 业务域筛选（电商/运营/财务/通用）。
            page: 页码，从 1 开始。
            page_size: 每页条数。

        Returns:
            分页的语义模型列表响应。
        """
        allowed_domains = ("电商", "运营", "财务", "通用")

        # 构建 WHERE 条件
        where_clauses = [SemanticModel.deleted_at.is_(None)]
        if domain is not None:
            if domain not in allowed_domains:
                from datapilot_common.exceptions import ValidationError

                raise ValidationError(
                    message=f"domain 必须为 {allowed_domains} 之一，收到: {domain}",
                )
            where_clauses.append(SemanticModel.domain == domain)

        # 查询总数
        count_stmt = select(func.count()).select_from(SemanticModel).where(*where_clauses)
        total = (await db.execute(count_stmt)).scalar() or 0

        # 分页查询
        offset = (page - 1) * page_size
        data_stmt = (
            select(SemanticModel)
            .where(*where_clauses)
            .order_by(SemanticModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await db.execute(data_stmt)).scalars().all()
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

    async def update_model(
        self,
        model_id: str,
        data: SemanticModelUpdate,
        db: AsyncSession,
    ) -> SemanticModelResponse:
        """更新语义模型。

        仅更新请求体中非 None 的字段。

        Args:
            model_id: 语义模型 ID。
            data: 更新请求体。
            db: 数据库会话。

        Returns:
            更新后的语义模型响应。

        Raises:
            NotFoundError: 语义模型不存在。
        """
        stmt = select(SemanticModel).where(
            SemanticModel.id == model_id, SemanticModel.deleted_at.is_(None)
        )
        model = (await db.execute(stmt)).scalar_one_or_none()

        if model is None:
            raise NotFoundError(resource="语义模型", resource_id=model_id)

        # 仅更新非 None 的字段
        update_data = data.model_dump(exclude_unset=True)
        for field_name, value in update_data.items():
            setattr(model, field_name, value)

        db.add(model)
        await db.commit()
        await db.refresh(model)

        logger.info("语义模型更新成功", model_id=model_id)
        return SemanticModelResponse.model_validate(model)

    async def delete_model(
        self,
        model_id: str,
        db: AsyncSession,
    ) -> None:
        """删除语义模型（软删除）。

        将 deleted_at 设置为当前时间。

        Args:
            model_id: 语义模型 ID。
            db: 数据库会话。

        Raises:
            NotFoundError: 语义模型不存在。
        """
        from datetime import datetime

        stmt = select(SemanticModel).where(
            SemanticModel.id == model_id, SemanticModel.deleted_at.is_(None)
        )
        model = (await db.execute(stmt)).scalar_one_or_none()

        if model is None:
            raise NotFoundError(resource="语义模型", resource_id=model_id)

        model.deleted_at = datetime.now(UTC)
        db.add(model)
        await db.commit()

        logger.info("语义模型软删除成功", model_id=model_id)
