"""混合搜索 + RRF 重排模块。

结合语义搜索（向量余弦相似度）和关键词搜索（PostgreSQL 全文检索 / ILIKE），
使用 Reciprocal Rank Fusion (RRF) 算法重排结果。

RRF 公式::

    RRF_score(d) = Σ 1/(k + rank_i(d))  其中 k=60（标准默认值）

用法::

    searcher = HybridSearcher(session, embedding_client)
    results = await searcher.search(
        query="上个月销售额",
        entity_types=["metric", "dimension"],
        top_k=20,
    )
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from datapilot_semantic.retrieval.embedding import EmbeddingClient
from datapilot_semantic.retrieval.vector_store import VectorSearchHit, VectorStore

logger = structlog.get_logger(__name__)

# 实体类型 → 表名映射（与 vector_store 保持一致）
ENTITY_TABLE_MAP: dict[str, str] = {
    "metric": "metrics",
    "dimension": "dimensions",
    "source_table": "source_tables",
}

# 实体类型 → 名称列映射
ENTITY_NAME_COLUMN_MAP: dict[str, str] = {
    "metric": "name",
    "dimension": "name",
    "source_table": "table_name",
}

# 实体类型 → 描述列映射
ENTITY_DESC_COLUMN_MAP: dict[str, str] = {
    "metric": "description",
    "dimension": "column_name",
    "source_table": "description",
}

# RRF 默认 k 值（标准值，推荐 60）
DEFAULT_RRF_K = 60

# 语义搜索默认 top_k（从向量检索取更多候选，再重排）
SEMANTIC_SEARCH_CANDIDATE_K = 50

# 关键词搜索默认 top_k
KEYWORD_SEARCH_CANDIDATE_K = 50


@dataclass
class SearchHit:
    """混合搜索结果。

    Attributes:
        entity_type: 实体类型（metric/dimension/source_table）。
        entity_id: 实体 ID。
        score: RRF 重排得分。
        entity_name: 实体名称。
        entity_description: 实体描述。
        semantic_score: 语义搜索相似度（None 表示未参与语义搜索）。
        keyword_score: 关键词搜索排名倒数（None 表示未参与关键词搜索）。
    """

    entity_type: str
    entity_id: str
    score: float
    entity_name: str | None = None
    entity_description: str | None = None
    semantic_score: float | None = None
    keyword_score: float | None = None


@dataclass
class _RankedItem:
    """内部用于 RRF 计算的中间结构。"""

    entity_type: str
    entity_id: str
    name: str | None = None
    description: str | None = None
    semantic_rank: int | None = None
    semantic_similarity: float | None = None
    keyword_rank: int | None = None


class HybridSearcher:
    """混合搜索引擎，结合语义搜索和关键词搜索，使用 RRF 重排。"""

    def __init__(
        self,
        session: AsyncSession,
        embedding_client: EmbeddingClient,
        *,
        rrf_k: int = DEFAULT_RRF_K,
        semantic_top_k: int = SEMANTIC_SEARCH_CANDIDATE_K,
        keyword_top_k: int = KEYWORD_SEARCH_CANDIDATE_K,
        semantic_threshold: float = 0.5,
        default_tenant_id: str | UUID | None = None,
    ) -> None:
        """初始化 HybridSearcher。

        Args:
            session: SQLAlchemy 异步会话。
            embedding_client: Embedding 客户端。
            rrf_k: RRF 的 k 参数。默认 60。
            semantic_top_k: 语义搜索候选数量。默认 50。
            keyword_top_k: 关键词搜索候选数量。默认 50。
            semantic_threshold: 语义搜索相似度阈值。默认 0.5（宽松，因为后续 RRF 会重排）。
            default_tenant_id: 默认租户 ID，用于过滤。
        """
        self._session = session
        self._embedding_client = embedding_client
        self._vector_store = VectorStore(session)
        self._rrf_k = rrf_k
        self._semantic_top_k = semantic_top_k
        self._keyword_top_k = keyword_top_k
        self._semantic_threshold = semantic_threshold
        self._default_tenant_id = (
            str(default_tenant_id) if default_tenant_id else None
        )

    # ------------------------------------------------------------------
    # 语义搜索（向量）
    # ------------------------------------------------------------------

    async def _semantic_search(
        self,
        query_embedding: list[float],
        entity_types: list[str],
        tenant_id: str | UUID | None = None,
    ) -> dict[str, _RankedItem]:
        """执行语义搜索，返回以 entity_key 为键的排名结果。

        Args:
            query_embedding: 查询向量。
            entity_types: 实体类型列表。
            tenant_id: 租户 ID。

        Returns:
            {entity_type:entity_id: _RankedItem} 字典。
        """
        results: dict[str, _RankedItem] = {}

        for entity_type in entity_types:
            if entity_type not in ENTITY_TABLE_MAP:
                continue

            try:
                hits = await self._vector_store.search(
                    entity_type=entity_type,
                    query_embedding=query_embedding,
                    top_k=self._semantic_top_k,
                    threshold=self._semantic_threshold,
                    tenant_id=tenant_id,
                )

                for rank, hit in enumerate(hits, start=1):
                    key = f"{hit.entity_type}:{hit.entity_id}"
                    if key not in results:
                        results[key] = _RankedItem(
                            entity_type=hit.entity_type,
                            entity_id=hit.entity_id,
                            name=hit.name,
                            description=hit.description,
                        )
                    results[key].semantic_rank = rank
                    results[key].semantic_similarity = hit.similarity

            except Exception as e:
                logger.warning(
                    "semantic_search_failed",
                    entity_type=entity_type,
                    error=str(e),
                )

        return results

    # ------------------------------------------------------------------
    # 关键词搜索（全文检索 + ILIKE）
    # ------------------------------------------------------------------

    async def _keyword_search(
        self,
        query: str,
        entity_types: list[str],
        tenant_id: str | UUID | None = None,
    ) -> dict[str, _RankedItem]:
        """执行关键词搜索（tsvector + ILIKE），返回排名结果。

        使用 PostgreSQL 的 to_tsvector('simple', ...) + to_tsquery('simple', ...)
        进行全文检索，同时配合 ILIKE 模糊匹配。

        Args:
            query: 用户查询文本。
            entity_types: 实体类型列表。
            tenant_id: 租户 ID。

        Returns:
            {entity_type:entity_id: _RankedItem} 字典。
        """
        results: dict[str, _RankedItem] = {}

        # 构建全文检索查询词（拆分空格，用 & 连接）
        # 使用 'simple' 配置避免中文分词问题
        query_tokens = _tokenize_for_search(query)
        tsquery = " & ".join(query_tokens) if query_tokens else ""

        for entity_type in entity_types:
            if entity_type not in ENTITY_TABLE_MAP:
                continue

            table_name = ENTITY_TABLE_MAP[entity_type]
            name_col = ENTITY_NAME_COLUMN_MAP[entity_type]
            desc_col = ENTITY_DESC_COLUMN_MAP[entity_type]

            try:
                items = await self._keyword_search_single_table(
                    table_name=table_name,
                    entity_type=entity_type,
                    name_col=name_col,
                    desc_col=desc_col,
                    tsquery=tsquery,
                    query=query,
                    top_k=self._keyword_top_k,
                    tenant_id=tenant_id,
                )

                for rank, item in enumerate(items, start=1):
                    key = f"{item.entity_type}:{item.entity_id}"
                    if key not in results:
                        results[key] = _RankedItem(
                            entity_type=item.entity_type,
                            entity_id=item.entity_id,
                            name=item.name,
                            description=item.description,
                        )
                    results[key].keyword_rank = rank

            except Exception as e:
                logger.warning(
                    "keyword_search_failed",
                    entity_type=entity_type,
                    error=str(e),
                )

        return results

    async def _keyword_search_single_table(
        self,
        table_name: str,
        entity_type: str,
        name_col: str,
        desc_col: str,
        tsquery: str,
        query: str,
        top_k: int,
        tenant_id: str | UUID | None = None,
    ) -> list[_RankedItem]:
        """对单张表执行关键词搜索。

        使用联合评分方式：
        - tsvector 全文检索匹配得分
        - ILIKE 前缀匹配得分
        - 两者取最高分作为最终排序依据

        Args:
            table_name: 表名。
            entity_type: 实体类型。
            name_col: 名称列名。
            desc_col: 描述列名。
            tsquery: 全文检索查询字符串。
            query: 原始查询文本。
            top_k: 返回数量。
            tenant_id: 租户 ID。

        Returns:
            排名后的 _RankedItem 列表。
        """
        params: dict[str, Any] = {
            "query": f"%{query}%",
            "query_prefix": f"{query}%",
            "top_k": top_k,
        }

        tenant_clause = ""
        if tenant_id is not None:
            tenant_clause = "AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        # 构建评分表达式
        # ts_rank: 全文检索相关度
        # ILIKE 匹配: 名称前缀匹配优先
        if tsquery:
            # 有有效 token 时使用全文检索 + ILIKE
            score_expr = f"""
                GREATEST(
                    ts_rank(to_tsvector('simple', COALESCE({name_col}, '')), to_tsquery('simple', :tsquery)),
                    CASE WHEN {name_col} ILIKE :query_prefix THEN 2.0
                         WHEN {name_col} ILIKE :query THEN 1.0
                         WHEN COALESCE({desc_col}, '') ILIKE :query THEN 0.5
                         ELSE 0.0
                    END
                ) AS score
            """
            params["tsquery"] = tsquery
        else:
            # 无有效 token 时仅用 ILIKE
            score_expr = f"""
                CASE WHEN {name_col} ILIKE :query_prefix THEN 2.0
                     WHEN {name_col} ILIKE :query THEN 1.0
                     WHEN COALESCE({desc_col}, '') ILIKE :query THEN 0.5
                     ELSE 0.0
                END AS score
            """

        sql = text(f"""
            SELECT
                id,
                {name_col} AS name,
                {desc_col} AS description,
                {score_expr}
            FROM {table_name}
            WHERE deleted_at IS NULL
              {tenant_clause}
              AND (
                  {name_col} ILIKE :query
                  OR COALESCE({desc_col}, '') ILIKE :query
              )
            ORDER BY score DESC
            LIMIT :top_k
        """)

        result = await self._session.execute(sql, params)
        rows = result.fetchall()

        return [
            _RankedItem(
                entity_type=entity_type,
                entity_id=str(row.id),
                name=row.name,
                description=row.description,
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # RRF 重排
    # ------------------------------------------------------------------

    @staticmethod
    def _rrf_fusion(
        semantic_results: dict[str, _RankedItem],
        keyword_results: dict[str, _RankedItem],
        k: int = DEFAULT_RRF_K,
    ) -> list[SearchHit]:
        """使用 Reciprocal Rank Fusion 算法合并并重排两路搜索结果。

        RRF 公式: RRF_score(d) = Σ 1/(k + rank_i(d))

        Args:
            semantic_results: 语义搜索结果（entity_key → _RankedItem）。
            keyword_results: 关键词搜索结果（entity_key → _RankedItem）。
            k: RRF 参数，默认 60。

        Returns:
            按 RRF 得分降序排列的 SearchHit 列表。
        """
        # 收集所有唯一实体
        all_keys = set(semantic_results.keys()) | set(keyword_results.keys())

        # 计算 RRF 得分
        scored: list[SearchHit] = []
        for key in all_keys:
            # 语义搜索排名（1-based），key 可能只存在于一路结果中
            sem_item = semantic_results.get(key)
            kw_item = keyword_results.get(key)
            sem_rank = sem_item.semantic_rank if sem_item else None
            kw_rank = kw_item.keyword_rank if kw_item else None

            rrf_score = 0.0
            if sem_rank is not None:
                rrf_score += 1.0 / (k + sem_rank)
            if kw_rank is not None:
                rrf_score += 1.0 / (k + kw_rank)

            # 取语义搜索的结果获取名称和描述（优先）
            item = semantic_results.get(key) or keyword_results.get(key)

            scored.append(SearchHit(
                entity_type=item.entity_type,
                entity_id=item.entity_id,
                score=rrf_score,
                entity_name=item.name,
                entity_description=item.description,
                semantic_score=item.semantic_similarity,
                keyword_score=(
                    1.0 / (k + kw_rank) if kw_rank is not None else None
                ),
            ))

        # 按 RRF 得分降序排列
        scored.sort(key=lambda x: x.score, reverse=True)

        return scored

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        entity_types: list[str] | None = None,
        *,
        top_k: int = 20,
        tenant_id: str | UUID | None = None,
    ) -> list[SearchHit]:
        """执行混合搜索。

        流程:
        1. 将 query 通过 EmbeddingClient 转为向量
        2. 并行执行语义搜索和关键词搜索
        3. 使用 RRF 重排合并结果
        4. 返回 top_k 个结果

        Args:
            query: 用户查询文本。
            entity_types: 要搜索的实体类型列表。默认全部。
            top_k: 返回结果数量。默认 20。
            tenant_id: 租户 ID。默认使用初始化时的 default_tenant_id。

        Returns:
            按综合得分降序排列的 SearchHit 列表。
        """
        if entity_types is None:
            entity_types = list(ENTITY_TABLE_MAP.keys())

        effective_tenant_id = tenant_id or self._default_tenant_id

        # 1. 向量化查询
        try:
            query_embedding = await self._embedding_client.embed_text(query)
        except Exception as e:
            logger.error(
                "hybrid_search_embedding_failed",
                query=query,
                error=str(e),
            )
            # 向量化失败时回退到纯关键词搜索
            logger.info("hybrid_search_fallback_to_keyword", query=query)
            keyword_results = await self._keyword_search(
                query=query,
                entity_types=entity_types,
                tenant_id=effective_tenant_id,
            )
            hits = self._rrf_fusion(
                semantic_results={},
                keyword_results=keyword_results,
                k=self._rrf_k,
            )
            return hits[:top_k]

        # 2. 并行执行语义搜索和关键词搜索
        import asyncio

        sem_task = self._semantic_search(
            query_embedding=query_embedding,
            entity_types=entity_types,
            tenant_id=effective_tenant_id,
        )
        kw_task = self._keyword_search(
            query=query,
            entity_types=entity_types,
            tenant_id=effective_tenant_id,
        )

        sem_results, kw_results = await asyncio.gather(sem_task, kw_task)

        # 3. RRF 重排
        hits = self._rrf_fusion(
            semantic_results=sem_results,
            keyword_results=kw_results,
            k=self._rrf_k,
        )

        logger.info(
            "hybrid_search_completed",
            query=query,
            entity_types=entity_types,
            semantic_count=len(sem_results),
            keyword_count=len(kw_results),
            total_before_cutoff=len(hits),
            top_k=top_k,
        )

        return hits[:top_k]


def _tokenize_for_search(query: str) -> list[str]:
    """为全文检索分词。

    简单分词：按非字母数字字符拆分，过滤空串和过短的 token。
    中文文本不做拆分（PostgreSQL 'simple' 配置不支持中文分词，
    此时全文检索退化为精确匹配，主要靠 ILIKE）。

    仅返回 ASCII token（字母和数字），中文 token 会被过滤掉，
    因为 to_tsquery('simple', ...) 无法解析中文。

    Args:
        query: 用户查询文本。

    Returns:
        分词后的 token 列表（仅 ASCII）。
    """
    # 按非字母数字字符拆分
    tokens = re.split(r'[^\w]+', query, flags=re.UNICODE)
    # 过滤空串、过短的 token、非 ASCII token（中文等）
    return [t.lower() for t in tokens if len(t) >= 2 and t.isascii()]
