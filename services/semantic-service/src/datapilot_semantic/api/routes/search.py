"""语义搜索 API 路由。

提供混合搜索接口，结合语义搜索和关键词搜索，使用 RRF 重排返回结果。

接口列表:
- GET /api/v1/search — 混合搜索指标、维度、数据表
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from datapilot_semantic.api.dependencies import get_db as get_db_session
from datapilot_semantic.retrieval.embedding import EmbeddingClient
from datapilot_semantic.retrieval.hybrid_search import HybridSearcher, SearchHit

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/search", tags=["search"])

# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------


class SearchHitResponse(BaseModel):
    """搜索命中结果响应。"""

    entity_type: str = Field(..., description="实体类型：metric / dimension / source_table")
    entity_id: str = Field(..., description="实体 ID")
    score: float = Field(..., description="RRF 综合得分")
    entity_name: str | None = Field(None, description="实体名称")
    entity_description: str | None = Field(None, description="实体描述")
    semantic_score: float | None = Field(None, description="语义搜索相似度")
    keyword_score: float | None = Field(None, description="关键词搜索得分")

    model_config = {"from_attributes": True}


class SearchResponse(BaseModel):
    """搜索响应。"""

    query: str = Field(..., description="搜索查询文本")
    total: int = Field(..., description="结果总数")
    results: list[SearchHitResponse] = Field(default_factory=list, description="搜索结果列表")
    page: int = Field(1, description="当前页码")
    page_size: int = Field(10, description="每页数量")


# ---------------------------------------------------------------------------
# 依赖注入
# ---------------------------------------------------------------------------


async def get_embedding_client() -> EmbeddingClient:
    """获取 Embedding 客户端实例。

    TODO: 后续改为从应用状态获取单例实例。
    """
    import os

    return EmbeddingClient(
        api_base=os.getenv("EMBEDDING_API_BASE"),
        api_key=os.getenv("EMBEDDING_API_KEY"),
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-v3"),
    )


async def get_searcher(
    session: AsyncSession = Depends(get_db_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
) -> HybridSearcher:
    """获取 HybridSearcher 实例。

    Args:
        session: 数据库会话。
        embedding_client: Embedding 客户端。

    Returns:
        HybridSearcher 实例。
    """
    return HybridSearcher(
        session=session,
        embedding_client=embedding_client,
    )


# ---------------------------------------------------------------------------
# API 接口
# ---------------------------------------------------------------------------

# 支持的实体类型
VALID_ENTITY_TYPES = {"metric", "dimension", "source_table"}


@router.get("", response_model=SearchResponse)
async def hybrid_search(
    q: str = Query(..., min_length=1, max_length=500, description="搜索查询文本"),
    types: str | None = Query(
        None,
        description="按实体类型过滤，逗号分隔，如 metric,dimension",
        alias="types",
    ),
    top_k: int = Query(20, ge=1, le=100, description="返回结果数量"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    searcher: HybridSearcher = Depends(get_searcher),
) -> SearchResponse:
    """混合搜索指标、维度、数据表。

    结合语义搜索（向量余弦相似度）和关键词搜索（全文检索 + ILIKE），
    使用 RRF 算法重排，返回综合排序结果。

    Args:
        q: 搜索查询文本。
        types: 可选，实体类型过滤（逗号分隔）。
        top_k: 返回结果数量。
        page: 页码（从 1 开始）。
        page_size: 每页数量。
        searcher: HybridSearcher 实例（依赖注入）。

    Returns:
        SearchResponse 包含匹配结果列表。
    """
    # 解析 entity types
    entity_types: list[str] | None = None
    if types:
        parsed = [t.strip().lower() for t in types.split(",") if t.strip()]
        invalid = set(parsed) - VALID_ENTITY_TYPES
        if invalid:
            from datapilot_common.exceptions import ValidationError

            raise ValidationError(
                f"不支持的实体类型: {', '.join(invalid)}，"
                f"支持: {', '.join(sorted(VALID_ENTITY_TYPES))}"
            )
        entity_types = parsed

    # 执行搜索（取 top_k 条用于分页）
    hits: list[SearchHit] = await searcher.search(
        query=q,
        entity_types=entity_types,
        top_k=top_k,
    )

    # 分页
    start = (page - 1) * page_size
    end = start + page_size
    page_hits = hits[start:end]

    results = [
        SearchHitResponse(
            entity_type=hit.entity_type,
            entity_id=hit.entity_id,
            score=hit.score,
            entity_name=hit.entity_name,
            entity_description=hit.entity_description,
            semantic_score=hit.semantic_score,
            keyword_score=hit.keyword_score,
        )
        for hit in page_hits
    ]

    return SearchResponse(
        query=q,
        total=len(hits),
        results=results,
        page=page,
        page_size=page_size,
    )
