"""SemanticCache 单元测试。

测试内容:
- 缓存键生成（query → MD5 hash）
- 序列化 / 反序列化
- get_cached_results（缓存命中/未命中）
- set_cached_results（写入缓存）
- invalidate（缓存失效）
- clear_all（清除所有缓存）
- Redis 异常不影响主流程
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 缓存键生成测试
# ---------------------------------------------------------------------------


class TestQueryToKey:
    """_query_to_key 缓存键生成测试。"""

    def test_basic_query(self) -> None:
        """测试基本查询的键生成。"""
        from datapilot_semantic.retrieval.cache import SemanticCache

        key = SemanticCache._query_to_key("销售额")
        assert key.startswith("datapilot:semantic_search:")
        assert len(key) == len("datapilot:semantic_search:") + 32  # MD5 = 32 hex chars

    def test_query_normalization(self) -> None:
        """测试查询文本归一化（小写 + 去空格）。"""
        from datapilot_semantic.retrieval.cache import SemanticCache

        key1 = SemanticCache._query_to_key(" 销售额 ")
        key2 = SemanticCache._query_to_key("销售额")
        assert key1 == key2

    def test_case_insensitive(self) -> None:
        """测试大小写不敏感。"""
        from datapilot_semantic.retrieval.cache import SemanticCache

        key1 = SemanticCache._query_to_key("Sales Revenue")
        key2 = SemanticCache._query_to_key("sales revenue")
        assert key1 == key2

    def test_different_queries_different_keys(self) -> None:
        """测试不同查询产生不同键。"""
        from datapilot_semantic.retrieval.cache import SemanticCache

        key1 = SemanticCache._query_to_key("销售额")
        key2 = SemanticCache._query_to_key("订单量")
        assert key1 != key2

    def test_custom_prefix(self) -> None:
        """测试自定义前缀。"""
        from datapilot_semantic.retrieval.cache import SemanticCache

        key = SemanticCache._query_to_key("test", prefix="custom:")
        assert key.startswith("custom:")


# ---------------------------------------------------------------------------
# 序列化 / 反序列化测试
# ---------------------------------------------------------------------------


class TestSerialization:
    """序列化与反序列化测试。"""

    def test_serialize_deserialize_roundtrip(self) -> None:
        """测试序列化 → 反序列化往返。"""
        from datapilot_semantic.retrieval.cache import SemanticCache, CachedSearchResult

        results = [
            CachedSearchResult(
                entity_type="metric",
                entity_id="id-1",
                score=0.95,
                entity_name="GMV",
                entity_description="商品交易总额",
            ),
            CachedSearchResult(
                entity_type="dimension",
                entity_id="id-2",
                score=0.85,
                entity_name="地区",
                entity_description=None,
            ),
        ]

        serialized = SemanticCache._serialize_results(results)
        deserialized = SemanticCache._deserialize_results(serialized)

        assert len(deserialized) == 2
        assert deserialized[0].entity_type == "metric"
        assert deserialized[0].entity_name == "GMV"
        assert deserialized[0].score == 0.95
        assert deserialized[1].entity_type == "dimension"
        assert deserialized[1].entity_description is None

    def test_serialize_empty_list(self) -> None:
        """测试空列表序列化。"""
        from datapilot_semantic.retrieval.cache import SemanticCache

        serialized = SemanticCache._serialize_results([])
        data = json.loads(serialized)
        assert data == []

    def test_deserialize_invalid_json(self) -> None:
        """测试无效 JSON 反序列化返回空列表。"""
        from datapilot_semantic.retrieval.cache import SemanticCache

        result = SemanticCache._deserialize_results("not json")
        assert result == []

    def test_deserialize_non_list(self) -> None:
        """测试非列表 JSON 反序列化返回空列表。"""
        from datapilot_semantic.retrieval.cache import SemanticCache

        result = SemanticCache._deserialize_results('{"key": "value"}')
        assert result == []

    def test_deserialize_malformed_items(self) -> None:
        """测试列表中包含畸形项时跳过。"""
        from datapilot_semantic.retrieval.cache import SemanticCache

        raw = json.dumps([
            {"entity_type": "metric", "entity_id": "id1", "score": 0.9},
            "not a dict",
            {"entity_type": "dimension"},  # 缺少 entity_id
        ])
        result = SemanticCache._deserialize_results(raw)
        assert len(result) == 2  # 有效 1 个 + 缺少字段的 1 个

    def test_serialize_chinese_content(self) -> None:
        """测试中文内容序列化。"""
        from datapilot_semantic.retrieval.cache import SemanticCache, CachedSearchResult

        results = [
            CachedSearchResult(
                entity_type="metric",
                entity_id="id-1",
                score=0.95,
                entity_name="销售额",
                entity_description="所有订单金额总和",
            ),
        ]

        serialized = SemanticCache._serialize_results(results)
        assert "销售额" in serialized
        assert "所有订单金额总和" in serialized


# ---------------------------------------------------------------------------
# 缓存操作测试（mock Redis）
# ---------------------------------------------------------------------------


class TestSemanticCacheOperations:
    """SemanticCache 缓存操作测试。"""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """创建 mock Redis 客户端。"""
        return AsyncMock()

    def _make_cache(self) -> "SemanticCache":
        """创建测试用 SemanticCache。"""
        from datapilot_semantic.retrieval.cache import SemanticCache

        return SemanticCache(redis_url="redis://localhost:6379/0", ttl=60)

    @pytest.mark.asyncio
    async def test_cache_miss(self) -> None:
        """测试缓存未命中。"""
        cache = self._make_cache()

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch.object(cache, "_get_redis", return_value=mock_redis):
            result = await cache.get_cached_results("销售额")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit(self) -> None:
        """测试缓存命中。"""
        cache = self._make_cache()

        from datapilot_semantic.retrieval.cache import SemanticCache, CachedSearchResult

        cached = [
            CachedSearchResult(
                entity_type="metric",
                entity_id="id-1",
                score=0.95,
                entity_name="GMV",
            ),
        ]
        serialized = SemanticCache._serialize_results(cached)

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=serialized)

        with patch.object(cache, "_get_redis", return_value=mock_redis):
            result = await cache.get_cached_results("销售额")

        assert result is not None
        assert len(result) == 1
        assert result[0].entity_name == "GMV"

    @pytest.mark.asyncio
    async def test_set_cached_results(self) -> None:
        """测试写入缓存。"""
        cache = self._make_cache()

        from datapilot_semantic.retrieval.cache import CachedSearchResult

        results = [
            CachedSearchResult(
                entity_type="metric",
                entity_id="id-1",
                score=0.95,
                entity_name="GMV",
            ),
        ]

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)

        with patch.object(cache, "_get_redis", return_value=mock_redis):
            success = await cache.set_cached_results("销售额", results)

        assert success is True
        mock_redis.set.assert_called_once()

        # 验证 TTL 参数
        call_args = mock_redis.set.call_args
        assert call_args.kwargs.get("ex") == 60

    @pytest.mark.asyncio
    async def test_set_empty_results_returns_false(self) -> None:
        """测试空结果不缓存。"""
        cache = self._make_cache()

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()

        with patch.object(cache, "_get_redis", return_value=mock_redis):
            success = await cache.set_cached_results("销售额", [])

        assert success is False
        mock_redis.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalidate(self) -> None:
        """测试缓存失效。"""
        cache = self._make_cache()

        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=True)

        with patch.object(cache, "_get_redis", return_value=mock_redis):
            success = await cache.invalidate("销售额")

        assert success is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_all(self) -> None:
        """测试清除所有缓存。"""
        cache = self._make_cache()

        # mock scan_iter 返回多个键
        async def mock_scan_iter(*args, **kwargs):
            yield "datapilot:semantic_search:aaa"
            yield "datapilot:semantic_search:bbb"
            yield "datapilot:semantic_search:ccc"

        mock_redis = AsyncMock()
        mock_redis.scan_iter = mock_scan_iter
        mock_redis.delete = AsyncMock(return_value=True)

        with patch.object(cache, "_get_redis", return_value=mock_redis):
            success = await cache.clear_all()

        assert success is True
        assert mock_redis.delete.call_count == 3


# ---------------------------------------------------------------------------
# 异常处理测试
# ---------------------------------------------------------------------------


class TestSemanticCacheErrorHandling:
    """缓存异常处理测试（Redis 异常不影响主流程）。"""

    def _make_cache(self) -> "SemanticCache":
        """创建测试用 SemanticCache。"""
        from datapilot_semantic.retrieval.cache import SemanticCache

        return SemanticCache(redis_url="redis://localhost:6379/0")

    @pytest.mark.asyncio
    async def test_get_redis_error_returns_none(self) -> None:
        """测试 Redis 读取异常返回 None。"""
        cache = self._make_cache()

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Connection refused"))

        with patch.object(cache, "_get_redis", return_value=mock_redis):
            result = await cache.get_cached_results("销售额")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_redis_error_returns_false(self) -> None:
        """测试 Redis 写入异常返回 False。"""
        cache = self._make_cache()

        from datapilot_semantic.retrieval.cache import CachedSearchResult

        results = [
            CachedSearchResult(
                entity_type="metric",
                entity_id="id-1",
                score=0.95,
            ),
        ]

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(side_effect=Exception("Connection refused"))

        with patch.object(cache, "_get_redis", return_value=mock_redis):
            success = await cache.set_cached_results("销售额", results)

        assert success is False

    @pytest.mark.asyncio
    async def test_invalidate_redis_error_returns_false(self) -> None:
        """测试 Redis 删除异常返回 False。"""
        cache = self._make_cache()

        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(side_effect=Exception("Connection refused"))

        with patch.object(cache, "_get_redis", return_value=mock_redis):
            success = await cache.invalidate("销售额")

        assert success is False

    @pytest.mark.asyncio
    async def test_clear_all_redis_error_returns_false(self) -> None:
        """测试 Redis 批量删除异常返回 False。"""
        cache = self._make_cache()

        mock_redis = AsyncMock()
        mock_redis.scan_iter = AsyncMock(side_effect=Exception("Connection refused"))

        with patch.object(cache, "_get_redis", return_value=mock_redis):
            success = await cache.clear_all()

        assert success is False

    @pytest.mark.asyncio
    async def test_deserialize_error_in_get(self) -> None:
        """测试缓存值反序列化失败返回 None。"""
        cache = self._make_cache()

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="invalid json content")

        with patch.object(cache, "_get_redis", return_value=mock_redis):
            result = await cache.get_cached_results("销售额")

        assert result is None


# ---------------------------------------------------------------------------
# 配置测试
# ---------------------------------------------------------------------------


class TestSemanticCacheConfig:
    """SemanticCache 配置测试。"""

    def test_default_config(self) -> None:
        """测试默认配置。"""
        from datapilot_semantic.retrieval.cache import SemanticCache, SemanticCacheConfig

        cache = SemanticCache(redis_url="redis://localhost:6379/0")

        assert cache._config.redis_url == "redis://localhost:6379/0"
        assert cache._config.ttl == 300  # 默认 5 分钟
        assert cache._config.key_prefix == "datapilot:semantic_search:"

    def test_custom_ttl(self) -> None:
        """测试自定义 TTL。"""
        from datapilot_semantic.retrieval.cache import SemanticCache

        cache = SemanticCache(redis_url="redis://localhost:6379/0", ttl=600)
        assert cache._config.ttl == 600

    def test_cached_search_result_creation(self) -> None:
        """测试 CachedSearchResult 创建。"""
        from datapilot_semantic.retrieval.cache import CachedSearchResult

        result = CachedSearchResult(
            entity_type="metric",
            entity_id="id-1",
            score=0.95,
            entity_name="GMV",
            entity_description="商品交易总额",
        )

        assert result.entity_type == "metric"
        assert result.entity_id == "id-1"
        assert result.score == 0.95
        assert result.entity_name == "GMV"

    def test_cached_search_result_defaults(self) -> None:
        """测试 CachedSearchResult 默认值。"""
        from datapilot_semantic.retrieval.cache import CachedSearchResult

        result = CachedSearchResult(
            entity_type="dimension",
            entity_id="id-2",
            score=0.0,
        )

        assert result.entity_name is None
        assert result.entity_description is None
