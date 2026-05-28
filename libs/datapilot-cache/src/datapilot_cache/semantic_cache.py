"""语义缓存。

基于问题相似度匹配缓存（Phase1 使用关键词重叠，后续可升级为向量相似度）。
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from datapilot_cache.models import CacheKey

if TYPE_CHECKING:
    from datapilot_cache.cache import CacheManager

logger = logging.getLogger(__name__)


class SemanticCache:
    """语义缓存。

    通过计算用户问题与已缓存问题的相似度来匹配缓存。
    Phase1 使用 Jaccard 相似度（关键词交集/并集），后续可升级为向量相似度。

    Args:
        cache: 底层缓存管理器实例。
        similarity_threshold: 相似度阈值，默认 0.85。仅当相似度 >= 阈值时视为命中。
    """

    def __init__(
        self,
        cache: CacheManager,
        similarity_threshold: float = 0.85,
    ) -> None:
        self._cache = cache
        self._namespace = "semantic"
        self._threshold = similarity_threshold
        # 用于存储原始问题文本，便于相似度匹配
        # key: CacheKey, value: 原始问题文本
        self._question_store: dict[CacheKey, str] = {}

    def _tokenize(self, text: str) -> set[str]:
        """对文本进行分词。

        使用正则提取中文字符、英文单词和数字作为词元。

        Args:
            text: 输入文本。

        Returns:
            词元集合。
        """
        # 提取中文单个字符、英文单词和数字
        tokens = set(re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9]+", text.lower()))
        return tokens

    def _calculate_similarity(self, question: str, cached_question: str) -> float:
        """计算两个问题的相似度。

        Phase1 使用 Jaccard 相似度（关键词交集/并集）。

        Args:
            question: 用户问题。
            cached_question: 缓存中的问题。

        Returns:
            相似度分数，范围 [0.0, 1.0]。
        """
        tokens_a = self._tokenize(question)
        tokens_b = self._tokenize(cached_question)

        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0

        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union)

    def _make_key(self, question: str, session_id: str = "") -> CacheKey:
        """为问题生成缓存键。

        Args:
            question: 用户问题。
            session_id: 会话标识。

        Returns:
            CacheKey 实例。
        """
        import hashlib

        raw = f"{session_id}:{question}"
        key_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
        return CacheKey(namespace=self._namespace, key=key_hash)

    def get(self, question: str, session_id: str = "") -> Any | None:
        """查找语义相似的缓存。

        遍历当前命名空间下所有缓存的问题，计算相似度，
        返回第一个超过阈值的缓存结果。

        Args:
            question: 用户问题。
            session_id: 会话标识（可选，用于限定会话范围）。

        Returns:
            缓存结果，无匹配返回 None。
        """
        best_match_key: CacheKey | None = None
        best_similarity = 0.0

        for cache_key, cached_question in self._question_store.items():
            # 如果指定了 session_id，则仅匹配同一命名空间下所有条目
            # （Phase1 不区分会话）
            similarity = self._calculate_similarity(question, cached_question)
            if similarity >= self._threshold and similarity > best_similarity:
                best_similarity = similarity
                best_match_key = cache_key

        if best_match_key is not None:
            result = self._cache.get(best_match_key)
            if result is not None:
                logger.info(
                    "语义缓存命中: similarity=%.2f, question='%s'",
                    best_similarity,
                    question,
                )
                return result

        self._cache.get(self._make_key(question, session_id))  # 记录 miss
        logger.debug("语义缓存未命中: question='%s'", question)
        return None

    def set(
        self,
        question: str,
        result: Any,
        ttl: float = 300.0,
        session_id: str = "",
    ) -> None:
        """设置语义缓存。

        将问题和结果一起存入缓存，并记录原始问题文本。

        Args:
            question: 用户问题。
            result: 查询结果。
            ttl: 过期时间（秒），默认 300 秒。
            session_id: 会话标识。
        """
        cache_key = self._make_key(question, session_id)
        self._cache.set(cache_key, result, ttl=ttl)
        self._question_store[cache_key] = question
        logger.debug("语义缓存设置: question='%s'", question)

    def clear(self) -> None:
        """清空语义缓存及其问题存储。"""
        self._cache.clear(namespace=self._namespace)
        self._question_store.clear()
        logger.info("语义缓存已清空")
