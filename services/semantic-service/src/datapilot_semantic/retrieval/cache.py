"""语义缓存模块。

基于 Redis 缓存语义检索结果（query → search results），避免对相同或相似查询重复计算。

特性:
- 缓存键使用 query 的 MD5 hash
- TTL 可配置（默认 5 分钟）
- 支持批量缓存和批量获取

用法::

    cache = SemanticCache(redis_url="redis://localhost:6379")
    cached = await cache.get_cached_results("上个月销售额")
    if cached is None:
        results = await searcher.search("上个月销售额")
        await cache.set_cached_results("上个月销售额", results)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# 默认缓存 TTL（秒）
DEFAULT_CACHE_TTL = 300  # 5 分钟

# 缓存键前缀
CACHE_KEY_PREFIX = "datapilot:semantic_search:"

# Redis 连接默认配置
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


@dataclass
class CachedSearchResult:
    """缓存中的单条搜索结果。

    Attributes:
        entity_type: 实体类型。
        entity_id: 实体 ID。
        score: 得分。
        entity_name: 实体名称。
        entity_description: 实体描述。
    """

    entity_type: str
    entity_id: str
    score: float
    entity_name: str | None = None
    entity_description: str | None = None


@dataclass
class SemanticCacheConfig:
    """语义缓存配置。

    Attributes:
        redis_url: Redis 连接串。
        ttl: 缓存过期时间（秒）。
        key_prefix: 缓存键前缀。
    """

    redis_url: str = DEFAULT_REDIS_URL
    ttl: int = DEFAULT_CACHE_TTL
    key_prefix: str = CACHE_KEY_PREFIX


class SemanticCache:
    """基于 Redis 的语义检索结果缓存。

    使用 query 文本的 MD5 hash 作为缓存键，结果序列化为 JSON 存储。
    """

    def __init__(
        self,
        redis_url: str | None = None,
        ttl: int | None = None,
    ) -> None:
        """初始化 SemanticCache。

        Args:
            redis_url: Redis 连接串。默认从环境变量 AGENT_REDIS_URL 读取，
                      或使用 localhost:6379。
            ttl: 缓存过期时间（秒）。默认 300（5 分钟）。
        """
        import os

        redis_url = redis_url or os.getenv(
            "AGENT_REDIS_URL", DEFAULT_REDIS_URL
        )

        self._config = SemanticCacheConfig(
            redis_url=redis_url,
            ttl=ttl or DEFAULT_CACHE_TTL,
        )

        # Redis 客户端延迟初始化
        self._redis: Any = None

    async def _get_redis(self) -> Any:
        """获取或创建 Redis 客户端（懒初始化）。

        使用 redis.asyncio 或 aioredis（取决于安装的包）。
        """
        if self._redis is not None:
            return self._redis

        try:
            import redis.asyncio as aioredis
        except ImportError:
            import aioredis  # type: ignore[no-redef]

        self._redis = aioredis.from_url(
            self._config.redis_url,
            decode_responses=True,
        )
        return self._redis

    async def close(self) -> None:
        """关闭 Redis 连接。"""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None

    # ------------------------------------------------------------------
    # 缓存键生成
    # ------------------------------------------------------------------

    @staticmethod
    def _query_to_key(query: str, prefix: str = CACHE_KEY_PREFIX) -> str:
        """将查询文本转换为缓存键。

        使用 MD5 hash 确保键长度固定，添加前缀避免冲突。

        Args:
            query: 用户查询文本。
            prefix: 缓存键前缀。

        Returns:
            Redis 缓存键，如 "datapilot:semantic_search:abc123..."。
        """
        normalized = query.strip().lower()
        hash_hex = hashlib.md5(normalized.encode("utf-8")).hexdigest()
        return f"{prefix}{hash_hex}"

    # ------------------------------------------------------------------
    # 序列化 / 反序列化
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_results(results: list[CachedSearchResult]) -> str:
        """将搜索结果序列化为 JSON 字符串。

        Args:
            results: CachedSearchResult 列表。

        Returns:
            JSON 字符串。
        """
        data = [
            {
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "score": r.score,
                "entity_name": r.entity_name,
                "entity_description": r.entity_description,
            }
            for r in results
        ]
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def _deserialize_results(raw: str) -> list[CachedSearchResult]:
        """将 JSON 字符串反序列化为搜索结果。

        Args:
            raw: JSON 字符串。

        Returns:
            CachedSearchResult 列表。
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning("cache_deserialize_failed", error=str(e))
            return []

        if not isinstance(data, list):
            return []

        results: list[CachedSearchResult] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            results.append(CachedSearchResult(
                entity_type=item.get("entity_type", ""),
                entity_id=item.get("entity_id", ""),
                score=float(item.get("score", 0.0)),
                entity_name=item.get("entity_name"),
                entity_description=item.get("entity_description"),
            ))
        return results

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    async def get_cached_results(
        self,
        query: str,
    ) -> list[CachedSearchResult] | None:
        """获取缓存的搜索结果。

        Args:
            query: 用户查询文本。

        Returns:
            缓存的搜索结果列表，如果缓存未命中则返回 None。
        """
        redis = await self._get_redis()
        key = self._query_to_key(query, self._config.key_prefix)

        try:
            raw = await redis.get(key)
            if raw is None:
                logger.debug("semantic_cache_miss", query=query, key=key)
                return None

            results = self._deserialize_results(raw)
            if not results:
                logger.debug("semantic_cache_empty_results", query=query, key=key)
                return None

            logger.debug(
                "semantic_cache_hit",
                query=query,
                key=key,
                result_count=len(results),
            )
            return results

        except Exception as e:
            logger.warning(
                "semantic_cache_get_error",
                query=query,
                key=key,
                error=str(e),
            )
            return None  # 缓存异常不影响主流程

    async def set_cached_results(
        self,
        query: str,
        results: list[CachedSearchResult],
    ) -> bool:
        """缓存搜索结果。

        Args:
            query: 用户查询文本。
            results: 搜索结果列表。

        Returns:
            是否成功写入缓存。
        """
        if not results:
            return False

        redis = await self._get_redis()
        key = self._query_to_key(query, self._config.key_prefix)
        value = self._serialize_results(results)

        try:
            await redis.set(key, value, ex=self._config.ttl)
            logger.debug(
                "semantic_cache_set",
                query=query,
                key=key,
                result_count=len(results),
                ttl=self._config.ttl,
            )
            return True

        except Exception as e:
            logger.warning(
                "semantic_cache_set_error",
                query=query,
                key=key,
                error=str(e),
            )
            return False  # 缓存异常不影响主流程

    async def invalidate(
        self,
        query: str,
    ) -> bool:
        """使指定查询的缓存失效。

        Args:
            query: 用户查询文本。

        Returns:
            是否成功删除缓存。
        """
        redis = await self._get_redis()
        key = self._query_to_key(query, self._config.key_prefix)

        try:
            await redis.delete(key)
            logger.debug("semantic_cache_invalidate", query=query, key=key)
            return True

        except Exception as e:
            logger.warning(
                "semantic_cache_invalidate_error",
                query=query,
                key=key,
                error=str(e),
            )
            return False

    async def clear_all(self) -> bool:
        """清除所有语义搜索缓存。

        使用 SCAN + DEL 避免 KEYS 命令在生产环境阻塞。

        Returns:
            是否成功清除。
        """
        redis = await self._get_redis()
        prefix = self._config.key_prefix

        try:
            deleted_count = 0
            async for key in redis.scan_iter(match=f"{prefix}*", count=100):
                await redis.delete(key)
                deleted_count += 1

            logger.info(
                "semantic_cache_clear_all",
                deleted_count=deleted_count,
                prefix=prefix,
            )
            return True

        except Exception as e:
            logger.warning(
                "semantic_cache_clear_error",
                prefix=prefix,
                error=str(e),
            )
            return False
