"""Sprint 10 Track B — 查询缓存层单元测试。

测试 datapilot-cache 库的核心功能：CacheKey、CacheEntry、CacheStats、
CacheManager、QueryResultCache、SemanticCache。
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from datapilot_cache.cache import CacheManager
from datapilot_cache.models import CacheEntry, CacheKey, CacheStats
from datapilot_cache.query_cache import QueryResultCache
from datapilot_cache.semantic_cache import SemanticCache


# ============================================================
# CacheKey 测试
# ============================================================


class TestCacheKey:
    """CacheKey 不可变数据类测试。"""

    def test_hash_and_equality(self) -> None:
        """相同字段值的 CacheKey 哈希和相等性一致。"""
        key1 = CacheKey(namespace="test", key="abc", version="v1")
        key2 = CacheKey(namespace="test", key="abc", version="v1")
        assert key1 == key2
        assert hash(key1) == hash(key2)

    def test_inequality_different_key(self) -> None:
        """不同 key 字段的不相等。"""
        key1 = CacheKey(namespace="test", key="abc")
        key2 = CacheKey(namespace="test", key="xyz")
        assert key1 != key2

    def test_inequality_different_namespace(self) -> None:
        """不同 namespace 字段的不相等。"""
        key1 = CacheKey(namespace="ns1", key="abc")
        key2 = CacheKey(namespace="ns2", key="abc")
        assert key1 != key2

    def test_inequality_different_version(self) -> None:
        """不同 version 字段的不相等。"""
        key1 = CacheKey(namespace="test", key="abc", version="v1")
        key2 = CacheKey(namespace="test", key="abc", version="v2")
        assert key1 != key2

    def test_equality_with_non_cache_key(self) -> None:
        """与不同类型比较返回 NotImplemented。"""
        key = CacheKey(namespace="test", key="abc")
        assert key != "test:abc"  # type: ignore[comparison-overlap]
        assert key != 42  # type: ignore[comparison-overlap]

    def test_frozen_immutable(self) -> None:
        """frozen=True 使实例不可变。"""
        key = CacheKey(namespace="test", key="abc")
        with pytest.raises(AttributeError):
            key.namespace = "modified"  # type: ignore[misc]

    def test_str_representation(self) -> None:
        """__str__ 返回格式化的字符串。"""
        key = CacheKey(namespace="query", key="abc123", version="v2")
        assert str(key) == "query:v2:abc123"

    def test_default_version(self) -> None:
        """默认 version 为 v1。"""
        key = CacheKey(namespace="test", key="abc")
        assert key.version == "v1"
        assert str(key) == "test:v1:abc"

    def test_usable_as_dict_key(self) -> None:
        """可作为字典键使用。"""
        key = CacheKey(namespace="test", key="abc")
        d: dict[CacheKey, str] = {key: "value"}
        assert d[key] == "value"

    def test_distinct_hashes_for_distinct_keys(self) -> None:
        """不同 CacheKey 哈希大概率不同。"""
        keys = [CacheKey(namespace="ns", key=f"k{i}") for i in range(100)]
        hashes = {hash(k) for k in keys}
        assert len(hashes) >= 95  # 允许极少碰撞


# ============================================================
# CacheEntry 测试
# ============================================================


class TestCacheEntry:
    """CacheEntry 数据类测试。"""

    def test_default_values(self) -> None:
        """默认值正确设置。"""
        key = CacheKey(namespace="test", key="abc")
        entry = CacheEntry(key=key, value="hello")
        assert entry.value == "hello"
        assert entry.hit_count == 0
        assert entry.size_bytes == 0
        assert entry.ttl == 300.0
        assert entry.tags == []

    def test_expires_at(self) -> None:
        """expires_at 计算正确。"""
        key = CacheKey(namespace="test", key="abc")
        entry = CacheEntry(key=key, value="data", created_at=1000.0, ttl=60.0)
        assert entry.expires_at == 1060.0

    def test_is_expired_false(self) -> None:
        """未过期时 is_expired 为 False。"""
        key = CacheKey(namespace="test", key="abc")
        entry = CacheEntry(key=key, value="data", created_at=time.time(), ttl=300.0)
        assert entry.is_expired is False

    def test_is_expired_true(self) -> None:
        """已过期时 is_expired 为 True。"""
        key = CacheKey(namespace="test", key="abc")
        entry = CacheEntry(key=key, value="data", created_at=time.time() - 500, ttl=300.0)
        assert entry.is_expired is True

    def test_custom_tags(self) -> None:
        """可自定义 tags。"""
        key = CacheKey(namespace="test", key="abc")
        entry = CacheEntry(key=key, value="data", tags=["sql", "user_query"])
        assert entry.tags == ["sql", "user_query"]

    def test_custom_size_bytes(self) -> None:
        """可自定义 size_bytes。"""
        key = CacheKey(namespace="test", key="abc")
        entry = CacheEntry(key=key, value="data", size_bytes=1024)
        assert entry.size_bytes == 1024


# ============================================================
# CacheStats 测试
# ============================================================


class TestCacheStats:
    """CacheStats 数据类测试。"""

    def test_hit_rate_zero(self) -> None:
        """无访问时命中率为 0。"""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate_all_hits(self) -> None:
        """全部命中时命中率为 1.0。"""
        stats = CacheStats(hits=10, misses=0)
        assert stats.hit_rate == 1.0

    def test_hit_rate_partial(self) -> None:
        """部分命中时命中率计算正确。"""
        stats = CacheStats(hits=3, misses=7)
        assert stats.hit_rate == pytest.approx(0.3)

    def test_hit_rate_all_misses(self) -> None:
        """全部未命中时命中率为 0。"""
        stats = CacheStats(hits=0, misses=5)
        assert stats.hit_rate == 0.0

    def test_default_values(self) -> None:
        """默认值全部为零。"""
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.total_size_bytes == 0
        assert stats.entry_count == 0


# ============================================================
# CacheManager 测试
# ============================================================


class TestCacheManager:
    """CacheManager 缓存管理器测试。"""

    def test_set_and_get(self) -> None:
        """基本设置和获取。"""
        cache = CacheManager()
        key = CacheKey(namespace="test", key="a")
        cache.set(key, "value1")
        assert cache.get(key) == "value1"

    def test_get_miss_returns_none(self) -> None:
        """获取不存在的键返回 None。"""
        cache = CacheManager()
        key = CacheKey(namespace="test", key="nonexistent")
        assert cache.get(key) is None

    def test_set_overwrite(self) -> None:
        """覆盖已存在的键。"""
        cache = CacheManager()
        key = CacheKey(namespace="test", key="a")
        cache.set(key, "v1")
        cache.set(key, "v2")
        assert cache.get(key) == "v2"

    def test_delete_existing(self) -> None:
        """删除存在的条目返回 True。"""
        cache = CacheManager()
        key = CacheKey(namespace="test", key="a")
        cache.set(key, "value")
        assert cache.delete(key) is True
        assert cache.get(key) is None

    def test_delete_nonexistent(self) -> None:
        """删除不存在的条目返回 False。"""
        cache = CacheManager()
        key = CacheKey(namespace="test", key="a")
        assert cache.delete(key) is False

    def test_clear_all(self) -> None:
        """清空所有缓存。"""
        cache = CacheManager()
        k1 = CacheKey(namespace="ns1", key="a")
        k2 = CacheKey(namespace="ns2", key="b")
        cache.set(k1, "v1")
        cache.set(k2, "v2")
        count = cache.clear()
        assert count == 2
        assert cache.get(k1) is None
        assert cache.get(k2) is None

    def test_clear_by_namespace(self) -> None:
        """按命名空间清空。"""
        cache = CacheManager()
        k1 = CacheKey(namespace="ns1", key="a")
        k2 = CacheKey(namespace="ns2", key="b")
        k3 = CacheKey(namespace="ns1", key="c")
        cache.set(k1, "v1")
        cache.set(k2, "v2")
        cache.set(k3, "v3")

        count = cache.clear(namespace="ns1")
        assert count == 2
        assert cache.get(k1) is None
        assert cache.get(k3) is None
        assert cache.get(k2) == "v2"

    def test_clear_empty_namespace(self) -> None:
        """清空不存在的命名空间返回 0。"""
        cache = CacheManager()
        count = cache.clear(namespace="nonexistent")
        assert count == 0

    def test_stats_hits_and_misses(self) -> None:
        """统计命中和未命中次数。"""
        cache = CacheManager()
        k1 = CacheKey(namespace="test", key="a")
        k2 = CacheKey(namespace="test", key="b")

        cache.set(k1, "v1")
        cache.get(k1)  # hit
        cache.get(k1)  # hit
        cache.get(k2)  # miss

        stats = cache.get_stats()
        assert stats.hits == 2
        assert stats.misses == 1

    def test_stats_entry_count(self) -> None:
        """统计条目数。"""
        cache = CacheManager()
        cache.set(CacheKey(namespace="test", key="a"), "v1")
        cache.set(CacheKey(namespace="test", key="b"), "v2")
        stats = cache.get_stats()
        assert stats.entry_count == 2

    def test_stats_total_size_bytes(self) -> None:
        """统计总大小。"""
        cache = CacheManager()
        cache.set(CacheKey(namespace="test", key="a"), "hello")
        cache.set(CacheKey(namespace="test", key="b"), "world!")
        stats = cache.get_stats()
        # "hello" = 5 bytes, "world!" = 6 bytes
        assert stats.total_size_bytes == 11

    def test_lru_eviction(self) -> None:
        """LRU 淘汰策略：超过容量时淘汰最久未访问的条目。"""
        cache = CacheManager(max_size=3)
        k1 = CacheKey(namespace="test", key="a")
        k2 = CacheKey(namespace="test", key="b")
        k3 = CacheKey(namespace="test", key="c")
        k4 = CacheKey(namespace="test", key="d")

        cache.set(k1, "v1")
        cache.set(k2, "v2")
        cache.set(k3, "v3")
        # 访问 k1，使其变为最近使用
        cache.get(k1)
        # 添加 k4，应淘汰 k2（最久未访问）
        cache.set(k4, "v4")

        stats = cache.get_stats()
        assert stats.evictions == 1
        assert cache.get(k2) is None  # k2 被淘汰
        assert cache.get(k1) == "v1"  # k1 仍在

    def test_lru_eviction_on_set_overwrite(self) -> None:
        """覆盖已有键时不触发额外的淘汰。"""
        cache = CacheManager(max_size=2)
        k1 = CacheKey(namespace="test", key="a")
        k2 = CacheKey(namespace="test", key="b")

        cache.set(k1, "v1")
        cache.set(k2, "v2")
        # 覆盖 k1，不增加条目数
        cache.set(k1, "v1_new")

        stats = cache.get_stats()
        assert stats.evictions == 0
        assert stats.entry_count == 2

    def test_cleanup_expired(self) -> None:
        """清理过期条目。"""
        cache = CacheManager()
        k1 = CacheKey(namespace="test", key="expired")
        k2 = CacheKey(namespace="test", key="fresh")

        # 手动创建一个已过期的条目
        entry_expired = CacheEntry(
            key=k1,
            value="old",
            created_at=time.time() - 500,
            ttl=300.0,
        )
        entry_fresh = CacheEntry(
            key=k2,
            value="new",
            created_at=time.time(),
            ttl=300.0,
        )

        cache._store[k1] = entry_expired
        cache._store[k2] = entry_fresh
        cache._access_order = [k1, k2]

        cleaned = cache.cleanup_expired()
        assert cleaned == 1
        assert cache.get(k1) is None
        assert cache.get(k2) == "new"

    def test_get_expired_returns_none(self) -> None:
        """获取已过期条目返回 None。"""
        cache = CacheManager()
        k = CacheKey(namespace="test", key="old")

        entry = CacheEntry(
            key=k,
            value="stale",
            created_at=time.time() - 500,
            ttl=300.0,
        )
        cache._store[k] = entry
        cache._access_order = [k]

        assert cache.get(k) is None
        # 过期条目应在 get 时被自动移除
        assert k not in cache._store

    def test_default_ttl(self) -> None:
        """使用默认 TTL。"""
        cache = CacheManager(default_ttl=60.0)
        k = CacheKey(namespace="test", key="a")
        cache.set(k, "value")
        entry = cache._store[k]
        assert entry.ttl == 60.0

    def test_custom_ttl(self) -> None:
        """自定义 TTL。"""
        cache = CacheManager(default_ttl=300.0)
        k = CacheKey(namespace="test", key="a")
        cache.set(k, "value", ttl=600.0)
        entry = cache._store[k]
        assert entry.ttl == 600.0

    def test_hit_count_increments(self) -> None:
        """命中时 hit_count 递增。"""
        cache = CacheManager()
        k = CacheKey(namespace="test", key="a")
        cache.set(k, "value")

        cache.get(k)
        cache.get(k)
        cache.get(k)

        entry = cache._store[k]
        assert entry.hit_count == 3

    def test_max_size_one(self) -> None:
        """max_size=1 时仅保留最后一条。"""
        cache = CacheManager(max_size=1)
        k1 = CacheKey(namespace="test", key="a")
        k2 = CacheKey(namespace="test", key="b")

        cache.set(k1, "v1")
        cache.set(k2, "v2")

        assert cache.get(k1) is None
        assert cache.get(k2) == "v2"


# ============================================================
# QueryResultCache 测试
# ============================================================


class TestQueryResultCache:
    """QueryResultCache 查询结果缓存测试。"""

    def test_generate_key_deterministic(self) -> None:
        """相同输入生成相同的键。"""
        cache = CacheManager()
        qc = QueryResultCache(cache)
        k1 = qc.generate_key("SELECT 1", (), "ds1")
        k2 = qc.generate_key("SELECT 1", (), "ds1")
        assert k1 == k2

    def test_generate_key_different_sql(self) -> None:
        """不同 SQL 生成不同的键。"""
        cache = CacheManager()
        qc = QueryResultCache(cache)
        k1 = qc.generate_key("SELECT 1", (), "ds1")
        k2 = qc.generate_key("SELECT 2", (), "ds1")
        assert k1 != k2

    def test_generate_key_different_params(self) -> None:
        """不同参数生成不同的键。"""
        cache = CacheManager()
        qc = QueryResultCache(cache)
        k1 = qc.generate_key("SELECT * FROM t WHERE id = %s", (1,), "ds1")
        k2 = qc.generate_key("SELECT * FROM t WHERE id = %s", (2,), "ds1")
        assert k1 != k2

    def test_generate_key_different_datasource(self) -> None:
        """不同数据源生成不同的键。"""
        cache = CacheManager()
        qc = QueryResultCache(cache)
        k1 = qc.generate_key("SELECT 1", (), "ds1")
        k2 = qc.generate_key("SELECT 1", (), "ds2")
        assert k1 != k2

    def test_generate_key_default_params(self) -> None:
        """默认参数为空元组。"""
        cache = CacheManager()
        qc = QueryResultCache(cache)
        k1 = qc.generate_key("SELECT 1")
        k2 = qc.generate_key("SELECT 1", ())
        assert k1 == k2

    def test_set_and_get(self) -> None:
        """设置和获取查询结果。"""
        cache = CacheManager()
        qc = QueryResultCache(cache)
        result = [{"id": 1, "name": "test"}]
        qc.set("SELECT * FROM users WHERE id = 1", result, ttl=60.0, datasource_id="pg1")
        cached = qc.get("SELECT * FROM users WHERE id = 1", datasource_id="pg1")
        assert cached == result

    def test_get_miss(self) -> None:
        """未命中返回 None。"""
        cache = CacheManager()
        qc = QueryResultCache(cache)
        assert qc.get("SELECT * FROM nonexistent") is None

    def test_invalidate_datasource(self) -> None:
        """按数据源失效清空整个命名空间。"""
        cache = CacheManager()
        qc = QueryResultCache(cache)

        qc.set("SELECT 1", "r1", datasource_id="ds1")
        qc.set("SELECT 2", "r2", datasource_id="ds1")
        qc.set("SELECT 3", "r3", datasource_id="ds2")

        # invalidate_datasource 清理整个 query_result 命名空间
        count = qc.invalidate_datasource("ds1")
        # 至少清除了 2 条（ds1 的），实际清除了整个命名空间 3 条
        assert count == 3
        assert qc.get("SELECT 1", datasource_id="ds1") is None

    def test_generate_key_namespace(self) -> None:
        """生成的键命名空间为 query_result。"""
        cache = CacheManager()
        qc = QueryResultCache(cache)
        key = qc.generate_key("SELECT 1")
        assert key.namespace == "query_result"

    def test_set_default_ttl(self) -> None:
        """默认 TTL 为 60 秒。"""
        cache = CacheManager()
        qc = QueryResultCache(cache)
        k = qc.generate_key("SELECT 1")
        qc.set("SELECT 1", "data")
        entry = cache._store[k]
        assert entry.ttl == 60.0

    def test_set_custom_ttl(self) -> None:
        """自定义 TTL。"""
        cache = CacheManager()
        qc = QueryResultCache(cache)
        k = qc.generate_key("SELECT 1")
        qc.set("SELECT 1", "data", ttl=120.0)
        entry = cache._store[k]
        assert entry.ttl == 120.0


# ============================================================
# SemanticCache 测试
# ============================================================


class TestSemanticCache:
    """SemanticCache 语义缓存测试。"""

    def test_tokenize_chinese(self) -> None:
        """中文分词正确。"""
        cache = CacheManager()
        sc = SemanticCache(cache)
        tokens = sc._tokenize("查询用户数据")
        assert "查" in tokens
        assert "询" in tokens
        assert "用" in tokens
        assert "户" in tokens
        assert "数" in tokens
        assert "据" in tokens

    def test_tokenize_english(self) -> None:
        """英文分词按单词拆分。"""
        cache = CacheManager()
        sc = SemanticCache(cache)
        tokens = sc._tokenize("show me the users")
        assert "show" in tokens
        assert "me" in tokens
        assert "the" in tokens
        assert "users" in tokens

    def test_tokenize_mixed(self) -> None:
        """中英文混合分词。"""
        cache = CacheManager()
        sc = SemanticCache(cache)
        tokens = sc._tokenize("查询user数据")
        assert "查" in tokens
        assert "user" in tokens
        assert "数" in tokens

    def test_tokenize_case_insensitive(self) -> None:
        """分词忽略大小写。"""
        cache = CacheManager()
        sc = SemanticCache(cache)
        t1 = sc._tokenize("Show Users")
        t2 = sc._tokenize("show users")
        assert t1 == t2

    def test_similarity_identical(self) -> None:
        """完全相同的问题相似度为 1.0。"""
        cache = CacheManager()
        sc = SemanticCache(cache)
        sim = sc._calculate_similarity("查询用户数据", "查询用户数据")
        assert sim == pytest.approx(1.0)

    def test_similarity_different(self) -> None:
        """完全不同的问题相似度较低。"""
        cache = CacheManager()
        sc = SemanticCache(cache)
        sim = sc._calculate_similarity("查询用户数据", "删除系统日志")
        assert sim < 0.5

    def test_similarity_similar(self) -> None:
        """语义相似的问题相似度较高。"""
        cache = CacheManager()
        sc = SemanticCache(cache)
        sim = sc._calculate_similarity(
            "查询用户订单数据",
            "查询用户的订单信息",
        )
        assert sim > 0.5

    def test_similarity_empty_strings(self) -> None:
        """两个空字符串的相似度为 1.0。"""
        cache = CacheManager()
        sc = SemanticCache(cache)
        sim = sc._calculate_similarity("", "")
        assert sim == 1.0

    def test_similarity_one_empty(self) -> None:
        """一个空字符串的相似度为 0。"""
        cache = CacheManager()
        sc = SemanticCache(cache)
        sim = sc._calculate_similarity("查询数据", "")
        assert sim == 0.0

    def test_set_and_get_exact_match(self) -> None:
        """完全匹配时缓存命中。"""
        cache = CacheManager()
        sc = SemanticCache(cache)
        result = [{"data": "users"}]
        sc.set("查询用户数据", result)
        cached = sc.get("查询用户数据")
        assert cached == result

    def test_get_miss(self) -> None:
        """无匹配时返回 None。"""
        cache = CacheManager()
        sc = SemanticCache(cache)
        assert sc.get("查询用户数据") is None

    def test_get_semantic_match(self) -> None:
        """语义相似时缓存命中。"""
        cache = CacheManager()
        sc = SemanticCache(cache, similarity_threshold=0.5)
        result = [{"data": "orders"}]
        sc.set("查询订单数据", result)
        cached = sc.get("查询订单信息")
        assert cached == result

    def test_get_below_threshold(self) -> None:
        """低于阈值时缓存不命中。"""
        cache = CacheManager()
        sc = SemanticCache(cache, similarity_threshold=0.99)
        sc.set("查询订单数据", "result")
        cached = sc.get("删除系统日志")
        assert cached is None

    def test_set_and_get_with_session_id(self) -> None:
        """带 session_id 的设置和获取。"""
        cache = CacheManager()
        sc = SemanticCache(cache)
        sc.set("查询用户", "result1", session_id="s1")
        cached = sc.get("查询用户", session_id="s1")
        assert cached == "result1"

    def test_clear(self) -> None:
        """清空语义缓存。"""
        cache = CacheManager()
        sc = SemanticCache(cache)
        sc.set("查询用户", "result1")
        sc.set("查询订单", "result2")
        sc.clear()
        assert sc.get("查询用户") is None
        assert sc.get("查询订单") is None

    def test_make_key_namespace(self) -> None:
        """生成的键命名空间为 semantic。"""
        cache = CacheManager()
        sc = SemanticCache(cache)
        key = sc._make_key("查询用户")
        assert key.namespace == "semantic"

    def test_custom_similarity_threshold(self) -> None:
        """自定义相似度阈值。"""
        cache = CacheManager()
        sc = SemanticCache(cache, similarity_threshold=0.3)
        assert sc._threshold == 0.3


# ============================================================
# 集成场景测试
# ============================================================


class TestIntegration:
    """跨模块集成测试。"""

    def test_query_cache_uses_cache_manager_stats(self) -> None:
        """查询缓存的命中/未命中反映在 CacheManager 统计中。"""
        cache = CacheManager()
        qc = QueryResultCache(cache)

        qc.set("SELECT 1", "r1")
        qc.get("SELECT 1")  # hit
        qc.get("SELECT 2")  # miss

        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1

    def test_semantic_cache_uses_cache_manager_stats(self) -> None:
        """语义缓存的命中/未命中反映在 CacheManager 统计中。"""
        cache = CacheManager()
        sc = SemanticCache(cache)

        sc.set("查询用户", "r1")
        sc.get("查询用户")  # hit
        sc.get("完全不相关问题")  # miss

        stats = cache.get_stats()
        assert stats.hits >= 1
        assert stats.misses >= 1

    def test_multiple_namespaces_isolated(self) -> None:
        """不同命名空间的缓存互不影响。"""
        cache = CacheManager()
        qc = QueryResultCache(cache)
        sc = SemanticCache(cache)

        qc.set("SELECT 1", "query_result")
        sc.set("查询用户", "semantic_result")

        # 清空 query_result 命名空间
        qc.invalidate_datasource("ds1")

        # 语义缓存不受影响
        assert sc.get("查询用户") == "semantic_result"

    def test_cache_entry_with_bytes_value_size(self) -> None:
        """bytes 值的 size_bytes 正确计算。"""
        cache = CacheManager()
        key = CacheKey(namespace="test", key="binary")
        data = b"\x00\x01\x02" * 100  # 300 bytes
        cache.set(key, data)
        entry = cache._store[key]
        assert entry.size_bytes == 300
