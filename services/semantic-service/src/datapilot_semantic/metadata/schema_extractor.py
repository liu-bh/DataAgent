"""Schema Extractor 模块。

从数据源读取 information_schema，提取表结构元数据。
支持 MySQL 和 PostgreSQL 方言（Doris/StarRocks 兼容 MySQL 协议）。
"""

from __future__ import annotations

import logging

from sqlalchemy import create_engine, text

from datapilot_semantic.metadata.datasource_pool import build_connection_url
from datapilot_semantic.metadata.schemas import (
    ColumnSchema,
    DataConnectionConfig,
    TableSchema,
)

logger = logging.getLogger(__name__)


def _get_schema_query(dialect: str) -> str:
    """根据方言返回查询 information_schema 的 SQL。

    Args:
        dialect: 数据库方言类型。

    Returns:
        查询 SQL 字符串。

    Raises:
        ValueError: 不支持的方言。
    """
    if dialect in ("mysql", "doris", "starrocks"):
        # MySQL 兼容协议
        return """
            SELECT
                c.TABLE_SCHEMA AS schema_name,
                c.TABLE_NAME AS table_name,
                c.COLUMN_NAME AS column_name,
                c.COLUMN_TYPE AS column_type,
                c.COLUMN_KEY AS column_key,
                c.COLUMN_COMMENT AS column_comment,
                t.TABLE_COMMENT AS table_comment,
                t.TABLE_ROWS AS table_rows
            FROM information_schema.COLUMNS c
            JOIN information_schema.TABLES t
                ON c.TABLE_SCHEMA = t.TABLE_SCHEMA
                AND c.TABLE_NAME = t.TABLE_NAME
            WHERE c.TABLE_SCHEMA = :schema_name
                AND t.TABLE_TYPE = 'BASE TABLE'
            ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION
        """
    elif dialect == "postgresql":
        return """
            SELECT
                c.table_schema AS schema_name,
                c.table_name AS table_name,
                c.column_name AS column_name,
                c.data_type AS column_type,
                    CASE
                        WHEN pk.column_name IS NOT NULL THEN 'PRI'
                        ELSE ''
                    END AS column_key,
                col_description((quote_ident(c.table_schema) || '.' || quote_ident(c.table_name))::regclass, c.ordinal_position) AS column_comment,
                obj_description((quote_ident(c.table_schema) || '.' || quote_ident(c.table_name))::regclass) AS table_comment,
                pg_class.reltuples::BIGINT AS table_rows
            FROM information_schema.columns c
            JOIN information_schema.tables t
                ON c.table_schema = t.table_schema
                AND c.table_name = t.table_name
            JOIN pg_class ON pg_class.relname = c.table_name
            JOIN pg_namespace ON pg_namespace.nspname = c.table_schema
                AND pg_namespace.oid = pg_class.relnamespace
            LEFT JOIN (
                SELECT
                    kcu.table_schema,
                    kcu.table_name,
                    kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
            ) pk
                ON c.table_schema = pk.table_schema
                AND c.table_name = pk.table_name
                AND c.column_name = pk.column_name
            WHERE c.table_schema = :schema_name
                AND t.table_type = 'BASE TABLE'
            ORDER BY c.table_name, c.ordinal_position
        """
    elif dialect == "clickhouse":
        # ClickHouse 不使用 information_schema，使用 system.columns
        return """
            SELECT
                database AS schema_name,
                table AS table_name,
                name AS column_name,
                type AS column_type,
                '' AS column_key,
                '' AS column_comment,
                comment AS table_comment,
                0 AS table_rows
            FROM system.columns
            WHERE database = :schema_name
            ORDER BY table, position
        """
    else:
        raise ValueError(f"不支持的数据源方言: {dialect}")


def extract_schema(
    config: DataConnectionConfig,
    schema_name: str | None = None,
) -> list[TableSchema]:
    """从数据源提取表结构元数据。

    Args:
        config: 数据源连接配置。
        schema_name: 要提取的 Schema 名。
            MySQL 默认为数据库名，PostgreSQL 默认为 'public'。

    Returns:
        表结构列表。

    Raises:
        ValueError: 不支持的数据源类型。
        RuntimeError: 连接或查询失败。
    """
    dialect = config.type.lower()

    # 默认 schema_name
    if schema_name is None:
        if dialect in ("mysql", "doris", "starrocks", "clickhouse"):
            schema_name = config.database
        else:
            schema_name = "public"

    query = _get_schema_query(dialect)
    url = build_connection_url(config)

    # 使用短生命周期的引擎执行查询
    engine = create_engine(
        url,
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )

    try:
        with engine.connect() as conn:
            result = conn.execute(text(query), {"schema_name": schema_name})
            rows = result.fetchall()
    except Exception as e:
        raise RuntimeError(f"提取 Schema 失败: {e}") from e
    finally:
        engine.dispose()

    # 按 table_name 聚合
    table_map: dict[str, TableSchema] = {}
    for row in rows:
        t_name: str = row.table_name
        col = ColumnSchema(
            name=row.column_name,
            type=row.column_type,
            is_primary_key=(row.column_key or "").strip().upper() == "PRI",
            description=row.column_comment if row.column_comment else None,
        )

        if t_name not in table_map:
            table_map[t_name] = TableSchema(
                table_name=t_name,
                schema_name=row.schema_name,
                columns=[],
                description=row.table_comment if row.table_comment else None,
                row_count=int(row.table_rows) if row.table_rows else None,
            )
        table_map[t_name].columns.append(col)

    tables = list(table_map.values())
    logger.info(
        "Schema 提取完成: dialect=%s, schema=%s, 表数量=%d",
        dialect,
        schema_name,
        len(tables),
    )
    return tables
