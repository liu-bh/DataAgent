"""Provider 协议接口与数据模型单元测试。"""

from __future__ import annotations

import pytest

from datapilot_llm.provider import BaseProvider, LLMChunk, LLMResponse


class TestLLMResponse:
    """LLMResponse 数据模型测试。"""

    def test_default_values(self) -> None:
        """默认值初始化。"""
        resp = LLMResponse(content="hello")
        assert resp.content == "hello"
        assert resp.prompt_tokens == 0
        assert resp.completion_tokens == 0
        assert resp.model == ""
        assert resp.latency_ms == 0.0
        assert resp.cost == 0.0

    def test_full_initialization(self) -> None:
        """完整参数初始化。"""
        resp = LLMResponse(
            content="SELECT 1",
            prompt_tokens=100,
            completion_tokens=20,
            model="qwen-turbo",
            latency_ms=500.5,
            cost=0.000036,
        )
        assert resp.content == "SELECT 1"
        assert resp.prompt_tokens == 100
        assert resp.completion_tokens == 20
        assert resp.model == "qwen-turbo"
        assert resp.latency_ms == 500.5
        assert resp.cost == 0.000036

    def test_total_tokens(self) -> None:
        """total_tokens 属性计算正确。"""
        resp = LLMResponse(content="", prompt_tokens=100, completion_tokens=50)
        assert resp.total_tokens == 150

    def test_total_tokens_zero(self) -> None:
        """total_tokens 在默认值时为 0。"""
        resp = LLMResponse(content="")
        assert resp.total_tokens == 0


class TestLLMChunk:
    """LLMChunk 数据模型测试。"""

    def test_default_values(self) -> None:
        """默认 finish_reason 为 None。"""
        chunk = LLMChunk(delta_content="hello")
        assert chunk.delta_content == "hello"
        assert chunk.finish_reason is None

    def test_with_finish_reason(self) -> None:
        """设置 finish_reason。"""
        chunk = LLMChunk(delta_content="", finish_reason="stop")
        assert chunk.delta_content == ""
        assert chunk.finish_reason == "stop"

    def test_various_finish_reasons(self) -> None:
        """各种 finish_reason 值。"""
        for reason in ("stop", "length", "content_filter", None):
            chunk = LLMChunk(delta_content="", finish_reason=reason)
            assert chunk.finish_reason == reason


class TestBaseProvider:
    """BaseProvider 抽象基类测试。"""

    def test_cannot_instantiate(self) -> None:
        """BaseProvider 是抽象类，不能直接实例化。"""
        with pytest.raises(TypeError):
            BaseProvider()  # type: ignore[abstract]

    def test_concrete_provider_implements_interface(self) -> None:
        """具体 Provider 实现所有抽象方法后可实例化。"""

        class MockProvider(BaseProvider):
            @property
            def provider_name(self) -> str:
                return "mock"

            async def generate(
                self,
                prompt: str,
                *,
                system: str | None = None,
                temperature: float = 0.7,
                max_tokens: int = 4096,
                stop: list[str] | None = None,
            ) -> LLMResponse:
                return LLMResponse(content="mock response", model="mock")

            async def generate_stream(
                self,
                prompt: str,
                *,
                system: str | None = None,
                temperature: float = 0.7,
                max_tokens: int = 4096,
                stop: list[str] | None = None,
            ):
                yield LLMChunk(delta_content="mock")

        provider = MockProvider()
        assert provider.provider_name == "mock"

    def test_provider_name_is_abstract(self) -> None:
        """provider_name 是抽象属性，子类必须实现。"""
        with pytest.raises(TypeError):

            class IncompleteProvider(BaseProvider):
                async def generate(self, prompt, **kwargs):
                    return LLMResponse(content="")

                async def generate_stream(self, prompt, **kwargs):
                    yield LLMChunk(delta_content="")

            IncompleteProvider()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_mock_provider_generate(self) -> None:
        """Mock Provider 的 generate 方法返回正确结果。"""

        class MockProvider(BaseProvider):
            @property
            def provider_name(self) -> str:
                return "mock"

            async def generate(self, prompt, **kwargs) -> LLMResponse:
                return LLMResponse(
                    content=f"response to: {prompt}",
                    model=self.provider_name,
                )

            async def generate_stream(self, prompt, **kwargs):
                yield LLMChunk(delta_content="stream")

        provider = MockProvider()
        resp = await provider.generate("hello")
        assert resp.content == "response to: hello"
        assert resp.model == "mock"

    @pytest.mark.asyncio
    async def test_mock_provider_generate_stream(self) -> None:
        """Mock Provider 的 generate_stream 方法返回正确结果。"""

        class MockProvider(BaseProvider):
            @property
            def provider_name(self) -> str:
                return "mock"

            async def generate(self, prompt, **kwargs) -> LLMResponse:
                return LLMResponse(content="")

            async def generate_stream(self, prompt, **kwargs):
                for word in prompt.split():
                    yield LLMChunk(delta_content=f"{word} ")
                yield LLMChunk(delta_content="", finish_reason="stop")

        provider = MockProvider()
        chunks = []
        async for chunk in provider.generate_stream("hello world"):
            chunks.append(chunk)

        assert len(chunks) == 3
        assert chunks[0].delta_content == "hello "
        assert chunks[1].delta_content == "world "
        assert chunks[2].finish_reason == "stop"
