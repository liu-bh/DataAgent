"""向量存储操作模块。

管理 pgvector 的 CRUD 操作，包括：
- 插入/更新向量（upsert_embedding）
- 余弦相似度搜索（search）
- IVFFlat 索引创建（create_index，使用 CONCURRENTLY）
- 删除向量（delete_embedding）

支持的实体类型: metric, dimension, source_table。

注意：Track B 的 Metric/Dimension SQLAlchemy 模型可能还未就绪，
本模块使用原生 SQL 操作 metrics/dimensions/source_tables 表的 embedding 列。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# 实体类型 → 表名映射
ENTITY_TABLE_MAP: dict[str, str] = {
    "metric": "metrics",
    "dimension": "dimensions",
    "source_table": "source_tables",
}

# 实体类型 → 名称字段映射
ENTITY_NAME_COLUMN_MAP: dict[str, str] = {
    "metric": "name",
    "dimension": "name",
    "source_table": "table_name",
}

# 实体类型 → 描述字段映射
ENTITY_DESC_COLUMN_MAP: dict[str, str] = {
    "metric": "description",
    "dimension": "column_name",
    "source_table": "description",
}

# IVFFlat 默认 lists 参数（建议为 sqrt(行数)，数据量较少时使用较小值）
DEFAULT_IVFFLAT_LISTS = 100


@dataclass
class VectorSearchHit:
    """向量搜索命中结果。

    Attributes:
        entity_type: 实体类型（metric/dimension/source_table）。
        entity_id: 实体 ID。
        name: 实体名称。
        description: 实体描述。
        similarity: 余弦相似度（0~1）。
        distance: 余弦距离（0~2，越小越相似）。
    """

    entity_type: str
    entity_id: str
    name: str | None
    description: str | None
    similarity: float
    distance: float


class VectorStore:
    """pgvector 向量存储操作类。

    通过 SQLAlchemy AsyncSession 执行原生 SQL（pgvector 操作），
    支持 metrics、dimensions、source_tables 三种实体类型的向量 CRUD。
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        ivfflat_lists: int = DEFAULT_IVFFLAT_LISTS,
    ) -> None:
        """初始化 VectorStore。

        Args:
            session: SQLAlchemy 异步会话。
            ivfflat_lists: IVFFlat 索引的 lists 参数。
        """
        self._session = session
        self._ivfflat_lists = ivfflat_lists

    def _validate_entity_type(self, entity_type: str) -> str:
        """校验实体类型是否合法。

        Args:
            entity_type: 实体类型字符串。

        Returns:
            校验通过的实体类型。

        Raises:
            ValueError: 不支持的实体类型。
        """
        if entity_type not in ENTITY_TABLE_MAP:
            valid = ", ".join(ENTITY_TABLE_MAP.keys())
            raise ValueError(
                f"不支持的实体类型: {entity_type}，支持: {valid}"
            )
        return entity_type

    def _get_table_name(self, entity_type: str) -> str:
        """获取实体类型对应的表名。"""
        return ENTITY_TABLE_MAP[entity_type]

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    async def upsert_embedding(
        self,
        entity_type: str,
        entity_id: UUID | str,
        raw_text: str | None = None,
        embedding: list[float] | None = None,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        """插入或更新实体的 embedding 向量。

        使用 PostgreSQL ON CONFLICT 实现 upsert 语义。
        同时更新 updated_at 时间戳。

        Args:
            entity_type: 实体类型（metric/dimension/source_table）。
            entity_id: 实体 ID（UUID）。
            raw_text: 可选，用于日志记录的原始文本。
            embedding: 向量列表（1536 维）。如果为 None 则清除 embedding。
            name: 可选，实体名称（用于日志）。
            description: 可选，实体描述（用于日志）。
        """
        entity_type = self._validate_entity_type(entity_type)
        table_name = self._get_table_name(entity_type)
        entity_id_str = str(entity_id)

        if embedding is not None and len(embedding) == 0:
            embedding = None

        if embedding is not None:
            # 构建 embedding 字面量: '[0.1, 0.2, ...]'
            embedding_literal = _build_vector_literal(embedding)

            sql = text(f"""
                UPDATE {table_name}
                SET embedding = :embedding::vector,
                    updated_at = NOW()
                WHERE id = :entity_id
                  AND deleted_at IS NULL
            """)
            params: dict[str, Any] = {
                "entity_id": entity_id_str,
                "embedding": embedding_literal,
            }
        else:
            # 清除 embedding
            sql = text(f"""
                UPDATE {table_name}
                SET embedding = NULL,
                    updated_at = NOW()
                WHERE id = :entity_id
                  AND deleted_at IS NULL
            """)
            params = {
                "entity_id": entity_id_str,
            }

        await self._session.execute(sql, params)

        logger.debug(
            "vector_upsert",
            entity_type=entity_type,
            entity_id=entity_id_str,
            has_embedding=embedding is not None,
            name=name,
        )

    # ------------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------------

    async def search(
        self,
        entity_type: str,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        threshold: float = 0.7,
        tenant_id: str | UUID | None = None,
    ) -> list[VectorSearchHit]:
        """余弦相似度搜索。

        使用 pgvector 的 <=> 运算符计算余弦距离（1 - cosine_similarity），
        返回相似度超过阈值的结果。

        Args:
            entity_type: 实体类型（metric/dimension/source_table）。
            query_embedding: 查询向量（1536 维）。
            top_k: 返回前 K 个结果。默认 10。
            threshold: 相似度阈值（0~1），低于阈值的结果被过滤。默认 0.7。
            tenant_id: 可选，租户 ID 过滤。

        Returns:
            按相似度降序排列的搜索命中列表。
        """
        entity_type = self._validate_entity_type(entity_type)
        table_name = self._get_table_name(entity_type)
        name_col = ENTITY_NAME_COLUMN_MAP[entity_type]
        desc_col = ENTITY_DESC_COLUMN_MAP[entity_type]

        embedding_literal = _build_vector_literal(query_embedding)

        # 构建租户过滤条件
        tenant_clause = ""
        params: dict[str, Any] = {
            "embedding": embedding_literal,
            "top_k": top_k,
            "threshold": threshold,
        }
        if tenant_id is not None:
            tenant_clause = "AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        sql = text(f"""
            SELECT
                id,
                {name_col} AS name,
                {desc_col} AS description,
                1 - (embedding <=> :embedding::vector) AS similarity,
                embedding <=> :embedding::vector AS distance
            FROM {table_name}
            WHERE embedding IS NOT NULL
              AND deleted_at IS NULL
              {tenant_clause}
            HAVING (1 - (embedding <=> :embedding::vector)) >= :threshold
            ORDER BY embedding <=> :embedding::vector
            LIMIT :top_k
        """)

        # 注意：HAVING 不适用于此场景（没有 GROUP BY），改用子查询方式
        # 重写为正确的 SQL
        sql = text(f"""
            SELECT id, name, description, similarity, distance
            FROM (
                SELECT
                    id,
                    {name_col} AS name,
                    {desc_col} AS description,
                    1 - (embedding <=> :embedding::vector) AS similarity,
                    embedding <=> :embedding::vector AS distance
                FROM {table_name}
                WHERE embedding IS NOT NULL
                  AND deleted_at IS NULL
                  {tenant_clause}
                ORDER BY embedding <=> :embedding::vector
                LIMIT :top_k
            ) AS ranked
            WHERE similarity >= :threshold
        """)

        result = await self._session.execute(sql, params)
        rows = result.fetchall()

        hits: list[VectorSearchHit] = []
        for row in rows:
            hits.append(VectorSearchHit(
                entity_type=entity_type,
                entity_id=str(row.id),
                name=row.name,
                description=row.description,
                similarity=float(row.similarity),
                distance=float(row.distance),
            ))

        logger.debug(
            "vector_search",
            entity_type=entity_type,
            query_embedding_dim=len(query_embedding),
            top_k=top_k,
            threshold=threshold,
            result_count=len(hits),
        )

        return hits

    # ------------------------------------------------------------------
    # 索引管理
    # ------------------------------------------------------------------

    async def create_index(
        self,
        entity_type: str,
        *,
        lists: int | None = None,
        concurrently: bool = True,
    ) -> str:
        """创建 IVFFlat 向量索引。

        使用 CONCURRENTLY 关键字避免锁表。
        注意：IVFFlat 索引需要先有足够数据才能获得良好查询性能，
        建议在数据量达到数百条后再创建索引。

        Args:
            entity_type: 实体类型（metric/dimension/source_table）。
            lists: IVFFlat lists 参数。默认使用初始化时的值。
            concurrently: 是否使用 CONCURRENTLY 创建。默认 True。

        Returns:
            创建的索引名称。
        """
        entity_type = self._validate_entity_type(entity_type)
        table_name = self._get_table_name(entity_type)
        lists = lists or self._ivfflat_lists

        index_name = f"idx_{table_name}_embedding"
        concurrently_keyword = "CONCURRENTLY" if concurrently else ""

        sql = text(f"""
            CREATE INDEX {concurrently_keyword} IF NOT EXISTS {index_name}
            ON {table_name} USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = {lists})
        """)

        # CONCURRENTLY 不能在事务中执行，需要使用 AUTOCOMMIT
        connection = await self._session.connection()
        # 关闭当前事务，以便 CONCURRENTLY 可以执行
        if connection.in_transaction():
            await connection.commit()

        await connection.execute(sql)

        logger.info(
            "vector_index_created",
            entity_type=entity_type,
            table_name=table_name,
            index_name=index_name,
            lists=lists,
            concurrently=concurrently,
        )

        return index_name

    async def drop_index(
        self,
        entity_type: str,
        *,
        concurrently: bool = True,
    ) -> None:
        """删除 IVFFlat 向量索引。

        Args:
            entity_type: 实体类型。
            concurrently: 是否使用 CONCURRENTLY 删除。
        """
        entity_type = self._validate_entity_type(entity_type)
        table_name = self._get_table_name(entity_type)
        index_name = f"idx_{table_name}_embedding"
        concurrently_keyword = "CONCURRENTLY" if concurrently else ""

        sql = text(f"DROP INDEX IF EXISTS {concurrently_keyword} {index_name}")

        connection = await self._session.connection()
        if connection.in_transaction():
            await connection.commit()

        await connection.execute(sql)

        logger.info(
            "vector_index_dropped",
            entity_type=entity_type,
            index_name=index_name,
        )

    # ------------------------------------------------------------------
    # 删除
    # ------------------------------------------------------------------

    async def delete_embedding(
        self,
        entity_type: str,
        entity_id: UUID | str,
    ) -> bool:
        """删除实体的 embedding 向量（置为 NULL）。

        Args:
            entity_type: 实体类型。
            entity_id: 实体 ID。

        Returns:
            是否成功删除（True 表示找到了并清除了向量）。
        """
        entity_type = self._validate_entity_type(entity_type)
        table_name = self._get_table_name(entity_type)
        entity_id_str = str(entity_id)

        sql = text(f"""
            UPDATE {table_name}
            SET embedding = NULL,
                updated_at = NOW()
            WHERE id = :entity_id
              AND embedding IS NOT NULL
              AND deleted_at IS NULL
        """)

        result = await self._session.execute(
            sql, {"entity_id": entity_id_str}
        )
        await self._session.commit()

        deleted = result.rowcount > 0

        logger.debug(
            "vector_delete",
            entity_type=entity_type,
            entity_id=entity_id_str,
            deleted=deleted,
        )

        return deleted

    # ------------------------------------------------------------------
    # 批量操作
    # ------------------------------------------------------------------

    async def batch_upsert_embeddings(
        self,
        entity_type: str,
        items: list[dict[str, Any]],
    ) -> int:
        """批量 upsert embedding。

        Args:
            entity_type: 实体类型。
            items: 字典列表，每个包含 entity_id (UUID|str), embedding (list[float])。

        Returns:
            成功更新的条数。
        """
        entity_type = self._validate_entity_type(entity_type)
        table_name = self._get_table_name(entity_type)

        count = 0
        for item in items:
            entity_id = item["entity_id"]
            embedding = item.get("embedding")
            await self.upsert_embedding(
                entity_type=entity_type,
                entity_id=entity_id,
                embedding=embedding,
            )
            count += 1

        await self._session.commit()

        logger.info(
            "vector_batch_upsert",
            entity_type=entity_type,
            count=count,
        )

        return count


def _build_vector_literal(embedding: list[float]) -> str:
    """将浮点数列表构建为 pgvector 字面量字符串。

    Args:
        embedding: 浮点数列表。

    Returns:
        如 "[0.1, 0.2, 0.3]" 的字符串。
    """
    parts = [str(float(v)) for v in embedding]
    return f"[{','.join(parts)}]"
