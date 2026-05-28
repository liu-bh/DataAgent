"""元数据同步后台任务模块。

负责增量同步数据源表结构到 source_tables 表。
为 Track C 向量更新预留接口。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from datapilot_semantic.metadata.models import DataSource, SourceTable
from datapilot_semantic.metadata.schema_extractor import extract_schema
from datapilot_semantic.metadata.schemas import (
    DataConnectionConfig,
    SyncResultResponse,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def sync_metadata(
    db: AsyncSession,
    datasource: DataSource,
    *,
    schema_name: str | None = None,
    force_full: bool = False,
) -> SyncResultResponse:
    """同步数据源元数据到 source_tables 表。

    逻辑:
    1. 使用 DataSource 配置构建连接，提取表结构。
    2. 对比现有 source_tables 记录，执行增量更新。
    3. 新表插入，已有表更新 columns/row_count，已删除表软删除。

    Args:
        db: 异步数据库会话。
        datasource: 数据源 ORM 对象。
        schema_name: 指定同步的 schema，默认自动推断。
        force_full: 是否强制全量同步（忽略增量对比）。

    Returns:
        同步结果。
    """
    # 构建连接配置
    config = DataConnectionConfig(
        type=datasource.type,
        host=datasource.host,
        port=datasource.port,
        database=datasource.database,
        username=datasource.username,
        password=datasource.password,  # 注意：这里存储的是加密后的密码，需要解密后使用
        # TODO: 解密密码（目前存储的是哈希，需要改为可逆加密才能连接）
    )

    try:
        # 提取远程表结构
        remote_tables = extract_schema(config, schema_name=schema_name)
    except Exception as e:
        logger.error("同步失败，无法提取 Schema: datasource_id=%s, error=%s", datasource.id, e)
        return SyncResultResponse(
            datasource_id=datasource.id,
            status="failed",
            total_tables=0,
            synced_tables=0,
            updated_tables=0,
            new_tables=0,
            message=f"Schema 提取失败: {e}",
            synced_at=datetime.now(UTC),
        )

    if not remote_tables:
        return SyncResultResponse(
            datasource_id=datasource.id,
            status="success",
            total_tables=0,
            synced_tables=0,
            updated_tables=0,
            new_tables=0,
            message="未发现任何表",
            synced_at=datetime.now(UTC),
        )

    now = datetime.now(UTC)
    total_tables = len(remote_tables)
    new_count = 0
    updated_count = 0
    synced_count = 0

    # 获取当前已有的 source_tables（未软删除的）
    existing_stmt = select(SourceTable).where(
        SourceTable.data_source_id == datasource.id,
        SourceTable.tenant_id == datasource.tenant_id,
        SourceTable.deleted_at.is_(None),
    )
    result = await db.execute(existing_stmt)
    existing_tables = result.scalars().all()
    existing_map: dict[str, SourceTable] = {t.table_name: t for t in existing_tables}

    remote_table_names = {t.table_name for t in remote_tables}

    # 处理每个远程表
    for table_schema in remote_tables:
        columns_data = [col.model_dump() for col in table_schema.columns]

        if table_schema.table_name in existing_map:
            # 已存在 → 更新
            existing = existing_map[table_schema.table_name]
            existing.columns = columns_data
            existing.row_count = table_schema.row_count
            existing.description = table_schema.description
            existing.schema_name = table_schema.schema_name or existing.schema_name
            existing.last_synced_at = now
            updated_count += 1
            synced_count += 1
        else:
            # 新表 → 插入
            new_table = SourceTable(
                tenant_id=datasource.tenant_id,
                data_source_id=datasource.id,
                schema_name=table_schema.schema_name,
                table_name=table_schema.table_name,
                columns=columns_data,
                row_count=table_schema.row_count,
                description=table_schema.description,
                last_synced_at=now,
            )
            db.add(new_table)
            new_count += 1
            synced_count += 1

    # 软删除远程不存在的表（仅全量同步时）
    if force_full:
        for table_name, existing in existing_map.items():
            if table_name not in remote_table_names:
                existing.deleted_at = now
                logger.info(
                    "软删除不存在的表: datasource_id=%s, table=%s",
                    datasource.id,
                    table_name,
                )

    # 更新数据源最后健康检查时间
    datasource.last_health_check = now

    await db.flush()

    status = "success" if synced_count == total_tables else "partial"
    message = f"同步完成: 共 {total_tables} 张表, 新增 {new_count}, 更新 {updated_count}"

    logger.info(
        "元数据同步完成: datasource_id=%s, status=%s, total=%d, new=%d, updated=%d",
        datasource.id,
        status,
        total_tables,
        new_count,
        updated_count,
    )

    # 预留：向量更新接口（Track C 负责实现）
    # await update_embeddings_for_new_tables(db, datasource.id, new_table_ids)

    return SyncResultResponse(
        datasource_id=datasource.id,
        status=status,
        total_tables=total_tables,
        synced_tables=synced_count,
        updated_tables=updated_count,
        new_tables=new_count,
        message=message,
        synced_at=now,
    )


# ---------------------------------------------------------------------------
# 预留向量更新接口（Track C 实现）
# ---------------------------------------------------------------------------


async def update_embeddings_for_new_tables(
    db: AsyncSession,
    datasource_id: UUID,
    table_ids: list[UUID],
) -> None:
    """为新增的表生成并存储语义向量。

    由 Track C（向量检索）负责实现。

    Args:
        db: 异步数据库会话。
        datasource_id: 数据源 ID。
        table_ids: 需要更新向量的表 ID 列表。
    """
    # TODO: Track C 实现
    # 1. 获取表的 columns 和 description
    # 2. 拼接为文本，调用 embedding 服务生成向量
    # 3. 更新 source_tables.embedding 字段
    logger.info(
        "向量更新预留接口: datasource_id=%s, table_count=%d",
        datasource_id,
        len(table_ids),
    )
