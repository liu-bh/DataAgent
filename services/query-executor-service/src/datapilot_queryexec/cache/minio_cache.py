"""MinIO 查询结果缓存。

使用 minio 异步客户端将大结果集（>=1MB）缓存到 MinIO 对象存储，
支持优雅降级（MinIO 不可用时返回 None 并记录警告）。
"""

from __future__ import annotations

from io import BytesIO

import structlog
from minio import Minio as SyncMinio

logger = structlog.get_logger(__name__)


class MinIOResultCache:
    """MinIO 结果缓存客户端。

    对 minio 同步客户端进行封装（在线程池中运行以模拟 async），
    提供 get / set / delete / exists 操作。
    所有方法均为 async，在 MinIO 不可用时优雅降级。

    Args:
        endpoint: MinIO 服务地址，默认 ``localhost:9000``。
        access_key: 访问密钥，默认 ``minioadmin``。
        secret_key: 密钥，默认 ``minioadmin``。
        bucket_name: 存储桶名称，默认 ``query-cache``。
        secure: 是否使用 HTTPS，默认 False。
    """

    def __init__(
        self,
        endpoint: str = "localhost:9000",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin",
        bucket_name: str = "query-cache",
        secure: bool = False,
    ) -> None:
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._bucket_name = bucket_name
        self._secure = secure
        self._client: SyncMinio | None = None

    def _ensure_client(self) -> SyncMinio | None:
        """确保 MinIO 客户端已初始化，失败时返回 None。"""
        if self._client is not None:
            return self._client
        try:
            self._client = SyncMinio(
                endpoint=self._endpoint,
                access_key=self._access_key,
                secret_key=self._secret_key,
                secure=self._secure,
            )
            # 测试连接
            self._client.list_buckets()
            logger.info("MinIO 客户端连接成功", endpoint=self._endpoint)
            return self._client
        except Exception as exc:
            logger.warning(
                "MinIO 连接失败，缓存将降级为不可用",
                endpoint=self._endpoint,
                error=str(exc),
            )
            self._client = None
            return None

    async def ensure_bucket(self) -> None:
        """确保缓存存储桶存在，不存在则创建。"""
        import asyncio

        def _do_ensure() -> None:
            client = self._ensure_client()
            if client is None:
                return
            if not client.bucket_exists(self._bucket_name):
                client.make_bucket(self._bucket_name)
                logger.info("MinIO 存储桶创建成功", bucket=self._bucket_name)
            else:
                logger.debug("MinIO 存储桶已存在", bucket=self._bucket_name)

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _do_ensure)
        except Exception as exc:
            logger.warning("确保 MinIO 存储桶存在时失败", error=str(exc))

    async def get(self, key: str) -> bytes | None:
        """从 MinIO 获取缓存数据。

        Args:
            key: 缓存 key，同时作为对象名称使用。

        Returns:
            缓存的原始字节数据，不存在或 MinIO 不可用时返回 None。
        """
        import asyncio

        def _do_get() -> bytes | None:
            client = self._ensure_client()
            if client is None:
                return None
            try:
                response = client.get_object(self._bucket_name, key)
                data = response.read()
                response.close()
                response.release_conn()
                logger.debug("MinIO 缓存命中", key=key, size_bytes=len(data))
                return data
            except Exception as exc:
                logger.debug("MinIO 缓存未命中", key=key, error=str(exc))
                return None

        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, _do_get)
        except Exception as exc:
            logger.warning("MinIO GET 操作失败，降级返回 None", key=key, error=str(exc))
            return None

    async def set(self, key: str, data: bytes) -> bool:
        """将数据写入 MinIO 缓存。

        Args:
            key: 缓存 key，同时作为对象名称使用。
            data: 要缓存的原始字节数据。

        Returns:
            写入成功返回 True，失败返回 False。
        """
        import asyncio

        def _do_set() -> bool:
            client = self._ensure_client()
            if client is None:
                return False
            try:
                data_stream = BytesIO(data)
                client.put_object(
                    bucket_name=self._bucket_name,
                    object_name=key,
                    data=data_stream,
                    length=len(data),
                )
                logger.debug(
                    "MinIO 缓存写入成功",
                    key=key,
                    size_bytes=len(data),
                    bucket=self._bucket_name,
                )
                return True
            except Exception as exc:
                logger.warning("MinIO SET 操作失败", key=key, error=str(exc))
                return False

        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, _do_set)
        except Exception as exc:
            logger.warning("MinIO SET 操作失败，降级返回 False", key=key, error=str(exc))
            return False

    async def delete(self, key: str) -> bool:
        """从 MinIO 删除缓存。

        Args:
            key: 缓存 key。

        Returns:
            删除成功返回 True，失败返回 False。
        """
        import asyncio

        def _do_delete() -> bool:
            client = self._ensure_client()
            if client is None:
                return False
            try:
                client.remove_object(self._bucket_name, key)
                logger.debug("MinIO 缓存删除成功", key=key)
                return True
            except Exception as exc:
                logger.warning("MinIO DELETE 操作失败", key=key, error=str(exc))
                return False

        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, _do_delete)
        except Exception as exc:
            logger.warning("MinIO DELETE 操作失败，降级返回 False", key=key, error=str(exc))
            return False

    async def exists(self, key: str) -> bool:
        """检查 MinIO 中是否存在指定对象。

        Args:
            key: 缓存 key。

        Returns:
            存在返回 True，否则返回 False。
        """
        import asyncio

        def _do_exists() -> bool:
            client = self._ensure_client()
            if client is None:
                return False
            try:
                client.stat_object(self._bucket_name, key)
                return True
            except Exception:
                return False

        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, _do_exists)
        except Exception as exc:
            logger.warning("MinIO EXISTS 操作失败，降级返回 False", key=key, error=str(exc))
            return False

    async def close(self) -> None:
        """关闭 MinIO 客户端。"""
        self._client = None
        logger.info("MinIO 客户端已释放")
