"""EmbeddingClient 单元测试。

测试内容:
- 文本预处理（prepare_text, _truncate_text）
- API 调用（mock httpx）
- 批量向量化（自动分批）
- 超时重试（指数退避）
- API 异常处理
"""

from __future__ import annotations

import json
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 文本预处理测试
# ---------------------------------------------------------------------------


class TestPrepareText:
    """EmbeddingClient.prepare_text 文本预处理测试。"""

    def test_name_only(self) -> None:
        """测试仅传入 name。"""
        from datapilot_semantic.retrieval.embedding import EmbeddingClient

        result = EmbeddingClient.prepare_text(name="销售额")
        assert result == "销售额"

    def test_name_and_description(self) -> None:
        """测试传入 name 和 description。"""
        from datapilot_semantic.retrieval.embedding import EmbeddingClient

        result = EmbeddingClient.prepare_text(
            name="销售额",
            description="所有订单的金额总和",
        )
        assert result == "销售额：所有订单的金额总和"

    def test_description_only(self) -> None:
        """测试仅传入 description。"""
        from datapilot_semantic.retrieval.embedding import EmbeddingClient

        result = EmbeddingClient.prepare_text(description="订单金额总和")
        assert result == "订单金额总和"

    def test_empty_inputs(self) -> None:
        """测试空输入。"""
        from datapilot_semantic.retrieval.embedding import EmbeddingClient

        result = EmbeddingClient.prepare_text(name=None, description=None)
        assert result == ""

    def test_whitespace_stripping(self) -> None:
        """测试前后空格被移除。"""
        from datapilot_semantic.retrieval.embedding import EmbeddingClient

        result = EmbeddingClient.prepare_text(name="  销售额  ", description="  描述  ")
        assert result == "销售额：描述"

    def test_truncation(self) -> None:
        """测试超长文本截断。"""
        from datapilot_semantic.retrieval.embedding import EmbeddingClient

        long_text = "x" * 10000
        result = EmbeddingClient.prepare_text(
            name=long_text,
            description=long_text,
            max_length=100,
        )
        assert len(result) <= 100


class TestTruncateText:
    """EmbeddingClient._truncate_text 截断测试。"""

    def test_no_truncation_needed(self) -> None:
        """测试不需要截断的情况。"""
        from datapilot_semantic.retrieval.embedding import EmbeddingClient

        text = "短文本"
        result = EmbeddingClient._truncate_text(text, max_length=100)
        assert result == text

    def test_truncation(self) -> None:
        """测试截断。"""
        from datapilot_semantic.retrieval.embedding import EmbeddingClient

        text = "a" * 200
        result = EmbeddingClient._truncate_text(text, max_length=100)
        assert len(result) == 100

    def test_exact_length(self) -> None:
        """测试恰好等于最大长度时不截断。"""
        from datapilot_semantic.retrieval.embedding import EmbeddingClient

        text = "a" * 100
        result = EmbeddingClient._truncate_text(text, max_length=100)
        assert result == text


# ---------------------------------------------------------------------------
# 客户端初始化测试
# ---------------------------------------------------------------------------


class TestEmbeddingClientInit:
    """EmbeddingClient 初始化测试。"""

    def test_init_with_env_vars(self) -> None:
        """测试从环境变量初始化。"""
        os.environ["EMBEDDING_API_BASE"] = "https://api.example.com/v1"
        os.environ["EMBEDDING_API_KEY"] = "test-key-123"

        from datapilot_semantic.retrieval.embedding import EmbeddingClient

        client = EmbeddingClient()
        assert client.config.api_base == "https://api.example.com/v1"
        assert client.config.api_key == "test-key-123"

    def test_init_with_params(self) -> None:
        """测试通过参数初始化。"""
        os.environ["EMBEDDING_API_BASE"] = "https://default.com"
        os.environ["EMBEDDING_API_KEY"] = "default-key"

        from datapilot_semantic.retrieval.embedding import EmbeddingClient

        client = EmbeddingClient(
            api_base="https://custom.com/v1",
            api_key="custom-key",
        )
        assert client.config.api_base == "https://custom.com/v1"
        assert client.config.api_key == "custom-key"

    def test_init_missing_api_base(self) -> None:
        """测试缺少 API_BASE 时抛出异常。"""
        os.environ.pop("EMBEDDING_API_BASE", None)
        os.environ["EMBEDDING_API_KEY"] = "test-key"

        from datapilot_semantic.retrieval.embedding import EmbeddingClient, EmbeddingError

        with pytest.raises(EmbeddingError, match="EMBEDDING_API_BASE"):
            EmbeddingClient()

    def test_init_missing_api_key(self) -> None:
        """测试缺少 API_KEY 时抛出异常。"""
        os.environ["EMBEDDING_API_BASE"] = "https://api.example.com"
        os.environ.pop("EMBEDDING_API_KEY", None)

        from datapilot_semantic.retrieval.embedding import EmbeddingClient, EmbeddingError

        with pytest.raises(EmbeddingError, match="EMBEDDING_API_KEY"):
            EmbeddingClient()

    def test_init_strips_trailing_slash(self) -> None:
        """测试 API_BASE 末尾斜杠被移除。"""
        os.environ["EMBEDDING_API_BASE"] = "https://api.example.com/v1/"
        os.environ["EMBEDDING_API_KEY"] = "test-key"

        from datapilot_semantic.retrieval.embedding import EmbeddingClient

        client = EmbeddingClient()
        assert client.config.api_base == "https://api.example.com/v1"


# ---------------------------------------------------------------------------
# API 调用测试（mock httpx）
# ---------------------------------------------------------------------------


class TestEmbeddingAPICall:
    """Embedding API 调用测试（mock httpx）。"""

    def _make_client(self) -> "EmbeddingClient":
        """创建测试用 EmbeddingClient。"""
        os.environ["EMBEDDING_API_BASE"] = "https://api.example.com/v1"
        os.environ["EMBEDDING_API_KEY"] = "test-key"

        from datapilot_semantic.retrieval.embedding import EmbeddingClient

        client = EmbeddingClient()
        return client

    def _mock_response(self, embeddings: list[list[float]]) -> MagicMock:
        """构建 mock 的 API 响应。"""
        data = {
            "data": [
                {"object": "embedding", "index": i, "embedding": emb}
                for i, emb in enumerate(embeddings)
            ]
        }
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = data
        response.raise_for_status = MagicMock()
        return response

    @pytest.mark.asyncio
    async def test_embed_text_success(self) -> None:
        """测试单条文本向量化成功。"""
        client = self._make_client()
        expected = [0.1] * 1536

        mock_response = self._mock_response([expected])
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.embed_text("销售额")

        assert result == expected
        assert len(result) == 1536

    @pytest.mark.asyncio
    async def test_embed_entity_success(self) -> None:
        """测试实体向量化成功。"""
        client = self._make_client()
        expected = [0.2] * 1536

        mock_response = self._mock_response([expected])
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.embed_entity(
                name="GMV",
                description="商品交易总额",
            )

        assert result == expected

    @pytest.mark.asyncio
    async def test_batch_embed_texts_success(self) -> None:
        """测试批量向量化成功。"""
        client = self._make_client()
        embeddings = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]

        mock_response = self._mock_response(embeddings)
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_client):
            results = await client.batch_embed_texts(["销售额", "订单量", "转化率"])

        assert len(results) == 3
        assert results[0] == [0.1] * 1536
        assert results[1] == [0.2] * 1536
        assert results[2] == [0.3] * 1536

    @pytest.mark.asyncio
    async def test_batch_embed_texts_auto_split(self) -> None:
        """测试批量向量化自动分批。"""
        client = self._make_client()
        # 设置小的 batch size 来触发分批
        client._config.max_batch_size = 2

        texts = ["a", "b", "c"]
        embeddings = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]

        mock_client = AsyncMock()
        mock_response_1 = self._mock_response(embeddings[:2])
        mock_response_2 = self._mock_response(embeddings[2:])
        mock_client.post.side_effect = [mock_response_1, mock_response_2]

        with patch.object(client, "_get_client", return_value=mock_client):
            results = await client.batch_embed_texts(texts)

        assert len(results) == 3
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_batch_embed_texts_empty(self) -> None:
        """测试空列表返回空结果。"""
        client = self._make_client()

        results = await client.batch_embed_texts([])
        assert results == []

    @pytest.mark.asyncio
    async def test_embed_text_truncates_long_text(self) -> None:
        """测试超长文本被截断。"""
        client = self._make_client()
        client._config.max_text_length = 100

        long_text = "x" * 10000
        expected = [0.1] * 1536

        mock_response = self._mock_response([expected])
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.embed_text(long_text)

        assert result == expected
        # 验证传入 API 的文本被截断
        call_args = mock_client.post.call_args
        sent_text = call_args.kwargs["json"]["input"][0]
        assert len(sent_text) <= 100


# ---------------------------------------------------------------------------
# 错误处理测试
# ---------------------------------------------------------------------------


class TestEmbeddingErrorHandling:
    """Embedding 错误处理测试。"""

    def _make_client(self) -> "EmbeddingClient":
        """创建测试用 EmbeddingClient。"""
        os.environ["EMBEDDING_API_BASE"] = "https://api.example.com/v1"
        os.environ["EMBEDDING_API_KEY"] = "test-key"

        from datapilot_semantic.retrieval.embedding import EmbeddingClient

        client = EmbeddingClient()
        return client

    @pytest.mark.asyncio
    async def test_api_timeout_retries(self) -> None:
        """测试 API 超时时触发重试。"""
        client = self._make_client()
        client._config.max_retries = 2

        mock_client = AsyncMock()

        import httpx

        # 前两次超时，第三次成功
        embeddings = [[0.1] * 1536]
        mock_response = self._make_mock_success_response(embeddings)
        mock_client.post.side_effect = [
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
            mock_response,
        ]

        with patch.object(client, "_get_client", return_value=mock_client):
            with patch("datapilot_semantic.retrieval.embedding.asyncio.sleep", new_callable=AsyncMock):
                result = await client.embed_text("test")

        assert result == [0.1] * 1536
        assert mock_client.post.call_count == 3

    @staticmethod
    def _make_mock_success_response(embeddings: list[list[float]]) -> MagicMock:
        """构建成功的 mock 响应。"""
        data = {
            "data": [
                {"object": "embedding", "index": i, "embedding": emb}
                for i, emb in enumerate(embeddings)
            ]
        }
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = data
        response.raise_for_status = MagicMock()
        return response

    @pytest.mark.asyncio
    async def test_api_4xx_no_retry(self) -> None:
        """测试 4xx 错误不重试。"""
        client = self._make_client()
        client._config.max_retries = 3

        import httpx

        from datapilot_semantic.retrieval.embedding import EmbeddingError

        error_response = MagicMock()
        error_response.status_code = 401
        error_response.json.return_value = {"error": "invalid_api_key"}
        error_response.text = '{"error": "invalid_api_key"}'

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=error_response,
        )

        with patch.object(client, "_get_client", return_value=mock_client):
            with pytest.raises(EmbeddingError, match="客户端错误"):
                await client.embed_text("test")

        # 4xx 不应重试
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_api_retries_exhausted(self) -> None:
        """测试重试耗尽后抛出异常。"""
        client = self._make_client()
        client._config.max_retries = 1

        import httpx

        from datapilot_semantic.retrieval.embedding import EmbeddingError

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")

        with patch.object(client, "_get_client", return_value=mock_client):
            with patch("datapilot_semantic.retrieval.embedding.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(EmbeddingError, match="调用失败"):
                    await client.embed_text("test")

    @pytest.mark.asyncio
    async def test_response_count_mismatch(self) -> None:
        """测试返回数量不匹配时抛出异常。"""
        client = self._make_client()

        from datapilot_semantic.retrieval.embedding import EmbeddingError

        # 返回 1 条但请求 2 条
        data = {
            "data": [
                {"object": "embedding", "index": 0, "embedding": [0.1] * 1536}
            ]
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_client):
            with pytest.raises(EmbeddingError, match="数量不匹配"):
                await client.embed_text("test1")
                # batch_embed_texts 会请求 2 条
                await client.batch_embed_texts(["test1", "test2"])

    @pytest.mark.asyncio
    async def test_dimension_mismatch(self) -> None:
        """测试返回维度不匹配时抛出异常。"""
        client = self._make_client()

        from datapilot_semantic.retrieval.embedding import EmbeddingError

        # 返回 768 维而非 1536 维
        data = {
            "data": [
                {"object": "embedding", "index": 0, "embedding": [0.1] * 768}
            ]
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(client, "_get_client", return_value=mock_client):
            with pytest.raises(EmbeddingError, match="维度不匹配"):
                await client.embed_text("test")

    @pytest.mark.asyncio
    async def test_batch_partial_failure(self) -> None:
        """测试批量调用中某一批失败。"""
        client = self._make_client()

        import httpx

        from datapilot_semantic.retrieval.embedding import EmbeddingError

        mock_client = AsyncMock()

        # 第一批成功，第二批失败
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "data": [{"index": 0, "embedding": [0.1] * 1536}]
        }
        success_response.raise_for_status = MagicMock()

        mock_client.post.side_effect = [
            success_response,
            httpx.TimeoutException("timeout"),
        ]

        # 设置小的 batch size 触发分批
        client._config.max_batch_size = 1

        with patch.object(client, "_get_client", return_value=mock_client):
            with patch("datapilot_semantic.retrieval.embedding.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(EmbeddingError, match="第 1 批调用失败"):
                    await client.batch_embed_texts(["a", "b"])
