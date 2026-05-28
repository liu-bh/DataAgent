"""OpenAI 兼容客户端单元测试。

使用 mock httpx 测试非流式/流式调用、重试逻辑、成本计算。
"""

from __future__ import annotations

import json

import httpx
import pytest

from datapilot_llm.client import (
    LLMError,
    OpenAICompatibleClient,
    TokenUsage,
)


# ---------- 辅助函数 ----------


def _make_success_response(
    content: str = "SELECT 1",
    model: str = "qwen-turbo",
    prompt_tokens: int = 100,
    completion_tokens: int = 20,
) -> dict:
    """构造成功的 API 响应 JSON。"""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _make_stream_chunk(
    delta_content: str = "",
    finish_reason: str | None = None,
) -> str:
    """构造 SSE 流式数据块。"""
    data = {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "model": "qwen-turbo",
        "choices": [
            {
                "index": 0,
                "delta": {"content": delta_content} if delta_content else {},
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(data)}\n\n"


# ---------- TokenUsage 测试 ----------


class TestTokenUsage:
    """TokenUsage 测试。"""

    def test_total_tokens(self) -> None:
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50)
        assert usage.total_tokens == 150

    def test_zero_tokens(self) -> None:
        usage = TokenUsage(prompt_tokens=0, completion_tokens=0)
        assert usage.total_tokens == 0


# ---------- 成本计算测试 ----------


class TestCostCalculation:
    """成本计算测试。"""

    def test_uniform_cost(self) -> None:
        """统一计费（输入输出同价）。"""
        client = OpenAICompatibleClient(
            api_key="test",
            api_base="https://api.example.com/v1",
            cost_per_million_input=0.3,
            cost_per_million_output=0.3,
        )
        usage = TokenUsage(prompt_tokens=1000000, completion_tokens=500000)
        # (1M * 0.3 + 0.5M * 0.3) / 1M = 0.45
        cost = client._calculate_cost(usage)
        assert abs(cost - 0.45) < 1e-9

    def test_different_input_output_cost(self) -> None:
        """差异化计费（输入输出不同价，如 DeepSeek）。"""
        client = OpenAICompatibleClient(
            api_key="test",
            api_base="https://api.example.com/v1",
            cost_per_million_input=1.0,
            cost_per_million_output=2.0,
        )
        usage = TokenUsage(prompt_tokens=1000000, completion_tokens=500000)
        # (1M * 1.0 + 0.5M * 2.0) / 1M = 2.0
        cost = client._calculate_cost(usage)
        assert abs(cost - 2.0) < 1e-9

    def test_small_tokens(self) -> None:
        """少量 token 的成本计算。"""
        client = OpenAICompatibleClient(
            api_key="test",
            api_base="https://api.example.com/v1",
            cost_per_million_input=1.2,
            cost_per_million_output=1.2,
        )
        usage = TokenUsage(prompt_tokens=100, completion_tokens=20)
        cost = client._calculate_cost(usage)
        # (120 * 1.2) / 1M = 0.000144
        assert abs(cost - 0.000144) < 1e-10


# ---------- 重试判断测试 ----------


class TestRetryableStatus:
    """HTTP 状态码可重试判断测试。"""

    def test_5xx_retryable(self) -> None:
        assert OpenAICompatibleClient._is_retryable(500) is True
        assert OpenAICompatibleClient._is_retryable(502) is True
        assert OpenAICompatibleClient._is_retryable(503) is True

    def test_429_retryable(self) -> None:
        assert OpenAICompatibleClient._is_retryable(429) is True

    def test_4xx_not_retryable(self) -> None:
        assert OpenAICompatibleClient._is_retryable(400) is False
        assert OpenAICompatibleClient._is_retryable(401) is False
        assert OpenAICompatibleClient._is_retryable(403) is False
        assert OpenAICompatibleClient._is_retryable(404) is False

    def test_2xx_not_retryable(self) -> None:
        assert OpenAICompatibleClient._is_retryable(200) is False
        assert OpenAICompatibleClient._is_retryable(201) is False


# ---------- 非流式调用测试 ----------


class TestChatCompletion:
    """chat_completion 非流式调用测试。"""

    @pytest.mark.asyncio
    async def test_success_call(self) -> None:
        """成功调用返回正确结果。"""
        client = OpenAICompatibleClient(
            api_key="test-key",
            api_base="https://api.example.com/v1",
            max_retries=0,
        )

        response_json = _make_success_response()

        async def mock_post(*args, **kwargs):
            class MockResponse:
                def raise_for_status(self) -> None:
                    pass

                def json(self) -> dict:
                    return response_json

            return MockResponse()

        client._get_client = lambda: type(
            "C",
            (),
            {"post": mock_post},
        )()

        result = await client.chat_completion("qwen-turbo", "SELECT 1")
        assert result["content"] == "SELECT 1"
        assert result["prompt_tokens"] == 100
        assert result["completion_tokens"] == 20
        assert result["model"] == "qwen-turbo"
        assert result["cost"] > 0

    @pytest.mark.asyncio
    async def test_http_500_error_no_retry(self) -> None:
        """5xx 错误且 max_retries=0 时直接抛出。"""
        client = OpenAICompatibleClient(
            api_key="test-key",
            api_base="https://api.example.com/v1",
            max_retries=0,
        )

        class Mock500Response:
            status_code = 500
            text = "Internal Server Error"

            def raise_for_status(self) -> None:
                raise httpx.HTTPStatusError(
                    "500", request=httpx.Request("POST", "url"), response=self
                )

        async def mock_post(*args, **kwargs):
            return Mock500Response()

        mock_client = type("C", (), {"post": mock_post})()
        client._get_client = lambda: mock_client

        with pytest.raises(LLMError) as exc_info:
            await client.chat_completion("qwen-turbo", "test")
        assert exc_info.value.status_code == 500
        assert exc_info.value.retryable is True

    @pytest.mark.asyncio
    async def test_http_400_error_not_retryable(self) -> None:
        """4xx 错误不应重试。"""
        client = OpenAICompatibleClient(
            api_key="test-key",
            api_base="https://api.example.com/v1",
            max_retries=3,
        )

        call_count = 0

        class Mock400Response:
            status_code = 400
            text = "Bad Request"

            def raise_for_status(self) -> None:
                raise httpx.HTTPStatusError(
                    "400", request=httpx.Request("POST", "url"), response=self
                )

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return Mock400Response()

        mock_client = type("C", (), {"post": mock_post})()
        client._get_client = lambda: mock_client

        with pytest.raises(LLMError) as exc_info:
            await client.chat_completion("qwen-turbo", "test")
        assert exc_info.value.retryable is False
        # 4xx 不重试，只调用一次
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_json_mode_payload(self) -> None:
        """json_mode=True 时 payload 包含 response_format。"""
        client = OpenAICompatibleClient(
            api_key="test-key",
            api_base="https://api.example.com/v1",
            max_retries=0,
        )

        captured_payload = None

        response_json = _make_success_response()

        async def mock_post(*args, **kwargs):
            nonlocal captured_payload
            captured_payload = kwargs.get("json") or args[1] if len(args) > 1 else None

            class MockResponse:
                def raise_for_status(self) -> None:
                    pass

                def json(self) -> dict:
                    return response_json

            return MockResponse()

        mock_client = type("C", (), {"post": mock_post})()
        client._get_client = lambda: mock_client

        await client.chat_completion(
            "qwen-turbo", "test", json_mode=True
        )
        assert captured_payload is not None
        assert captured_payload.get("response_format") == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_system_prompt_in_messages(self) -> None:
        """system 参数正确添加到消息列表。"""
        client = OpenAICompatibleClient(
            api_key="test-key",
            api_base="https://api.example.com/v1",
            max_retries=0,
        )

        captured_payload = None

        response_json = _make_success_response()

        async def mock_post(*args, **kwargs):
            nonlocal captured_payload
            captured_payload = kwargs.get("json") or args[1] if len(args) > 1 else None

            class MockResponse:
                def raise_for_status(self) -> None:
                    pass

                def json(self) -> dict:
                    return response_json

            return MockResponse()

        mock_client = type("C", (), {"post": mock_post})()
        client._get_client = lambda: mock_client

        await client.chat_completion(
            "qwen-turbo", "hello", system="You are a SQL expert."
        )
        assert captured_payload is not None
        messages = captured_payload["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a SQL expert."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "hello"


# ---------- LLMError 测试 ----------


class TestLLMError:
    """LLMError 异常测试。"""

    def test_default_values(self) -> None:
        err = LLMError()
        assert err.message == "LLM 调用失败"
        assert err.status_code == 0
        assert err.model == ""
        assert err.retryable is False

    def test_custom_values(self) -> None:
        err = LLMError(
            message="API Key 无效",
            status_code=401,
            model="qwen-turbo",
            retryable=False,
        )
        assert err.message == "API Key 无效"
        assert err.status_code == 401
        assert err.model == "qwen-turbo"
        assert err.retryable is False

    def test_inherits_exception(self) -> None:
        err = LLMError()
        assert isinstance(err, Exception)

    def test_str_representation(self) -> None:
        err = LLMError(message="超时错误")
        assert str(err) == "超时错误"
