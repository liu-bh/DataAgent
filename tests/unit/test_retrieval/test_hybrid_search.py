"""HybridSearcher 单元测试。

测试内容:
- RRF 重排算法
- 语义搜索和关键词搜索合并
- 分词工具函数
- SearchHit 结果排序
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 分词测试
# ---------------------------------------------------------------------------


class TestTokenizeForSearch:
    """_tokenize_for_search 分词测试。"""

    def test_simple_query(self) -> None:
        """测试简单英文查询分词。"""
        from datapilot_semantic.retrieval.hybrid_search import _tokenize_for_search

        tokens = _tokenize_for_search("sales revenue")
        assert "sales" in tokens
        assert "revenue" in tokens

    def test_chinese_query(self) -> None:
        """测试中文查询（simple 配置不做中文分词）。"""
        from datapilot_semantic.retrieval.hybrid_search import _tokenize_for_search

        tokens = _tokenize_for_search("销售额")
        # 中文 token 被 isascii() 过滤（to_tsquery 不支持中文）
        assert len(tokens) == 0

    def test_empty_query(self) -> None:
        """测试空查询。"""
        from datapilot_semantic.retrieval.hybrid_search import _tokenize_for_search

        tokens = _tokenize_for_search("")
        assert tokens == []

    def test_single_char_filtered(self) -> None:
        """测试单字符被过滤。"""
        from datapilot_semantic.retrieval.hybrid_search import _tokenize_for_search

        tokens = _tokenize_for_search("a b c")
        assert tokens == []

    def test_punctuation_split(self) -> None:
        """测试标点分词。"""
        from datapilot_semantic.retrieval.hybrid_search import _tokenize_for_search

        tokens = _tokenize_for_search("hello,world!test")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens

    def test_mixed_query(self) -> None:
        """测试中英文混合查询。"""
        from datapilot_semantic.retrieval.hybrid_search import _tokenize_for_search

        tokens = _tokenize_for_search("GMV 销售额")
        # "gmv" 是 ASCII 且长度 3 >= 2，保留
        # "销售额" 被 isascii() 过滤
        assert len(tokens) == 1
        assert "gmv" in tokens


# ---------------------------------------------------------------------------
# RRF 重排测试
# ---------------------------------------------------------------------------


class TestRRFFusion:
    """RRF 重排算法测试。"""

    def test_rrf_both_sources(self) -> None:
        """测试语义搜索和关键词搜索都有结果时的 RRF 合并。"""
        from datapilot_semantic.retrieval.hybrid_search import (
            HybridSearcher,
            _RankedItem,
        )

        sem_results = {
            "metric:id1": _RankedItem(
                entity_type="metric",
                entity_id="id1",
                name="GMV",
                semantic_rank=1,
                semantic_similarity=0.95,
            ),
            "metric:id2": _RankedItem(
                entity_type="metric",
                entity_id="id2",
                name="订单量",
                semantic_rank=2,
                semantic_similarity=0.85,
            ),
            "dimension:id3": _RankedItem(
                entity_type="dimension",
                entity_id="id3",
                name="地区",
                semantic_rank=3,
                semantic_similarity=0.75,
            ),
        }

        kw_results = {
            "metric:id2": _RankedItem(
                entity_type="metric",
                entity_id="id2",
                name="订单量",
                keyword_rank=1,
            ),
            "dimension:id3": _RankedItem(
                entity_type="dimension",
                entity_id="id3",
                name="地区",
                keyword_rank=2,
            ),
            "metric:id4": _RankedItem(
                entity_type="metric",
                entity_id="id4",
                name="退货率",
                keyword_rank=3,
            ),
        }

        hits = HybridSearcher._rrf_fusion(sem_results, kw_results, k=60)

        # 应该有 4 个唯一结果
        assert len(hits) == 4

        # 按 score 降序排列
        scores = [h.score for h in hits]
        assert scores == sorted(scores, reverse=True)

        # id2 在两路搜索中都出现，score 应该更高
        id2_hit = next(h for h in hits if h.entity_id == "id2")
        id4_hit = next(h for h in hits if h.entity_id == "id4")
        assert id2_hit.score > id4_hit.score

    def test_rrf_semantic_only(self) -> None:
        """测试只有语义搜索结果时的 RRF。"""
        from datapilot_semantic.retrieval.hybrid_search import (
            HybridSearcher,
            _RankedItem,
        )

        sem_results = {
            "metric:id1": _RankedItem(
                entity_type="metric",
                entity_id="id1",
                name="GMV",
                semantic_rank=1,
                semantic_similarity=0.95,
            ),
        }

        hits = HybridSearcher._rrf_fusion(sem_results, {}, k=60)

        assert len(hits) == 1
        assert hits[0].entity_id == "id1"
        # 只有语义搜索的 RRF score = 1/(60+1) ≈ 0.01639
        expected_score = 1.0 / (60 + 1)
        assert abs(hits[0].score - expected_score) < 1e-6

    def test_rrf_keyword_only(self) -> None:
        """测试只有关键词搜索结果时的 RRF。"""
        from datapilot_semantic.retrieval.hybrid_search import (
            HybridSearcher,
            _RankedItem,
        )

        kw_results = {
            "metric:id1": _RankedItem(
                entity_type="metric",
                entity_id="id1",
                name="GMV",
                keyword_rank=2,
            ),
        }

        hits = HybridSearcher._rrf_fusion({}, kw_results, k=60)

        assert len(hits) == 1
        expected_score = 1.0 / (60 + 2)
        assert abs(hits[0].score - expected_score) < 1e-6

    def test_rrf_both_ranks_boost(self) -> None:
        """测试双路命中排名提升效应。"""
        from datapilot_semantic.retrieval.hybrid_search import (
            HybridSearcher,
            _RankedItem,
        )

        # id1 在两路搜索中排名第 1
        sem_results = {
            "metric:id1": _RankedItem(
                entity_type="metric",
                entity_id="id1",
                semantic_rank=1,
            ),
        }
        kw_results = {
            "metric:id1": _RankedItem(
                entity_type="metric",
                entity_id="id1",
                keyword_rank=1,
            ),
        }

        hits = HybridSearcher._rrf_fusion(sem_results, kw_results, k=60)

        # 双路第 1 名: score = 1/(60+1) + 1/(60+1) = 2/61
        expected = 2.0 / 61
        assert abs(hits[0].score - expected) < 1e-6

    def test_rrf_empty_results(self) -> None:
        """测试两路搜索都无结果。"""
        from datapilot_semantic.retrieval.hybrid_search import HybridSearcher

        hits = HybridSearcher._rrf_fusion({}, {}, k=60)
        assert hits == []

    def test_rrf_custom_k(self) -> None:
        """测试自定义 RRF k 值。"""
        from datapilot_semantic.retrieval.hybrid_search import (
            HybridSearcher,
            _RankedItem,
        )

        sem_results = {
            "metric:id1": _RankedItem(
                entity_type="metric",
                entity_id="id1",
                semantic_rank=1,
            ),
        }

        # k=100 时 score = 1/101
        hits = HybridSearcher._rrf_fusion(sem_results, {}, k=100)
        assert abs(hits[0].score - 1.0 / 101) < 1e-6


# ---------------------------------------------------------------------------
# HybridSearcher 集成测试
# ---------------------------------------------------------------------------


class TestHybridSearcher:
    """HybridSearcher 混合搜索测试。"""

    @pytest.mark.asyncio
    async def test_search_with_mock(self) -> None:
        """测试完整搜索流程（mock 所有依赖）。"""
        session = MagicMock()
        embedding_client = MagicMock()
        embedding_client.embed_text = AsyncMock(return_value=[0.1] * 1536)

        from datapilot_semantic.retrieval.hybrid_search import HybridSearcher

        # Mock VectorStore.search 返回结果
        from datapilot_semantic.retrieval.vector_store import VectorSearchHit

        mock_hits = [
            VectorSearchHit(
                entity_type="metric",
                entity_id=str(uuid.uuid4()),
                name="GMV",
                description="商品交易总额",
                similarity=0.95,
                distance=0.05,
            ),
        ]

        searcher = HybridSearcher(session, embedding_client)

        # Mock 语义搜索
        with patch.object(
            searcher._vector_store,
            "search",
            new_callable=AsyncMock,
            return_value=mock_hits,
        ):
            # Mock 关键词搜索
            with patch.object(
                searcher,
                "_keyword_search",
                new_callable=AsyncMock,
                return_value={},
            ):
                results = await searcher.search(
                    query="销售额",
                    entity_types=["metric"],
                    top_k=10,
                )

        assert len(results) > 0
        assert results[0].entity_type == "metric"
        assert results[0].entity_name == "GMV"

    @pytest.mark.asyncio
    async def test_search_fallback_to_keyword(self) -> None:
        """测试向量化失败时回退到纯关键词搜索。"""
        session = MagicMock()
        embedding_client = MagicMock()
        embedding_client.embed_text = AsyncMock(
            side_effect=Exception("API unavailable")
        )

        from datapilot_semantic.retrieval.hybrid_search import (
            HybridSearcher,
            _RankedItem,
        )

        searcher = HybridSearcher(session, embedding_client)

        kw_results = {
            "metric:id1": _RankedItem(
                entity_type="metric",
                entity_id="id1",
                name="销售额",
                keyword_rank=1,
            ),
        }

        with patch.object(
            searcher,
            "_keyword_search",
            new_callable=AsyncMock,
            return_value=kw_results,
        ):
            results = await searcher.search(query="销售额")

        assert len(results) == 1
        assert results[0].entity_name == "销售额"

    @pytest.mark.asyncio
    async def test_search_default_entity_types(self) -> None:
        """测试默认搜索所有实体类型。"""
        session = MagicMock()
        embedding_client = MagicMock()
        embedding_client.embed_text = AsyncMock(return_value=[0.1] * 1536)

        from datapilot_semantic.retrieval.hybrid_search import HybridSearcher

        searcher = HybridSearcher(session, embedding_client)

        with patch.object(
            searcher,
            "_semantic_search",
            new_callable=AsyncMock,
            return_value={},
        ) as mock_sem:
            with patch.object(
                searcher,
                "_keyword_search",
                new_callable=AsyncMock,
                return_value={},
            ) as mock_kw:
                await searcher.search(query="test")

                # 验证传入了全部三种实体类型
                call_args = mock_sem.call_args
                entity_types = call_args.kwargs["entity_types"]
                assert "metric" in entity_types
                assert "dimension" in entity_types
                assert "source_table" in entity_types


# ---------------------------------------------------------------------------
# SearchHit 数据类测试
# ---------------------------------------------------------------------------


class TestSearchHit:
    """SearchHit 数据类测试。"""

    def test_creation(self) -> None:
        """测试创建 SearchHit。"""
        from datapilot_semantic.retrieval.hybrid_search import SearchHit

        hit = SearchHit(
            entity_type="metric",
            entity_id=str(uuid.uuid4()),
            score=0.032,
            entity_name="GMV",
            entity_description="商品交易总额",
            semantic_score=0.95,
            keyword_score=0.016,
        )

        assert hit.entity_type == "metric"
        assert hit.score == 0.032
        assert hit.semantic_score == 0.95
        assert hit.keyword_score == 0.016

    def test_optional_fields_default(self) -> None:
        """测试可选字段默认为 None。"""
        from datapilot_semantic.retrieval.hybrid_search import SearchHit

        hit = SearchHit(
            entity_type="dimension",
            entity_id="id1",
            score=0.01,
        )

        assert hit.entity_name is None
        assert hit.entity_description is None
        assert hit.semantic_score is None
        assert hit.keyword_score is None
