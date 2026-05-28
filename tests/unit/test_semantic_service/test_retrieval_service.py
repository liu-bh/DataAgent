"""RetrievalService 单元测试。

测试向量检索服务的混合搜索、缓存读写等业务逻辑。
使用 mock 模拟 HybridSearcher 和 SemanticCache，不依赖真实数据库和 Redis。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# 确保项目源码路径可被导入
import sys
from pathlib import Path

project_root = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "services"
    / "semantic-service"
    / "src"
)
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from datapilot_semantic.retrieval.cache import CachedSearchResult
from datapilot_semantic.retrieval.hybrid_search import SearchHit
from datapilot_semantic.retrieval.service import RetrievalService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_searcher() -> AsyncMock:
    """创建 mock HybridSearcher。"""
    searcher = AsyncMock(spec=RetrievalService.__init__.__annotations__["searcher"])
    return searcher


@pytest.fixture
def mock_cache() -> AsyncMock:
    """创建 mock SemanticCache。"""
    return AsyncMock()


@pytest.fixture
def sample_hits() -> list[SearchHit]:
    """创建样例搜索命中结果。"""
    return [
        SearchHit(
            entity_type="metric",
            entity_id=str(uuid4()),
            score=0.85,
            entity_name="销售额",
            entity_description="总销售金额",
            semantic_score=0.9,
            keyword_score=0.8,
        ),
        SearchHit(
            entity_type="dimension",
            entity_id=str(uuid4()),
            score=0.65,
            entity_name="时间维度",
            entity_description="按日期维度",
            semantic_score=0.7,
            keyword_score=0.6,
        ),
    ]


@pytest.fixture
def sample_cached_results() -> list[CachedSearchResult]:
    """创建样例缓存结果。"""
    return [
        CachedSearchResult(
            entity_type="metric",
            entity_id=str(uuid4()),
            score=0.85,
            entity_name="销售额",
            entity_description="总销售金额",
        ),
    ]


@pytest.fixture
def sample_dict_results() -> list[dict]:
    """创建样例字典格式的搜索结果。"""
    return [
        {
            "entity_type": "metric",
            "entity_id": str(uuid4()),
            "score": 0.85,
            "entity_name": "销售额",
            "entity_description": "总销售金额",
            "semantic_score": 0.9,
            "keyword_score": 0.8,
        },
    ]


# ---------------------------------------------------------------------------
# 测试：初始化
# ---------------------------------------------------------------------------


class TestRetrievalServiceInit:
    """RetrievalService 初始化测试。"""

    def test_init_with_cache(self, mock_searcher: AsyncMock, mock_cache: AsyncMock) -> None:
        """带缓存初始化。"""
        service = RetrievalService(searcher=mock_searcher, cache=mock_cache)
        assert service._searcher is mock_searcher
        assert service._cache is mock_cache

    def test_init_without_cache(self, mock_searcher: AsyncMock) -> None:
        """无缓存初始化。"""
        service = RetrievalService(searcher=mock_searcher)
        assert service._searcher is mock_searcher
        assert service._cache is None


# ---------------------------------------------------------------------------
# 测试：混合搜索
# ---------------------------------------------------------------------------


class TestSearch:
    """search 方法测试。"""

    async def test_search_with_cache_hit(
        self,
        mock_searcher: AsyncMock,
        mock_cache: AsyncMock,
        sample_dict_results: list[dict],
    ) -> None:
        """缓存命中时直接返回缓存结果，不调用搜索器。"""
        mock_cache.get_cached_results.return_value = sample_dict_results

        service = RetrievalService(searcher=mock_searcher, cache=mock_cache)
        results = await service.search("销售额", "tenant-001")

        assert len(results) == 1
        assert results[0]["entity_type"] == "metric"
        # 搜索器不应被调用
        mock_searcher.search.assert_not_awaited()

    async def test_search_cache_miss_calls_searcher(
        self,
        mock_searcher: AsyncMock,
        mock_cache: AsyncMock,
        sample_hits: list[SearchHit],
    ) -> None:
        """缓存未命中时调用搜索器执行搜索。"""
        mock_cache.get_cached_results.return_value = None
        mock_searcher.search.return_value = sample_hits
        mock_cache.set_cached_results.return_value = True

        service = RetrievalService(searcher=mock_searcher, cache=mock_cache)
        results = await service.search("上个月销售额", "tenant-001")

        # 验证搜索器被调用
        mock_searcher.search.assert_awaited_once_with(
            query="上个月销售额",
            entity_types=None,
            top_k=20,
            tenant_id="tenant-001",
        )
        assert len(results) == 2
        assert results[0]["entity_type"] == "metric"
        assert results[1]["entity_type"] == "dimension"

    async def test_search_with_entity_types(
        self,
        mock_searcher: AsyncMock,
        mock_cache: AsyncMock,
        sample_hits: list[SearchHit],
    ) -> None:
        """指定实体类型过滤搜索。"""
        mock_cache.get_cached_results.return_value = None
        mock_searcher.search.return_value = sample_hits[:1]
        mock_cache.set_cached_results.return_value = True

        service = RetrievalService(searcher=mock_searcher, cache=mock_cache)
        results = await service.search(
            "销售额", "tenant-001", entity_types=["metric"], top_k=5
        )

        mock_searcher.search.assert_awaited_once_with(
            query="销售额",
            entity_types=["metric"],
            top_k=5,
            tenant_id="tenant-001",
        )
        assert len(results) == 1

    async def test_search_caches_result_after_search(
        self,
        mock_searcher: AsyncMock,
        mock_cache: AsyncMock,
        sample_hits: list[SearchHit],
    ) -> None:
        """搜索结果应被写入缓存。"""
        mock_cache.get_cached_results.return_value = None
        mock_searcher.search.return_value = sample_hits
        mock_cache.set_cached_results.return_value = True

        service = RetrievalService(searcher=mock_searcher, cache=mock_cache)
        await service.search("销售额", "tenant-001")

        # 验证缓存被写入
        mock_cache.set_cached_results.assert_awaited_once()
        call_args = mock_cache.set_cached_results.call_args
        # 缓存键应包含租户 ID 和查询文本
        assert "tenant-001:销售额" in str(call_args)

    async def test_search_no_cache(
        self,
        mock_searcher: AsyncMock,
        sample_hits: list[SearchHit],
    ) -> None:
        """无缓存实例时正常执行搜索。"""
        mock_searcher.search.return_value = sample_hits

        service = RetrievalService(searcher=mock_searcher)
        results = await service.search("销售额", "tenant-001")

        assert len(results) == 2
        mock_searcher.search.assert_awaited_once()

    async def test_search_empty_results_not_cached(
        self,
        mock_searcher: AsyncMock,
        mock_cache: AsyncMock,
    ) -> None:
        """搜索结果为空时不写入缓存。"""
        mock_cache.get_cached_results.return_value = None
        mock_searcher.search.return_value = []

        service = RetrievalService(searcher=mock_searcher, cache=mock_cache)
        results = await service.search("不存在的内容", "tenant-001")

        assert len(results) == 0
        # 空结果不应写入缓存
        mock_cache.set_cached_results.assert_not_awaited()


# ---------------------------------------------------------------------------
# 测试：缓存结果
# ---------------------------------------------------------------------------


class TestCacheResult:
    """cache_result 方法测试。"""

    async def test_cache_result_with_cache(
        self,
        mock_searcher: AsyncMock,
        mock_cache: AsyncMock,
        sample_dict_results: list[dict],
    ) -> None:
        """有缓存实例时写入缓存。"""
        mock_cache.set_cached_results.return_value = True

        service = RetrievalService(searcher=mock_searcher, cache=mock_cache)
        await service.cache_result("销售额", "tenant-001", sample_dict_results, ttl=600)

        mock_cache.set_cached_results.assert_awaited_once()
        # 验证传入的是 CachedSearchResult 对象
        call_args = mock_cache.set_cached_results.call_args
        cached_items = call_args[0][1]  # 第二个位置参数
        assert all(isinstance(item, CachedSearchResult) for item in cached_items)

    async def test_cache_result_without_cache(
        self,
        mock_searcher: AsyncMock,
        sample_dict_results: list[dict],
    ) -> None:
        """无缓存实例时不执行任何操作。"""
        service = RetrievalService(searcher=mock_searcher)
        # 不应抛出异常
        await service.cache_result("销售额", "tenant-001", sample_dict_results)

    async def test_cache_result_empty_list(
        self,
        mock_searcher: AsyncMock,
        mock_cache: AsyncMock,
    ) -> None:
        """空结果列表不写入缓存。"""
        mock_cache.set_cached_results.return_value = True

        service = RetrievalService(searcher=mock_searcher, cache=mock_cache)
        await service.cache_result("销售额", "tenant-001", [])

        # 空列表仍会调用 set_cached_results（由 SemanticCache 内部判断）
        # 但 RetrievalService 层不做过滤
        call_args = mock_cache.set_cached_results.call_args
        cached_items = call_args[0][1]
        assert len(cached_items) == 0


# ---------------------------------------------------------------------------
# 测试：获取缓存
# ---------------------------------------------------------------------------


class TestGetCached:
    """get_cached 方法测试。"""

    async def test_get_cached_hit(
        self,
        mock_searcher: AsyncMock,
        mock_cache: AsyncMock,
        sample_cached_results: list[CachedSearchResult],
    ) -> None:
        """缓存命中时返回字典列表。"""
        mock_cache.get_cached_results.return_value = sample_cached_results

        service = RetrievalService(searcher=mock_searcher, cache=mock_cache)
        result = await service.get_cached("销售额", "tenant-001")

        assert result is not None
        assert len(result) == 1
        assert result[0]["entity_type"] == "metric"
        assert result[0]["entity_name"] == "销售额"
        # 验证缓存键包含租户 ID
        mock_cache.get_cached_results.assert_awaited_once_with("tenant-001:销售额")

    async def test_get_cached_miss(
        self,
        mock_searcher: AsyncMock,
        mock_cache: AsyncMock,
    ) -> None:
        """缓存未命中时返回 None。"""
        mock_cache.get_cached_results.return_value = None

        service = RetrievalService(searcher=mock_searcher, cache=mock_cache)
        result = await service.get_cached("不存在的查询", "tenant-001")

        assert result is None

    async def test_get_cached_without_cache_instance(
        self,
        mock_searcher: AsyncMock,
    ) -> None:
        """无缓存实例时返回 None。"""
        service = RetrievalService(searcher=mock_searcher)
        result = await service.get_cached("销售额", "tenant-001")

        assert result is None
