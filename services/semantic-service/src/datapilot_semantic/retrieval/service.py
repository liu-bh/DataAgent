"""向量检索服务。

封装检索层的业务逻辑，包括混合搜索、结果缓存等。
将原本分散在 api/routes/search.py 中的检索逻辑抽取到此处，
实现 Controller-Service 分层。
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from datapilot_semantic.retrieval.cache import CachedSearchResult, SemanticCache
from datapilot_semantic.retrieval.hybrid_search import HybridSearcher, SearchHit

logger = structlog.get_logger(__name__)


class RetrievalService:
    """向量检索服务。

    封装混合搜索（语义 + 关键词）和检索结果缓存逻辑。
    调用方（路由层）不需要了解 HybridSearcher 和 SemanticCache 的细节。

    Args:
        searcher: 混合搜索器实例。
        cache: 语义缓存实例，可选。传入 None 则禁用缓存。
    """

    def __init__(
        self,
        searcher: HybridSearcher,
        cache: SemanticCache | None = None,
    ) -> None:
        """初始化 RetrievalService。

        Args:
            searcher: HybridSearcher 混合搜索器实例。
            cache: 可选的 SemanticCache 语义缓存实例。
        """
        self._searcher = searcher
        self._cache = cache

    async def search(
        self,
        query: str,
        tenant_id: str,
        *,
        entity_types: list[str] | None = None,
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """执行混合搜索（语义 + 关键词）。

        流程:
        1. 检查语义缓存，命中则直接返回。
        2. 未命中时调用 HybridSearcher 执行混合搜索。
        3. 将搜索结果写入缓存供后续复用。

        Args:
            query: 用户查询文本。
            tenant_id: 租户 ID。
            entity_types: 可选的实体类型过滤列表。
            top_k: 返回结果数量上限。

        Returns:
            搜索结果字典列表，每条包含 entity_type、entity_id、score 等字段。
        """
        # 1. 尝试从缓存获取
        cached = await self.get_cached(query, tenant_id)
        if cached is not None:
            logger.debug("retrieval_cache_hit", query=query, tenant_id=tenant_id)
            return cached

        # 2. 执行混合搜索
        hits: list[SearchHit] = await self._searcher.search(
            query=query,
            entity_types=entity_types,
            top_k=top_k,
            tenant_id=tenant_id,
        )

        results = [
            {
                "entity_type": hit.entity_type,
                "entity_id": hit.entity_id,
                "score": hit.score,
                "entity_name": hit.entity_name,
                "entity_description": hit.entity_description,
                "semantic_score": hit.semantic_score,
                "keyword_score": hit.keyword_score,
            }
            for hit in hits
        ]

        # 3. 写入缓存
        if results:
            await self.cache_result(query, tenant_id, results)

        logger.info(
            "retrieval_search_completed",
            query=query,
            tenant_id=tenant_id,
            result_count=len(results),
        )
        return results

    async def cache_result(
        self,
        query: str,
        tenant_id: str,
        result: list[dict[str, Any]],
        ttl: int = 300,
    ) -> None:
        """缓存搜索结果。

        将搜索结果写入语义缓存，设置 TTL。

        Args:
            query: 用户查询文本。
            tenant_id: 租户 ID。
            result: 搜索结果列表。
            ttl: 缓存过期时间（秒），默认 300（5 分钟）。
        """
        if self._cache is None:
            return

        # 将 dict 转为 CachedSearchResult
        cached_results: list[CachedSearchResult] = []
        for item in result:
            cached_results.append(CachedSearchResult(
                entity_type=item.get("entity_type", ""),
                entity_id=item.get("entity_id", ""),
                score=float(item.get("score", 0.0)),
                entity_name=item.get("entity_name"),
                entity_description=item.get("entity_description"),
            ))

        success = await self._cache.set_cached_results(
            f"{tenant_id}:{query}",
            cached_results,
        )

        if success:
            logger.debug(
                "retrieval_cache_set",
                query=query,
                tenant_id=tenant_id,
                result_count=len(cached_results),
                ttl=ttl,
            )

    async def get_cached(
        self,
        query: str,
        tenant_id: str,
    ) -> list[dict[str, Any]] | None:
        """获取缓存的搜索结果。

        Args:
            query: 用户查询文本。
            tenant_id: 租户 ID。

        Returns:
            缓存的搜索结果列表，缓存未命中则返回 None。
        """
        if self._cache is None:
            return None

        cached = await self._cache.get_cached_results(f"{tenant_id}:{query}")
        if cached is None:
            return None

        # 将 CachedSearchResult 转为 dict
        return [
            {
                "entity_type": item.entity_type,
                "entity_id": item.entity_id,
                "score": item.score,
                "entity_name": item.entity_name,
                "entity_description": item.entity_description,
            }
            for item in cached
        ]
