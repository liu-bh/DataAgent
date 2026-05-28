"""查询结果缓存。

基于 SQL 和参数生成缓存键，支持按数据源失效。
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Any

from datapilot_cache.models import CacheKey

if TYPE_CHECKING:
    from datapilot_cache.cache import CacheManager

logger = logging.getLogger(__name__)


class QueryResultCache:
    """查询结果缓存。

    使用 SQL 语句、查询参数和数据源 ID 生成唯一的缓存键，
    支持按数据源维度批量失效缓存。

    Args:
        cache: 底层缓存管理器实例。
    """

    def __init__(self, cache: CacheManager) -> None:
        self._cache = cache
        self._namespace = "query_result"

    def generate_key(
        self,
        sql: str,
        params: tuple = (),
        datasource_id: str = "",
    ) -> CacheKey:
        """生成查询缓存键。

        将 SQL、参数和数据源 ID 拼接后做 SHA256 哈希，
        确保不同查询生成不同的键。

        Args:
            sql: SQL 查询语句。
            params: 查询参数元组。
            datasource_id: 数据源标识。

        Returns:
            不可变的 CacheKey 实例。
        """
        # 拼接各字段并生成哈希
        raw = f"{datasource_id}|{sql}|{params}"
        key_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
        return CacheKey(namespace=self._namespace, key=key_hash)

    def get(
        self,
        sql: str,
        params: tuple = (),
        datasource_id: str = "",
    ) -> Any | None:
        """获取查询缓存。

        Args:
            sql: SQL 查询语句。
            params: 查询参数元组。
            datasource_id: 数据源标识。

        Returns:
            缓存结果，未命中返回 None。
        """
        cache_key = self.generate_key(sql, params, datasource_id)
        return self._cache.get(cache_key)

    def set(
        self,
        sql: str,
        result: Any,
        ttl: float = 60.0,
        datasource_id: str = "",
    ) -> None:
        """设置查询缓存。

        Args:
            sql: SQL 查询语句。
            result: 查询结果。
            ttl: 过期时间（秒），默认 60 秒。
            datasource_id: 数据源标识。
        """
        cache_key = self.generate_key(sql, params=(), datasource_id=datasource_id)
        self._cache.set(cache_key, result, ttl=ttl)

    def invalidate_datasource(self, datasource_id: str) -> int:
        """按数据源 ID 失效缓存。

        遍历所有缓存条目，删除命名空间匹配且键中包含数据源 ID 的条目。
        由于键是哈希值，无法直接反向匹配数据源 ID，因此通过
        清理整个 query_result 命名空间来实现（Phase1 简化方案）。

        Args:
            datasource_id: 需要失效的数据源标识。

        Returns:
            被失效的条目数。
        """
        # Phase1: 由于键为哈希值无法反向查找数据源 ID，
        # 清理整个 query_result 命名空间
        logger.info(
            "按数据源 ID 失效缓存: datasource_id=%s (清理整个命名空间)",
            datasource_id,
        )
        return self._cache.clear(namespace=self._namespace)
