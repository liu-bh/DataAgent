"""数据源管理服务。

将原本分散在 api/routes/data_sources.py 中的业务逻辑抽取到 Service 层，
实现 Controller-Service 分层。Service 层不直接处理 HTTP 请求/响应，
通过抛出自定义异常（AppError、NotFoundError、ValidationError）与路由层交互。
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from datapilot_common.exceptions import NotFoundError, ValidationError

from datapilot_semantic.metadata.datasource_pool import encrypt_password, test_connection
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
from datapilot_semantic.models.schemas import PaginatedResponse, PaginationMeta
from datapilot_semantic.metadata.sync_worker import sync_metadata

logger = structlog.get_logger(__name__)


class DataSourceService:
    """数据源管理服务，封装数据源 CRUD 业务逻辑。

    将原本分散在 api/routes/data_sources.py 中的业务逻辑抽取到此处。
    由于没有真实的数据库连接，Service 方法使用 mock 实现。

    Args:
        session_factory: 可选的数据库会话工厂，用于创建会话。
    """

    def __init__(self, session_factory: Callable[[], AsyncSession] | None = None) -> None:
        """初始化 DataSourceService。

        Args:
            session_factory: 可选的数据库会话工厂函数。
        """
        self._session_factory = session_factory

    async def _get_datasource_or_raise(
        self,
        db: AsyncSession,
        datasource_id: UUID,
        tenant_id: Optional[UUID] = None,
    ) -> DataSource:
        """获取数据源，不存在则抛出 NotFoundError。

        Args:
            db: 数据库会话。
            datasource_id: 数据源 ID。
            tenant_id: 可选的租户 ID，用于多租户过滤。

        Returns:
            数据源 ORM 对象。

        Raises:
            NotFoundError: 数据源不存在。
        """
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

    async def create_datasource(
        self,
        data: DataSourceCreate,
        db: AsyncSession,
    ) -> DataSourceResponse:
        """注册数据源。

        加密存储密码，创建数据源记录。

        Args:
            data: 创建请求体。
            db: 数据库会话。

        Returns:
            创建的数据源响应。
        """
        # 加密密码
        encrypted_pwd = encrypt_password(data.password)

        datasource = DataSource(
            name=data.name,
            type=data.type,
            host=data.host,
            port=data.port,
            database=data.database,
            username=data.username,
            password=encrypted_pwd,
            pool_size=data.pool_size,
            freshness_level=data.freshness_level,
            freshness_cron=data.freshness_cron,
            status="active",
        )
        db.add(datasource)
        await db.flush()
        await db.refresh(datasource)

        logger.info(
            "数据源注册成功",
            id=str(datasource.id),
            name=data.name,
            type=data.type,
        )
        return DataSourceResponse.model_validate(datasource, from_attributes=True)

    async def get_datasource(
        self,
        datasource_id: UUID,
        db: AsyncSession,
    ) -> DataSourceResponse:
        """获取数据源详情。

        Args:
            datasource_id: 数据源 ID。
            db: 数据库会话。

        Returns:
            数据源响应。

        Raises:
            NotFoundError: 数据源不存在。
        """
        datasource = await self._get_datasource_or_raise(db, datasource_id)
        return DataSourceResponse.model_validate(datasource, from_attributes=True)

    async def list_datasources(
        self,
        db: AsyncSession,
        *,
        type: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[DataSourceResponse]:
        """获取数据源列表（分页）。

        Args:
            db: 数据库会话。
            type: 按类型过滤。
            status: 按状态过滤。
            page: 页码，从 1 开始。
            page_size: 每页条数。

        Returns:
            分页的数据源响应列表。
        """
        # 查询总数
        count_stmt = select(func.count()).select_from(DataSource).where(
            DataSource.deleted_at.is_(None)
        )
        if type is not None:
            count_stmt = count_stmt.where(DataSource.type == type)
        if status is not None:
            count_stmt = count_stmt.where(DataSource.status == status)

        total = (await db.execute(count_stmt)).scalar() or 0

        # 分页查询
        data_stmt = select(DataSource).where(DataSource.deleted_at.is_(None))
        if type is not None:
            data_stmt = data_stmt.where(DataSource.type == type)
        if status is not None:
            data_stmt = data_stmt.where(DataSource.status == status)

        data_stmt = (
            data_stmt.order_by(DataSource.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await db.execute(data_stmt)
        datasources = result.scalars().all()

        data = [
            DataSourceResponse.model_validate(ds, from_attributes=True)
            for ds in datasources
        ]

        return PaginatedResponse[DataSourceResponse](
            data=data,
            pagination=PaginationMeta(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=math.ceil(total / page_size) if page_size > 0 else 0,
            ),
        )

    async def update_datasource(
        self,
        datasource_id: UUID,
        data: DataSourceUpdate,
        db: AsyncSession,
    ) -> DataSourceResponse:
        """更新数据源。

        仅更新请求体中非 None 的字段。如果更新了密码，需要加密。

        Args:
            datasource_id: 数据源 ID。
            data: 更新请求体。
            db: 数据库会话。

        Returns:
            更新后的数据源响应。

        Raises:
            NotFoundError: 数据源不存在。
        """
        datasource = await self._get_datasource_or_raise(db, datasource_id)

        update_data = data.model_dump(exclude_unset=True)

        # 如果更新了密码，需要加密
        if "password" in update_data and update_data["password"] is not None:
            update_data["password"] = encrypt_password(update_data["password"])

        for field, value in update_data.items():
            setattr(datasource, field, value)

        await db.flush()
        await db.refresh(datasource)

        logger.info("数据源更新成功", id=str(datasource_id))
        return DataSourceResponse.model_validate(datasource, from_attributes=True)

    async def delete_datasource(
        self,
        datasource_id: UUID,
        db: AsyncSession,
    ) -> None:
        """删除数据源（软删除）。

        将 deleted_at 设置为当前时间，status 设置为 disabled。

        Args:
            datasource_id: 数据源 ID。
            db: 数据库会话。

        Raises:
            NotFoundError: 数据源不存在。
        """
        datasource = await self._get_datasource_or_raise(db, datasource_id)
        datasource.deleted_at = datetime.now(timezone.utc)
        datasource.status = "disabled"

        await db.flush()

        logger.info("数据源软删除成功", id=str(datasource_id))

    async def sync_datasource(
        self,
        datasource_id: UUID,
        db: AsyncSession,
        *,
        schema_name: Optional[str] = None,
        force_full: bool = False,
    ) -> SyncResultResponse:
        """触发元数据同步。

        调用 Schema Extractor 提取远程表结构，增量写入 source_tables。

        Args:
            datasource_id: 数据源 ID。
            db: 数据库会话。
            schema_name: 指定同步的 Schema 名。
            force_full: 是否强制全量同步。

        Returns:
            同步结果响应。

        Raises:
            NotFoundError: 数据源不存在。
            ValidationError: API 类型的数据源不支持元数据同步。
        """
        datasource = await self._get_datasource_or_raise(db, datasource_id)

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

    async def get_datasource_health(
        self,
        datasource_id: UUID,
        db: AsyncSession,
    ) -> DataSourceHealthResponse:
        """获取数据源健康状态。

        执行实时连接测试，并记录健康状态。

        Args:
            datasource_id: 数据源 ID。
            db: 数据库会话。

        Returns:
            数据源健康检查响应。

        Raises:
            NotFoundError: 数据源不存在。
        """
        datasource = await self._get_datasource_or_raise(db, datasource_id)

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

        now = datetime.now(timezone.utc)
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

        logger.info(
            "数据源健康检查完成",
            datasource_id=str(datasource_id),
            status=health_status,
        )

        return DataSourceHealthResponse.model_validate(health_record, from_attributes=True)

    async def list_synced_tables(
        self,
        datasource_id: UUID,
        db: AsyncSession,
        *,
        schema_name: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[SourceTableResponse]:
        """获取已同步的表列表。

        Args:
            datasource_id: 数据源 ID。
            db: 数据库会话。
            schema_name: 按 Schema 过滤。
            page: 页码。
            page_size: 每页数量。

        Returns:
            源表响应列表。

        Raises:
            NotFoundError: 数据源不存在。
        """
        # 先验证数据源存在
        await self._get_datasource_or_raise(db, datasource_id)

        stmt = select(SourceTable).where(
            SourceTable.data_source_id == datasource_id,
            SourceTable.deleted_at.is_(None),
        )

        if schema_name is not None:
            stmt = stmt.where(SourceTable.schema_name == schema_name)

        stmt = (
            stmt.order_by(SourceTable.table_name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await db.execute(stmt)
        tables = result.scalars().all()

        return [
            SourceTableResponse.model_validate(t, from_attributes=True) for t in tables
        ]
