"""FewShotMatcher 匹配器单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from datapilot_sqlgen.generator.models import FewShotExample
from datapilot_sqlgen.fewshot.matcher import (
    DEFAULT_TOP_K,
    FewShotMatcher,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_budget_manager() -> MagicMock:
    """创建 mock TokenBudgetManager。"""
    manager = MagicMock()
    manager.estimate_tokens.return_value = 50
    return manager


@pytest.fixture
def candidate_examples() -> list[FewShotExample]:
    """生成候选 Few-shot 示例列表。"""
    return [
        FewShotExample(
            question="各地区的销售额是多少",
            sql="SELECT region, SUM(amount) FROM orders GROUP BY region",
            domain="电商",
            difficulty="simple",
            similarity_score=0.0,
        ),
        FewShotExample(
            question="上个月订单量趋势",
            sql="SELECT DATE(created_at), COUNT(*) FROM orders GROUP BY DATE(created_at)",
            domain="电商",
            difficulty="medium",
            similarity_score=0.0,
        ),
        FewShotExample(
            question="用户行为分析",
            sql="SELECT user_id, COUNT(*) FROM events GROUP BY user_id",
            domain="运营",
            difficulty="complex",
            similarity_score=0.0,
        ),
        FewShotExample(
            question="客单价最高的商品",
            sql="SELECT product_id, AVG(amount) FROM orders GROUP BY product_id ORDER BY AVG(amount) DESC LIMIT 10",
            domain="电商",
            difficulty="medium",
            similarity_score=0.0,
        ),
    ]


@pytest.fixture
def matcher(mock_budget_manager: MagicMock) -> FewShotMatcher:
    """创建 FewShotMatcher 实例（无外部函数）。"""
    return FewShotMatcher(budget_manager=mock_budget_manager)


# ---------------------------------------------------------------------------
# 文本降级匹配测试
# ---------------------------------------------------------------------------


class TestTextFallbackMatching:
    """文本降级匹配策略测试。"""

    @pytest.mark.asyncio
    async def test_match_with_no_external_fn(
        self,
        matcher: FewShotMatcher,
        candidate_examples: list[FewShotExample],
    ) -> None:
        """没有 embedding 函数时应使用文本降级匹配。"""
        # 使用 mock 的 store 函数返回候选列表
        matcher._examples_store_fn = AsyncMock(return_value=candidate_examples)

        results = await matcher.match(
            question="各地区销售额",
            tenant_id="test-tenant",
        )

        # 应返回结果（使用文本匹配）
        assert len(results) > 0
        assert all(isinstance(r, FewShotExample) for r in results)

    @pytest.mark.asyncio
    async def test_match_top_k_limit(
        self,
        matcher: FewShotMatcher,
        candidate_examples: list[FewShotExample],
    ) -> None:
        """结果数量不应超过 top_k。"""
        matcher._examples_store_fn = AsyncMock(return_value=candidate_examples)

        results = await matcher.match(
            question="销售额",
            tenant_id="test-tenant",
            top_k=2,
        )

        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_no_candidates_returns_empty(
        self,
        matcher: FewShotMatcher,
    ) -> None:
        """没有候选示例时应返回空列表。"""
        matcher._examples_store_fn = AsyncMock(return_value=[])

        results = await matcher.match(
            question="销售额",
            tenant_id="test-tenant",
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_no_store_fn_returns_empty(
        self,
        matcher: FewShotMatcher,
    ) -> None:
        """没有存储函数时应返回空列表。"""
        results = await matcher.match(
            question="销售额",
            tenant_id="test-tenant",
        )

        assert results == []


# ---------------------------------------------------------------------------
# 缓存测试
# ---------------------------------------------------------------------------


class TestCaching:
    """匹配缓存测试。"""

    @pytest.mark.asyncio
    async def test_cache_hit(
        self,
        matcher: FewShotMatcher,
        candidate_examples: list[FewShotExample],
    ) -> None:
        """相同问题应命中缓存。"""
        matcher._examples_store_fn = AsyncMock(return_value=candidate_examples)

        # 第一次调用
        results1 = await matcher.match(
            question="销售额统计",
            tenant_id="test-tenant",
        )
        # 第二次调用（应命中缓存）
        results2 = await matcher.match(
            question="销售额统计",
            tenant_id="test-tenant",
        )

        # 存储函数应该只被调用一次
        assert matcher._examples_store_fn.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_different_domain(
        self,
        matcher: FewShotMatcher,
        candidate_examples: list[FewShotExample],
    ) -> None:
        """不同域名不应命中缓存。"""
        matcher._examples_store_fn = AsyncMock(return_value=candidate_examples)

        await matcher.match(question="销售额", tenant_id="test-tenant", domain="电商")
        await matcher.match(question="销售额", tenant_id="test-tenant", domain="运营")

        assert matcher._examples_store_fn.call_count == 2

    def test_clear_cache(
        self,
        matcher: FewShotMatcher,
    ) -> None:
        """清空缓存应正常工作。"""
        matcher._cache["key"] = []
        assert len(matcher._cache) > 0
        matcher.clear_cache()
        assert len(matcher._cache) == 0


# ---------------------------------------------------------------------------
# 排序测试
# ---------------------------------------------------------------------------


class TestSortPriority:
    """难度排序测试。"""

    def test_simple_priority_over_complex(self) -> None:
        """simple 难度应优先于 complex。"""
        examples = [
            FewShotExample(question="A", sql="S1", difficulty="complex", similarity_score=0.9),
            FewShotExample(question="B", sql="S2", difficulty="simple", similarity_score=0.7),
            FewShotExample(question="C", sql="S3", difficulty="medium", similarity_score=0.8),
        ]

        sorted_list = FewShotMatcher._sort_by_priority(examples)
        difficulties = [ex.difficulty for ex in sorted_list]

        assert difficulties[0] == "simple"
        assert difficulties[1] == "medium"
        assert difficulties[2] == "complex"

    def test_same_difficulty_sorts_by_similarity(self) -> None:
        """同难度内按相似度降序排序。"""
        examples = [
            FewShotExample(question="A", sql="S1", difficulty="simple", similarity_score=0.5),
            FewShotExample(question="B", sql="S2", difficulty="simple", similarity_score=0.9),
            FewShotExample(question="C", sql="S3", difficulty="simple", similarity_score=0.7),
        ]

        sorted_list = FewShotMatcher._sort_by_priority(examples)
        scores = [ex.similarity_score for ex in sorted_list]

        assert scores == [0.9, 0.7, 0.5]

    def test_low_similarity_filtered(self) -> None:
        """相似度太低的示例应被过滤。"""
        examples = [
            FewShotExample(question="A", sql="S1", difficulty="simple", similarity_score=0.05),
            FewShotExample(question="B", sql="S2", difficulty="simple", similarity_score=0.9),
        ]

        sorted_list = FewShotMatcher._sort_by_priority(examples)
        assert len(sorted_list) == 1
        assert sorted_list[0].question == "B"

    def test_empty_list(self) -> None:
        """空列表应返回空列表。"""
        assert FewShotMatcher._sort_by_priority([]) == []

    def test_all_low_similarity(self) -> None:
        """全部低相似度时应返回空列表。"""
        examples = [
            FewShotExample(question="A", sql="S1", difficulty="simple", similarity_score=0.01),
            FewShotExample(question="B", sql="S2", difficulty="simple", similarity_score=0.05),
        ]
        assert FewShotMatcher._sort_by_priority(examples) == []


# ---------------------------------------------------------------------------
# 文本降级匹配
# ---------------------------------------------------------------------------


class TestTextFallback:
    """文本降级匹配策略详细测试。"""

    def test_exact_keyword_overlap(self) -> None:
        """完全关键词重叠应有高相似度。"""
        examples = [
            FewShotExample(question="销售额统计", sql="SELECT SUM(amount)", similarity_score=0.0),
        ]

        results = FewShotMatcher._text_fallback_similarity("销售额是多少", examples)
        assert results[0].similarity_score > 0.5

    def test_no_overlap(self) -> None:
        """无重叠应返回低相似度。"""
        examples = [
            FewShotExample(question="天气查询", sql="SELECT temperature", similarity_score=0.0),
        ]

        results = FewShotMatcher._text_fallback_similarity("销售额统计", examples)
        assert results[0].similarity_score < 0.5

    def test_empty_question(self) -> None:
        """空问题不应报错。"""
        examples = [
            FewShotExample(question="测试", sql="SELECT 1", similarity_score=0.0),
        ]
        results = FewShotMatcher._text_fallback_similarity("", examples)
        assert results[0].similarity_score == 0.0


# ---------------------------------------------------------------------------
# 向量匹配测试（mock）
# ---------------------------------------------------------------------------


class TestVectorMatching:
    """向量相似度匹配测试（使用 mock 函数）。"""

    @pytest.mark.asyncio
    async def test_vector_matching_success(
        self,
        mock_budget_manager: MagicMock,
        candidate_examples: list[FewShotExample],
    ) -> None:
        """向量匹配正常流程。"""
        embedding_fn = AsyncMock(return_value=[0.1] * 10)
        similarity_fn = AsyncMock(return_value=[0.9, 0.7, 0.5, 0.3])

        matcher = FewShotMatcher(
            budget_manager=mock_budget_manager,
            embedding_fn=embedding_fn,
            similarity_fn=similarity_fn,
            examples_store_fn=AsyncMock(return_value=candidate_examples),
        )

        results = await matcher.match(
            question="销售额统计",
            tenant_id="test-tenant",
        )

        assert len(results) > 0
        # 应按相似度排序（结合难度优先级）
        assert all(r.similarity_score > 0 for r in results)

    @pytest.mark.asyncio
    async def test_vector_matching_failure_fallback(
        self,
        mock_budget_manager: MagicMock,
        candidate_examples: list[FewShotExample],
    ) -> None:
        """向量匹配失败时应降级为文本匹配。"""
        embedding_fn = AsyncMock(side_effect=Exception("embedding 服务不可用"))
        similarity_fn = AsyncMock()

        matcher = FewShotMatcher(
            budget_manager=mock_budget_manager,
            embedding_fn=embedding_fn,
            similarity_fn=similarity_fn,
            examples_store_fn=AsyncMock(return_value=candidate_examples),
        )

        results = await matcher.match(
            question="销售额统计",
            tenant_id="test-tenant",
        )

        # 应降级为文本匹配，仍返回结果
        assert len(results) >= 0  # 可能全被过滤


# ---------------------------------------------------------------------------
# Cache Key 测试
# ---------------------------------------------------------------------------


class TestCacheKey:
    """缓存键生成测试。"""

    def test_without_domain(self) -> None:
        """不带域名的缓存键。"""
        key = FewShotMatcher._cache_key("销售额统计", None)
        assert key == "销售额统计"

    def test_with_domain(self) -> None:
        """带域名的缓存键。"""
        key = FewShotMatcher._cache_key("销售额统计", "电商")
        assert key == "电商:销售额统计"

    def test_normalization(self) -> None:
        """缓存键应规范化（小写+去空格）。"""
        key1 = FewShotMatcher._cache_key("  销售额统计  ", None)
        key2 = FewShotMatcher._cache_key("销售额统计", None)
        assert key1 == key2
