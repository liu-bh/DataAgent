"""Redis 查询结果缓存。

使用 redis.asyncio 客户端将小结果集（<1MB）缓存到 Redis，
支持 TTL 过期和优雅降级（Redis 不可用时返回 None 并记录警告）。
"""

from __future__ import annotations

import structlog
from redis.asyncio import ConnectionPool, Redis

logger = structlog.get_logger(__name__)


class RedisResultCache:
    """Redis 结果缓存客户端。

    对 redis.asyncio 进行封装，提供 get / set / delete / exists / get_ttl 操作。
    所有方法均为 async，在 Redis 连接失败时优雅降级。

    Args:
        redis_url: Redis 连接 URL，默认 ``redis://localhost:6379/0``。
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis_url = redis_url
        self._pool: ConnectionPool | None = None
        self._client: Redis | None = None

    async def _ensure_client(self) -> Redis | None:
        """确保 Redis 客户端已初始化，失败时返回 None。"""
        if self._client is not None:
            return self._client
        try:
            self._pool = ConnectionPool.from_url(self._redis_url, decode_responses=False)
            self._client = Redis(connection_pool=self._pool)
            # 测试连接
            await self._client.ping()
            logger.info("Redis 客户端连接成功", url=self._redis_url)
            return self._client
        except Exception as exc:
            logger.warning(
                "Redis 连接失败，缓存将降级为不可用",
                url=self._redis_url,
                error=str(exc),
            )
            self._pool = None
            self._client = None
            return None

    async def get(self, key: str) -> bytes | None:
        """从 Redis 获取缓存数据。

        Args:
            key: 缓存 key。

        Returns:
            缓存的原始字节数据，不存在或 Redis 不可用时返回 None。
        """
        client = await self._ensure_client()
        if client is None:
            return None
        try:
            result = await client.get(key)
            if result is not None:
                logger.debug("Redis 缓存命中", key=key)
            else:
                logger.debug("Redis 缓存未命中", key=key)
            return result
        except Exception as exc:
            logger.warning("Redis GET 操作失败，降级返回 None", key=key, error=str(exc))
            return None

    async def set(self, key: str, data: bytes, ttl_seconds: int = 300) -> bool:
        """将数据写入 Redis 缓存。

        Args:
            key: 缓存 key。
            data: 要缓存的原始字节数据。
            ttl_seconds: 过期时间（秒），默认 300。

        Returns:
            写入成功返回 True，失败返回 False。
        """
        client = await self._ensure_client()
        if client is None:
            return False
        try:
            await client.set(key, data, ex=ttl_seconds)
            logger.debug(
                "Redis 缓存写入成功",
                key=key,
                size_bytes=len(data),
                ttl_seconds=ttl_seconds,
            )
            return True
        except Exception as exc:
            logger.warning("Redis SET 操作失败", key=key, error=str(exc))
            return False

    async def delete(self, key: str) -> bool:
        """从 Redis 删除缓存。

        Args:
            key: 缓存 key。

        Returns:
            删除成功返回 True，失败返回 False。
        """
        client = await self._ensure_client()
        if client is None:
            return False
        try:
            result = await client.delete(key)
            logger.debug("Redis 缓存删除", key=key, deleted=result)
            return bool(result)
        except Exception as exc:
            logger.warning("Redis DELETE 操作失败", key=key, error=str(exc))
            return False

    async def exists(self, key: str) -> bool:
        """检查 Redis 中是否存在指定 key。

        Args:
            key: 缓存 key。

        Returns:
            存在返回 True，否则返回 False。
        """
        client = await self._ensure_client()
        if client is None:
            return False
        try:
            result = await client.exists(key)
            return bool(result)
        except Exception as exc:
            logger.warning("Redis EXISTS 操作失败", key=key, error=str(exc))
            return False

    async def get_ttl(self, key: str) -> int:
        """获取 Redis key 的剩余 TTL（秒）。

        Args:
            key: 缓存 key。

        Returns:
            剩余秒数；key 不存在返回 -2，无过期时间返回 -1，异常返回 -3。
        """
        client = await self._ensure_client()
        if client is None:
            return -3
        try:
            return await client.ttl(key)
        except Exception as exc:
            logger.warning("Redis TTL 操作失败", key=key, error=str(exc))
            return -3

    async def close(self) -> None:
        """关闭 Redis 连接。"""
        if self._client is not None:
            try:
                await self._client.aclose()
                logger.info("Redis 客户端连接已关闭")
            except Exception as exc:
                logger.warning("关闭 Redis 客户端时出错", error=str(exc))
            finally:
                self._client = None
                self._pool = None
