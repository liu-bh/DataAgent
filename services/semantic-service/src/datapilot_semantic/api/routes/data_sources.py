"""数据源管理 API 路由。

提供数据源 CRUD、健康检查、元数据同步等端点。
路由前缀: /api/v1/data-sources
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from datapilot_common.exceptions import NotFoundError, ValidationError
from datapilot_semantic.api.dependencies import get_db
from datapilot_semantic.metadata.datasource_pool import (
    encrypt_password,
    test_connection,
)
from datapilot_semantic.metadata.models import DataSource, DataSourceHealth, SourceTable
from datapilot_semantic.metadata.schemas import (
    DataConnectionConfig,
    DataSourceCreate,
    DataSourceHealthResponse,
    DataSourceResponse,
    DataSourceUpdate,
    SourceTableResponse,
    SyncResultResponse,
)
from datapilot_semantic.metadata.sync_worker import sync_metadata

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/data-sources", tags=["数据源管理"])

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


async def _get_datasource_or_404(
    db: AsyncSession, datasource_id: UUID, tenant_id: UUID | None = None
) -> DataSource:
    """获取数据源，不存在则抛出 404。"""
    stmt = select(DataSource).where(
        DataSource.id == datasource_id,
        DataSource.deleted_at.is_(None),
    )
    if tenant_id is not None:
        stmt = stmt.where(DataSource.tenant_id == tenant_id)

    result = await db.execute(stmt)
    datasource = result.scalar_one_or_none()

    if datasource is None:
        raise NotFoundError(resource="数据源", resource_id=str(datasource_id))
    return datasource


# ---------------------------------------------------------------------------
# A-3: 数据源 CRUD API
# ---------------------------------------------------------------------------


@router.post("", response_model=DataSourceResponse, status_code=201)
async def create_datasource(
    body: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
) -> DataSourceResponse:
    """注册数据源。

    加密存储密码，创建数据源记录。
    """
    # 加密密码
    encrypted_pwd = encrypt_password(body.password)

    datasource = DataSource(
        name=body.name,
        type=body.type,
        host=body.host,
        port=body.port,
        database=body.database,
        username=body.username,
        password=encrypted_pwd,
        pool_size=body.pool_size,
        freshness_level=body.freshness_level,
        freshness_cron=body.freshness_cron,
        status="active",
    )
    db.add(datasource)
    await db.flush()
    await db.refresh(datasource)

    logger.info("数据源注册成功: id=%s, name=%s, type=%s", datasource.id, body.name, body.type)
    return DataSourceResponse.model_validate(datasource, from_attributes=True)


@router.get("", response_model=list[DataSourceResponse])
async def list_datasources(
    db: AsyncSession = Depends(get_db),
    type: str | None = Query(default=None, description="按类型过滤"),
    status: str | None = Query(default=None, description="按状态过滤"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> list[DataSourceResponse]:
    """获取数据源列表。"""
    stmt = select(DataSource).where(DataSource.deleted_at.is_(None))

    if type is not None:
        stmt = stmt.where(DataSource.type == type)
    if status is not None:
        stmt = stmt.where(DataSource.status == status)

    stmt = stmt.order_by(DataSource.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    datasources = result.scalars().all()

    return [DataSourceResponse.model_validate(ds, from_attributes=True) for ds in datasources]


@router.get("/{datasource_id}", response_model=DataSourceResponse)
async def get_datasource(
    datasource_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DataSourceResponse:
    """获取数据源详情。"""
    datasource = await _get_datasource_or_404(db, datasource_id)
    return DataSourceResponse.model_validate(datasource, from_attributes=True)


@router.put("/{datasource_id}", response_model=DataSourceResponse)
async def update_datasource(
    datasource_id: UUID,
    body: DataSourceUpdate,
    db: AsyncSession = Depends(get_db),
) -> DataSourceResponse:
    """更新数据源。"""
    datasource = await _get_datasource_or_404(db, datasource_id)

    update_data = body.model_dump(exclude_unset=True)

    # 如果更新了密码，需要加密
    if "password" in update_data and update_data["password"] is not None:
        update_data["password"] = encrypt_password(update_data["password"])

    for field, value in update_data.items():
        setattr(datasource, field, value)

    await db.flush()
    await db.refresh(datasource)

    logger.info("数据源更新成功: id=%s", datasource_id)
    return DataSourceResponse.model_validate(datasource, from_attributes=True)


@router.delete("/{datasource_id}", status_code=204)
async def delete_datasource(
    datasource_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除数据源（软删除）。"""
    datasource = await _get_datasource_or_404(db, datasource_id)
    datasource.deleted_at = datetime.now(UTC)
    datasource.status = "disabled"

    await db.flush()

    logger.info("数据源软删除成功: id=%s", datasource_id)


@router.get("/{datasource_id}/health", response_model=DataSourceHealthResponse)
async def get_datasource_health(
    datasource_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DataSourceHealthResponse:
    """获取数据源健康状态。

    执行实时连接测试，并记录健康状态。
    """
    datasource = await _get_datasource_or_404(db, datasource_id)

    # 执行连接测试
    config = DataConnectionConfig(
        type=datasource.type,
        host=datasource.host,
        port=datasource.port,
        database=datasource.database,
        username=datasource.username,
        password="",  # 加密后的密码无法用于连接测试
    )

    # 尝试连接测试（API 类型和密码未知情况下跳过）
    is_connected = test_connection(config) if datasource.type != "api" else True

    now = datetime.now(UTC)
    health_status = "healthy" if is_connected else "down"

    # 创建健康记录
    health_record = DataSourceHealth(
        datasource_id=datasource.id,
        status=health_status,
        avg_latency_ms=0 if is_connected else None,
        pool_usage=0.0 if is_connected else None,
        last_heartbeat=now,
    )
    db.add(health_record)

    # 更新数据源最后健康检查时间
    datasource.last_health_check = now
    await db.flush()
    await db.refresh(health_record)

    return DataSourceHealthResponse.model_validate(health_record, from_attributes=True)


# ---------------------------------------------------------------------------
# A-4: 元数据同步 API
# ---------------------------------------------------------------------------


@router.post("/{datasource_id}/sync", response_model=SyncResultResponse)
async def trigger_sync(
    datasource_id: UUID,
    db: AsyncSession = Depends(get_db),
    schema_name: str | None = Query(default=None, description="指定同步的 Schema 名"),
    force_full: bool = Query(default=False, description="是否强制全量同步"),
) -> SyncResultResponse:
    """触发元数据同步。

    调用 Schema Extractor 提取远程表结构，增量写入 source_tables。
    """
    datasource = await _get_datasource_or_404(db, datasource_id)

    if datasource.type == "api":
        raise ValidationError(
            message="API 类型的数据源不支持元数据同步",
            details={"datasource_id": str(datasource_id)},
        )

    result = await sync_metadata(
        db,
        datasource,
        schema_name=schema_name,
        force_full=force_full,
    )

    return result


@router.get("/{datasource_id}/tables", response_model=list[SourceTableResponse])
async def list_synced_tables(
    datasource_id: UUID,
    db: AsyncSession = Depends(get_db),
    schema_name: str | None = Query(default=None, description="按 Schema 过滤"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> list[SourceTableResponse]:
    """获取已同步的表列表。"""
    # 先验证数据源存在
    await _get_datasource_or_404(db, datasource_id)

    stmt = select(SourceTable).where(
        SourceTable.data_source_id == datasource_id,
        SourceTable.deleted_at.is_(None),
    )

    if schema_name is not None:
        stmt = stmt.where(SourceTable.schema_name == schema_name)

    stmt = stmt.order_by(SourceTable.table_name.asc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    tables = result.scalars().all()

    return [SourceTableResponse.model_validate(t, from_attributes=True) for t in tables]
