"""Embedding 客户端模块。

调用 OpenAI 兼容接口（text-embedding-v3）生成文本向量，支持批量向量化、
文本预处理、超时重试和 API 异常捕获。

用法::

    client = EmbeddingClient(
        api_base="https://api.example.com/v1",
        api_key="sk-xxx",
    )
    embedding = await client.embed_text("销售额")
    embeddings = await client.batch_embed_texts(["销售额", "订单量", "转化率"])
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

# 默认向量维度（text-embedding-v3 输出维度）
DEFAULT_EMBEDDING_DIM = 1536

# 默认模型名称
DEFAULT_EMBEDDING_MODEL = "text-embedding-v3"

# 最大单次请求文本条数（OpenAI 兼容接口通常限制 2048 条）
MAX_BATCH_SIZE = 200

# 文本最大长度（超过此长度将被截断）
MAX_TEXT_LENGTH = 8192

# HTTP 超时（秒）
DEFAULT_TIMEOUT = 30

# 最大重试次数
MAX_RETRIES = 3

# 重试间隔基数（秒），实际间隔 = base * (2 ** attempt)
RETRY_BACKOFF_BASE = 1.0


class EmbeddingError(Exception):
    """Embedding 调用异常。"""

    def __init__(self, message: str, detail: Any = None) -> None:
        self.message = message
        self.detail = detail
        super().__init__(self.message)


@dataclass
class EmbeddingConfig:
    """Embedding 客户端配置。

    Attributes:
        api_base: API 基础地址，如 https://api.example.com/v1。
        api_key: API 密钥。
        model: 模型名称，默认 text-embedding-v3。
        dimensions: 输出向量维度，默认 1536。
        timeout: HTTP 请求超时（秒）。
        max_retries: 最大重试次数。
        max_batch_size: 单次批量请求最大文本数。
        max_text_length: 单条文本最大长度（字符数）。
    """

    api_base: str
    api_key: str
    model: str = DEFAULT_EMBEDDING_MODEL
    dimensions: int = DEFAULT_EMBEDDING_DIM
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = MAX_RETRIES
    max_batch_size: int = MAX_BATCH_SIZE
    max_text_length: int = MAX_TEXT_LENGTH


class EmbeddingClient:
    """Embedding 客户端，调用 OpenAI 兼容接口生成文本向量。

    支持：
    - 单条文本向量化（embed_text）
    - 批量文本向量化（batch_embed_texts），自动分批
    - 文本预处理：截断过长文本、拼接 name + description
    - 超时重试（指数退避）
    - API 异常捕获与结构化日志记录
    """

    def __init__(
        self,
        api_base: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        """初始化 EmbeddingClient。

        Args:
            api_base: API 基础地址。默认从环境变量 EMBEDDING_API_BASE 读取。
            api_key: API 密钥。默认从环境变量 EMBEDDING_API_KEY 读取。
            model: 模型名称。默认从环境变量 EMBEDDING_MODEL 读取，否则 text-embedding-v3。
            dimensions: 输出向量维度。默认 1536。
            timeout: HTTP 请求超时（秒）。默认 30。
            max_retries: 最大重试次数。默认 3。
        """
        import os

        api_base = api_base or os.getenv("EMBEDDING_API_BASE", "")
        api_key = api_key or os.getenv("EMBEDDING_API_KEY", "")
        model = model or os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)

        if not api_base:
            raise EmbeddingError("EMBEDDING_API_BASE 未配置")
        if not api_key:
            raise EmbeddingError("EMBEDDING_API_KEY 未配置")

        self._config = EmbeddingConfig(
            api_base=api_base.rstrip("/"),
            api_key=api_key,
            model=model,
            dimensions=dimensions or DEFAULT_EMBEDDING_DIM,
            timeout=timeout or DEFAULT_TIMEOUT,
            max_retries=max_retries or MAX_RETRIES,
        )

        # httpx.AsyncClient 延迟初始化
        self._client: httpx.AsyncClient | None = None

    @property
    def config(self) -> EmbeddingConfig:
        """获取客户端配置。"""
        return self._config

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 httpx AsyncClient（懒初始化）。"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._config.api_base,
                headers={
                    "Authorization": f"Bearer {self._config.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self._config.timeout),
            )
        return self._client

    async def close(self) -> None:
        """关闭 HTTP 客户端。"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # 文本预处理
    # ------------------------------------------------------------------

    @staticmethod
    def prepare_text(
        name: str | None = None,
        description: str | None = None,
        max_length: int = MAX_TEXT_LENGTH,
    ) -> str:
        """拼接 name + description 并截断。

        将名称和描述拼接为 "name: description" 格式，用于向量化。
        如果拼接后超过 max_length，从末尾截断。

        Args:
            name: 实体名称（如指标名称）。
            description: 实体描述。
            max_length: 最大文本长度。

        Returns:
            拼接并截断后的文本。
        """
        parts: list[str] = []
        if name:
            parts.append(name.strip())
        if description:
            parts.append(description.strip())
        text = "：".join(parts) if parts else ""
        if len(text) > max_length:
            text = text[:max_length]
        return text

    @staticmethod
    def _truncate_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
        """截断文本到最大长度。

        Args:
            text: 原始文本。
            max_length: 最大字符数。

        Returns:
            截断后的文本。
        """
        if len(text) <= max_length:
            return text
        return text[:max_length]

    # ------------------------------------------------------------------
    # API 调用（含重试）
    # ------------------------------------------------------------------

    async def _call_api(
        self,
        texts: list[str],
        retry_count: int = 0,
    ) -> list[list[float]]:
        """调用 Embedding API（含指数退避重试）。

        Args:
            texts: 待向量化的文本列表。
            retry_count: 当前重试次数。

        Returns:
            与 texts 一一对应的向量列表。

        Raises:
            EmbeddingError: API 调用失败且重试耗尽。
        """
        client = await self._get_client()

        payload: dict[str, Any] = {
            "model": self._config.model,
            "input": texts,
            "dimensions": self._config.dimensions,
        }

        try:
            logger.debug(
                "embedding_api_request",
                model=self._config.model,
                text_count=len(texts),
                retry_count=retry_count,
            )

            response = await client.post(
                "/embeddings",
                json=payload,
            )
            response.raise_for_status()

            data = response.json()

            # 解析返回结果，按 index 排序确保顺序一致
            embeddings_data = sorted(data.get("data", []), key=lambda x: x["index"])

            # 校验返回数量
            if len(embeddings_data) != len(texts):
                logger.error(
                    "embedding_response_count_mismatch",
                    expected=len(texts),
                    actual=len(embeddings_data),
                )
                raise EmbeddingError(
                    f"Embedding 返回数量不匹配：期望 {len(texts)}，实际 {len(embeddings_data)}"
                )

            embeddings = [item["embedding"] for item in embeddings_data]

            # 校验向量维度
            for i, emb in enumerate(embeddings):
                if len(emb) != self._config.dimensions:
                    raise EmbeddingError(
                        f"向量维度不匹配：期望 {self._config.dimensions}，实际 {len(emb)}（第 {i} 条）"
                    )

            logger.debug(
                "embedding_api_success",
                model=self._config.model,
                text_count=len(texts),
            )

            return embeddings

        except httpx.TimeoutException as e:
            logger.warning(
                "embedding_api_timeout",
                model=self._config.model,
                retry_count=retry_count,
                max_retries=self._config.max_retries,
            )
            return await self._retry_or_raise(texts, retry_count, e)

        except httpx.HTTPStatusError as e:
            detail = f"HTTP {e.response.status_code}"
            try:
                body = e.response.json()
                detail = json.dumps(body, ensure_ascii=False)
            except Exception:
                detail = e.response.text[:500]

            logger.error(
                "embedding_api_http_error",
                status_code=e.response.status_code,
                detail=detail,
                retry_count=retry_count,
            )

            # 4xx 客户端错误不重试（认证失败、参数错误等）
            if 400 <= e.response.status_code < 500:
                raise EmbeddingError(
                    f"Embedding API 客户端错误: HTTP {e.response.status_code}",
                    detail={"status_code": e.response.status_code, "body": detail},
                ) from e

            return await self._retry_or_raise(texts, retry_count, e)

        except httpx.RequestError as e:
            logger.warning(
                "embedding_api_request_error",
                error=str(e),
                retry_count=retry_count,
            )
            return await self._retry_or_raise(texts, retry_count, e)

    async def _retry_or_raise(
        self,
        texts: list[str],
        retry_count: int,
        original_error: Exception,
    ) -> list[list[float]]:
        """判断是否重试或抛出异常。

        Args:
            texts: 原始文本列表。
            retry_count: 当前重试次数。
            original_error: 原始异常。

        Returns:
            API 返回的向量列表。

        Raises:
            EmbeddingError: 重试耗尽。
        """
        if retry_count < self._config.max_retries:
            # 指数退避
            delay = RETRY_BACKOFF_BASE * (2**retry_count)
            logger.info(
                "embedding_api_retry",
                retry_count=retry_count + 1,
                delay_seconds=delay,
            )
            await asyncio.sleep(delay)
            return await self._call_api(texts, retry_count + 1)

        raise EmbeddingError(
            f"Embedding API 调用失败（已重试 {self._config.max_retries} 次）: {original_error}",
            detail={"error_type": type(original_error).__name__, "error": str(original_error)},
        ) from original_error

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    async def embed_text(self, text: str) -> list[float]:
        """将单条文本转换为向量。

        Args:
            text: 待向量化的文本。

        Returns:
            维度为 dimensions 的浮点数列表。

        Raises:
            EmbeddingError: API 调用失败。
        """
        text = self._truncate_text(text, self._config.max_text_length)
        results = await self._call_api([text])
        return results[0]

    async def embed_entity(
        self,
        name: str | None = None,
        description: str | None = None,
    ) -> list[float]:
        """将实体（指标/维度/表）的 name + description 转换为向量。

        使用 prepare_text 拼接名称和描述后再向量化。

        Args:
            name: 实体名称。
            description: 实体描述。

        Returns:
            维度为 dimensions 的浮点数列表。

        Raises:
            EmbeddingError: API 调用失败。
        """
        text = self.prepare_text(name=name, description=description)
        return await self.embed_text(text)

    async def batch_embed_texts(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """批量将文本转换为向量，自动分批。

        当文本数量超过 max_batch_size 时，自动拆分为多个批次并发请求。

        Args:
            texts: 待向量化的文本列表。

        Returns:
            与 texts 一一对应的向量列表。

        Raises:
            EmbeddingError: 任一批次 API 调用失败。
        """
        if not texts:
            return []

        # 预处理：截断文本
        truncated = [self._truncate_text(t, self._config.max_text_length) for t in texts]

        # 分批
        batches: list[list[str]] = []
        for i in range(0, len(truncated), self._config.max_batch_size):
            batches.append(truncated[i : i + self._config.max_batch_size])

        # 并发调用
        results = await asyncio.gather(
            *[self._call_api(batch) for batch in batches],
            return_exceptions=True,
        )

        # 合并结果，检查异常
        all_embeddings: list[list[float]] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                raise EmbeddingError(
                    f"批量 Embedding 第 {i} 批调用失败: {result}",
                    detail={"batch_index": i, "error": str(result)},
                ) from result
            all_embeddings.extend(result)

        return all_embeddings

    async def batch_embed_entities(
        self,
        entities: list[dict[str, str | None]],
    ) -> list[list[float]]:
        """批量将实体转换为向量。

        每个实体为 dict，包含 name 和 description 可选字段。

        Args:
            entities: 实体列表，每个实体为 {"name": ..., "description": ...}。

        Returns:
            与 entities 一一对应的向量列表。

        Raises:
            EmbeddingError: API 调用失败。
        """
        texts = [
            self.prepare_text(
                name=entity.get("name"),
                description=entity.get("description"),
            )
            for entity in entities
        ]
        return await self.batch_embed_texts(texts)
