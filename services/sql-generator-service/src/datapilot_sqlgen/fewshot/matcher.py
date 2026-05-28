"""Few-shot 示例匹配引擎。

根据用户问题匹配最相关的 Few-shot 示例，支持向量相似度匹配、
领域过滤和难度排序。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from datapilot_prompt.budget import TokenBudgetManager

    from ..generator.models import FewShotExample

logger = structlog.get_logger(__name__)

# 难度优先级：simple > medium > complex（避免过于复杂）
DIFFICULTY_PRIORITY: dict[str, int] = {
    "simple": 0,
    "medium": 1,
    "complex": 2,
}

# 默认 top_k
DEFAULT_TOP_K = 3


class FewShotMatcher:
    """Few-shot 示例匹配器。

    匹配策略：
    1. 领域过滤（可选）
    2. 向量相似度匹配（调用 embedding API）
    3. 难度排序（优先 simple/medium）
    4. Token 预算裁剪

    Args:
        budget_manager: Token 预算管理器。
        embedding_fn: Embedding 生成函数，签名为 async (text: str) -> list[float]。
        similarity_fn: 相似度计算函数，签名为 async (query_vec, candidate_vecs) -> list[float]。
        examples_store_fn: 从存储加载候选示例的函数，签名为
            async (tenant_id: str, domain: str | None) -> list[FewShotExample]。
    """

    def __init__(
        self,
        budget_manager: TokenBudgetManager,
        embedding_fn: object | None = None,
        similarity_fn: object | None = None,
        examples_store_fn: object | None = None,
    ) -> None:
        self._budget_manager = budget_manager
        self._embedding_fn = embedding_fn
        self._similarity_fn = similarity_fn
        self._examples_store_fn = examples_store_fn
        # 热门问题匹配缓存: question_hash -> list[FewShotExample]
        self._cache: dict[str, list[FewShotExample]] = {}

    async def match(
        self,
        question: str,
        tenant_id: str = "",
        domain: str | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[FewShotExample]:
        """匹配最相关的 Few-shot 示例。

        Args:
            question: 用户问题。
            tenant_id: 租户 ID。
            domain: 可选的业务域过滤。
            top_k: 返回的最大示例数量。

        Returns:
            按相似度排序的 Few-shot 列表（已截取 top_k 个）。
        """
        # 检查缓存
        cache_key = self._cache_key(question, domain)
        if cache_key in self._cache:
            logger.debug("Few-shot 命中缓存", cache_key=cache_key)
            return self._cache[cache_key]

        # 从存储加载候选示例
        candidates = await self._load_candidates(tenant_id, domain)
        if not candidates:
            logger.debug("无可用 Few-shot 示例", tenant_id=tenant_id, domain=domain)
            return []

        # 计算向量相似度
        scored = await self._compute_similarity(question, candidates)

        # 按难度优先级和相似度排序
        sorted_examples = self._sort_by_priority(scored)

        # 截取 top_k
        result = sorted_examples[:top_k]

        # 缓存结果
        self._cache[cache_key] = result

        logger.debug(
            "Few-shot 匹配完成",
            candidate_count=len(candidates),
            result_count=len(result),
            domain=domain,
        )

        return result

    async def _load_candidates(
        self,
        tenant_id: str,
        domain: str | None,
    ) -> list[FewShotExample]:
        """从存储加载候选示例。

        Args:
            tenant_id: 租户 ID。
            domain: 业务域过滤。

        Returns:
            候选示例列表。
        """
        if self._examples_store_fn is not None:
            # 调用外部存储函数
            fn = self._examples_store_fn  # type: ignore[assignment]
            candidates = await fn(tenant_id, domain)
            return candidates

        # 没有配置存储函数时返回空列表
        return []

    async def _compute_similarity(
        self,
        question: str,
        candidates: list[FewShotExample],
    ) -> list[FewShotExample]:
        """计算用户问题与候选示例的相似度。

        Args:
            question: 用户问题。
            candidates: 候选示例列表。

        Returns:
            带 similarity_score 的示例列表。
        """
        if self._embedding_fn is None or self._similarity_fn is None:
            # 没有 embedding 函数时，使用简单的文本匹配作为降级策略
            return self._text_fallback_similarity(question, candidates)

        # 使用向量相似度匹配
        try:
            import asyncio

            embedding_fn = self._embedding_fn  # type: ignore[assignment]
            similarity_fn = self._similarity_fn  # type: ignore[assignment]

            query_vec = await embedding_fn(question)
            candidate_texts = [ex.question for ex in candidates]
            candidate_vecs = await asyncio.gather(*[embedding_fn(text) for text in candidate_texts])
            scores = await similarity_fn(query_vec, list(candidate_vecs))

            for ex, score in zip(candidates, scores, strict=False):
                ex.similarity_score = float(score)

            return candidates
        except Exception:
            logger.warning("向量相似度计算失败，降级为文本匹配")
            return self._text_fallback_similarity(question, candidates)

    @staticmethod
    def _text_fallback_similarity(
        question: str,
        candidates: list[FewShotExample],
    ) -> list[FewShotExample]:
        """文本降级匹配：基于关键词重叠率计算相似度。

        Args:
            question: 用户问题。
            candidates: 候选示例列表。

        Returns:
            带 similarity_score 的示例列表。
        """
        # 分词（简单按字符切分）
        question_chars = set(question)
        for ex in candidates:
            candidate_chars = set(ex.question)
            overlap = question_chars & candidate_chars
            if len(question_chars) > 0:
                ex.similarity_score = len(overlap) / len(question_chars)
            else:
                ex.similarity_score = 0.0

        return candidates

    @staticmethod
    def _sort_by_priority(examples: list[FewShotExample]) -> list[FewShotExample]:
        """按难度优先级和相似度排序。

        排序规则：
        1. 优先级：simple > medium > complex
        2. 同难度内按相似度降序
        3. 相似度太低（<0.1）的过滤掉

        Args:
            examples: 候选示例列表。

        Returns:
            排序后的示例列表。
        """
        # 过滤相似度太低的
        filtered = [ex for ex in examples if ex.similarity_score >= 0.1]

        # 排序：先按难度优先级，再按相似度降序
        sorted_list = sorted(
            filtered,
            key=lambda ex: (
                DIFFICULTY_PRIORITY.get(ex.difficulty, 99),
                -ex.similarity_score,
            ),
        )
        return sorted_list

    @staticmethod
    def _cache_key(question: str, domain: str | None) -> str:
        """生成缓存键。

        Args:
            question: 用户问题。
            domain: 业务域。

        Returns:
            缓存键字符串。
        """
        normalized = question.strip().lower()
        if domain:
            return f"{domain}:{normalized}"
        return normalized

    def clear_cache(self) -> None:
        """清空匹配缓存。"""
        self._cache.clear()
