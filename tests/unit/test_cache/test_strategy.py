"""缓存策略单元测试。

测试分级缓存策略的层级决策逻辑和缓存 key 生成。
"""

from __future__ import annotations

import hashlib

import pytest

from datapilot_queryexec.cache.strategy import CachePolicy, CacheStrategy, CacheTier


class TestCacheTier:
    """CacheTier 枚举测试。"""

    def test_tier_values(self) -> None:
        """验证枚举值正确。"""
        assert CacheTier.NONE == "none"
        assert CacheTier.REDIS == "redis"
        assert CacheTier.MINIO == "minio"


class TestCachePolicy:
    """CachePolicy 数据类测试。"""

    def test_default_values(self) -> None:
        """验证默认策略值。"""
        policy = CachePolicy()
        assert policy.tier == CacheTier.NONE
        assert policy.ttl_seconds == 300
        assert policy.max_size_bytes == 1048576

    def test_custom_values(self) -> None:
        """验证自定义策略值。"""
        policy = CachePolicy(
            tier=CacheTier.REDIS,
            ttl_seconds=600,
            max_size_bytes=2097152,
        )
        assert policy.tier == CacheTier.REDIS
        assert policy.ttl_seconds == 600
        assert policy.max_size_bytes == 2097152


class TestCacheStrategy:
    """CacheStrategy 决策逻辑测试。"""

    def test_init_with_default_policy(self) -> None:
        """使用默认策略初始化。"""
        strategy = CacheStrategy()
        assert strategy._default_policy.tier == CacheTier.NONE
        assert strategy._default_policy.ttl_seconds == 300

    def test_init_with_custom_policy(self) -> None:
        """使用自定义策略初始化。"""
        policy = CachePolicy(ttl_seconds=120)
        strategy = CacheStrategy(default_policy=policy)
        assert strategy._default_policy.ttl_seconds == 120

    def test_determine_tier_small_data(self) -> None:
        """小数据集应选择 Redis。"""
        strategy = CacheStrategy()
        tier = strategy.determine_tier(1024)  # 1KB
        assert tier == CacheTier.REDIS

    def test_determine_tier_large_data(self) -> None:
        """大数据集应选择 MinIO。"""
        strategy = CacheStrategy()
        tier = strategy.determine_tier(2 * 1024 * 1024)  # 2MB
        assert tier == CacheTier.MINIO

    def test_determine_tier_boundary(self) -> None:
        """边界值：恰好等于阈值应选择 MinIO。"""
        strategy = CacheStrategy()
        tier = strategy.determine_tier(1048576)  # 恰好 1MB
        assert tier == CacheTier.MINIO

    def test_determine_tier_just_below_boundary(self) -> None:
        """边界值：小于阈值 1 字节应选择 Redis。"""
        strategy = CacheStrategy()
        tier = strategy.determine_tier(1048575)  # 1MB - 1
        assert tier == CacheTier.REDIS

    def test_determine_tier_zero_size(self) -> None:
        """零字节数据应选择 Redis。"""
        strategy = CacheStrategy()
        tier = strategy.determine_tier(0)
        assert tier == CacheTier.REDIS

    def test_determine_tier_forced_redis(self) -> None:
        """策略强制 Redis，忽略数据大小。"""
        strategy = CacheStrategy()
        policy = CachePolicy(tier=CacheTier.REDIS)
        tier = strategy.determine_tier(10 * 1024 * 1024, policy=policy)  # 10MB
        assert tier == CacheTier.REDIS

    def test_determine_tier_forced_minio(self) -> None:
        """策略强制 MinIO，忽略数据大小。"""
        strategy = CacheStrategy()
        policy = CachePolicy(tier=CacheTier.MINIO)
        tier = strategy.determine_tier(100, policy=policy)  # 100 字节
        assert tier == CacheTier.MINIO

    def test_determine_tier_forced_none_auto_decides(self) -> None:
        """策略为 NONE 时自动决策。"""
        strategy = CacheStrategy()
        policy = CachePolicy(tier=CacheTier.NONE)
        tier = strategy.determine_tier(1024, policy=policy)
        assert tier == CacheTier.REDIS

    def test_determine_tier_custom_threshold(self) -> None:
        """自定义阈值：小数据走 Redis，大数据走 MinIO。"""
        policy = CachePolicy(max_size_bytes=512)  # 512 字节阈值
        strategy = CacheStrategy(default_policy=policy)

        assert strategy.determine_tier(256) == CacheTier.REDIS
        assert strategy.determine_tier(512) == CacheTier.MINIO
        assert strategy.determine_tier(1024) == CacheTier.MINIO

    def test_determine_tier_override_with_param_policy(self) -> None:
        """参数 policy 覆盖默认策略。"""
        default_policy = CachePolicy(max_size_bytes=10 * 1024 * 1024)
        strategy = CacheStrategy(default_policy=default_policy)

        # 用参数 policy 的阈值
        param_policy = CachePolicy(max_size_bytes=100)
        assert strategy.determine_tier(200, policy=param_policy) == CacheTier.MINIO
        # 不传参数 policy，用默认
        assert strategy.determine_tier(200) == CacheTier.REDIS


class TestBuildCacheKey:
    """缓存 key 生成测试。"""

    def test_key_format(self) -> None:
        """验证 key 格式为 query_cache:<md5hex>。"""
        strategy = CacheStrategy()
        key = strategy.build_cache_key("SELECT 1", "tenant-1", "mysql")
        assert key.startswith("query_cache:")
        assert len(key.split(":")[1]) == 32  # MD5 哈希 32 位

    def test_key_deterministic(self) -> None:
        """相同输入应生成相同的 key。"""
        strategy = CacheStrategy()
        key1 = strategy.build_cache_key("SELECT 1", "tenant-1", "mysql")
        key2 = strategy.build_cache_key("SELECT 1", "tenant-1", "mysql")
        assert key1 == key2

    def test_key_different_sql(self) -> None:
        """不同 SQL 应生成不同 key。"""
        strategy = CacheStrategy()
        key1 = strategy.build_cache_key("SELECT 1", "tenant-1", "mysql")
        key2 = strategy.build_cache_key("SELECT 2", "tenant-1", "mysql")
        assert key1 != key2

    def test_key_different_tenant(self) -> None:
        """不同租户应生成不同 key（多租户隔离）。"""
        strategy = CacheStrategy()
        key1 = strategy.build_cache_key("SELECT 1", "tenant-1", "mysql")
        key2 = strategy.build_cache_key("SELECT 1", "tenant-2", "mysql")
        assert key1 != key2

    def test_key_different_dialect(self) -> None:
        """不同方言应生成不同 key。"""
        strategy = CacheStrategy()
        key1 = strategy.build_cache_key("SELECT 1", "tenant-1", "mysql")
        key2 = strategy.build_cache_key("SELECT 1", "tenant-1", "postgresql")
        assert key1 != key2

    def test_key_hash_correctness(self) -> None:
        """验证哈希计算的正确性。"""
        strategy = CacheStrategy()
        sql = "SELECT 1"
        tenant_id = "tenant-1"
        dialect = "mysql"
        key = strategy.build_cache_key(sql, tenant_id, dialect)

        raw = f"{sql}:{tenant_id}:{dialect}"
        expected_hash = hashlib.md5(raw.encode()).hexdigest()
        assert key == f"query_cache:{expected_hash}"
