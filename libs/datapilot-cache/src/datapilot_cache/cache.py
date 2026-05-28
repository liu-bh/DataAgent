"""内存缓存管理器。

提供基于 LRU 淘汰策略的内存缓存，支持命名空间隔离和过期清理。
"""

from __future__ import annotations

import logging
from typing import Any

from datapilot_cache.models import CacheEntry, CacheKey, CacheStats

logger = logging.getLogger(__name__)


class CacheManager:
    """内存缓存管理器。

    使用 LRU（最近最少使用）淘汰策略，当缓存条目数超过 max_size 时，
    自动淘汰最久未被访问的条目。

    Args:
        max_size: 最大缓存条目数，默认 1000。
        default_ttl: 默认过期时间（秒），默认 300 秒。
    """

    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        # 缓存存储：CacheKey -> CacheEntry
        self._store: dict[CacheKey, CacheEntry] = {}
        # 访问顺序列表，用于 LRU 淘汰
        self._access_order: list[CacheKey] = []
        # 统计信息
        self._stats = CacheStats()

    def get(self, key: CacheKey) -> Any | None:
        """获取缓存值。

        命中时更新 hit_count 和访问顺序，并增加统计计数。

        Args:
            key: 缓存键。

        Returns:
            缓存值，未命中或已过期返回 None。
        """
        entry = self._store.get(key)
        if entry is None:
            self._stats.misses += 1
            logger.debug("缓存未命中: %s", key)
            return None

        # 检查是否过期
        if entry.is_expired:
            # 过期条目直接删除
            self._remove_entry(key)
            self._stats.misses += 1
            logger.debug("缓存过期被移除: %s", key)
            return None

        # 命中：更新命中计数和访问顺序
        entry.hit_count += 1
        self._touch(key)
        self._stats.hits += 1
        logger.debug("缓存命中: %s (hit_count=%d)", key, entry.hit_count)
        return entry.value

    def set(
        self,
        key: CacheKey,
        value: Any,
        ttl: float | None = None,
    ) -> None:
        """设置缓存值。

        如果键已存在则更新值，超容量时执行 LRU 淘汰。

        Args:
            key: 缓存键。
            value: 缓存值。
            ttl: 过期时间（秒），为 None 时使用默认值。
        """
        actual_ttl = ttl if ttl is not None else self._default_ttl

        # 如果键已存在，先移除旧的（不影响容量计算）
        if key in self._store:
            self._remove_entry(key)

        # 检查容量，必要时淘汰
        while len(self._store) >= self._max_size:
            self._evict_lru()

        # 创建新条目
        import sys

        size_bytes = len(str(value).encode("utf-8")) if value is not None else 0
        # 对于 bytes 类型直接取长度
        if isinstance(value, (bytes, bytearray)):
            size_bytes = len(value)

        entry = CacheEntry(
            key=key,
            value=value,
            ttl=actual_ttl,
            size_bytes=size_bytes,
        )

        self._store[key] = entry
        self._touch(key)
        logger.debug("缓存设置: %s (ttl=%.1f, size=%d bytes)", key, actual_ttl, size_bytes)

    def delete(self, key: CacheKey) -> bool:
        """删除缓存条目。

        Args:
            key: 缓存键。

        Returns:
            是否删除成功（条目存在则返回 True）。
        """
        if key in self._store:
            self._remove_entry(key)
            logger.debug("缓存删除: %s", key)
            return True
        return False

    def clear(self, namespace: str | None = None) -> int:
        """清空缓存。

        Args:
            namespace: 命名空间，为 None 时清空所有缓存，
                      指定时仅清空对应命名空间的缓存。

        Returns:
            被清除的条目数。
        """
        if namespace is None:
            count = len(self._store)
            self._store.clear()
            self._access_order.clear()
            logger.info("缓存已全部清空，共 %d 条", count)
            return count

        # 按命名空间清除
        keys_to_remove = [
            k for k in self._store if k.namespace == namespace
        ]
        for key in keys_to_remove:
            self._remove_entry(key)
        logger.info("命名空间 '%s' 缓存已清空，共 %d 条", namespace, len(keys_to_remove))
        return len(keys_to_remove)

    def get_stats(self) -> CacheStats:
        """获取缓存统计信息的快照。

        Returns:
            包含最新数据的 CacheStats 实例。
        """
        total_size = sum(e.size_bytes for e in self._store.values())
        return CacheStats(
            hits=self._stats.hits,
            misses=self._stats.misses,
            evictions=self._stats.evictions,
            total_size_bytes=total_size,
            entry_count=len(self._store),
        )

    def cleanup_expired(self) -> int:
        """清理所有过期条目。

        Returns:
            被清理的条目数。
        """
        expired_keys = [
            key for key, entry in self._store.items() if entry.is_expired
        ]
        for key in expired_keys:
            self._remove_entry(key)
        if expired_keys:
            logger.info("清理过期缓存条目 %d 条", len(expired_keys))
        return len(expired_keys)

    def _touch(self, key: CacheKey) -> None:
        """将键移到访问顺序末尾（最近访问）。"""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def _remove_entry(self, key: CacheKey) -> None:
        """移除单个缓存条目及其访问顺序记录。"""
        self._store.pop(key, None)
        if key in self._access_order:
            self._access_order.remove(key)

    def _evict_lru(self) -> None:
        """淘汰最久未访问的缓存条目。"""
        if not self._access_order:
            return
        lru_key = self._access_order.pop(0)
        self._store.pop(lru_key, None)
        self._stats.evictions += 1
        logger.debug("LRU 淘汰: %s", lru_key)
