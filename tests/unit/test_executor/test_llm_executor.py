"""LLM 任务执行器单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datapilot_dag.executor.llm_executor import LLMTaskExecutor


class TestLLMTaskExecutor:
    """LLMTaskExecutor 测试。"""

    def test_init_without_router(self) -> None:
        """不传入 router 时 llm_router 为 None。"""
        executor = LLMTaskExecutor()
        assert executor._llm_router is None

    def test_init_with_router(self) -> None:
        """传入 router 时正确保存。"""
        mock_router = MagicMock()
        executor = LLMTaskExecutor(llm_router=mock_router)
        assert executor._llm_router is mock_router

    @pytest.mark.asyncio
    async def test_execute_without_router_returns_mock(self) -> None:
        """没有 router 时返回 mock 结果。"""
        executor = LLMTaskExecutor()

        result = await executor.execute(
            node_id="llm-1",
            config={
                "prompt": "解释这个 SQL",
                "scene": "explanation",
                "response_format": "text",
            },
            context={},
        )

        assert result["mock"] is True
        assert "content" in result
        assert result["scene"] == "explanation"

    @pytest.mark.asyncio
    async def test_execute_without_router_json_format(self) -> None:
        """没有 router 时 json 格式返回 mock 结果。"""
        executor = LLMTaskExecutor()

        result = await executor.execute(
            node_id="llm-1",
            config={
                "prompt": "分析意图",
                "scene": "intent",
                "response_format": "json",
            },
            context={},
        )

        assert result["mock"] is True
        assert "content" in result
        assert "result" in result["content"]

    @pytest.mark.asyncio
    async def test_execute_with_router_calls_generate(self) -> None:
        """有 router 时调用 generate 方法。"""
        mock_response = MagicMock()
        mock_response.content = "SQL 解释结果"
        mock_response.model = "qwen-plus"
        mock_response.latency_ms = 500.0

        mock_router = AsyncMock()
        mock_router.generate = AsyncMock(return_value=mock_response)

        executor = LLMTaskExecutor(llm_router=mock_router)

        with patch("datapilot_dag.executor.llm_executor.Scene", create=True) as mock_scene:
            mock_scene.return_value = "explanation"
            result = await executor.execute(
                node_id="llm-1",
                config={
                    "prompt": "解释 SQL",
                    "scene": "explanation",
                    "response_format": "text",
                },
                context={},
            )

        mock_router.generate.assert_called_once()
        assert result == "SQL 解释结果"

    @pytest.mark.asyncio
    async def test_execute_with_router_json_mode(self) -> None:
        """有 router 时 json 格式传递 json_mode=True。"""
        mock_response = MagicMock()
        mock_response.content = '{"result": "ok"}'
        mock_response.model = "qwen-plus"
        mock_response.latency_ms = 300.0

        mock_router = AsyncMock()
        mock_router.generate = AsyncMock(return_value=mock_response)

        executor = LLMTaskExecutor(llm_router=mock_router)

        with patch("datapilot_dag.executor.llm_executor.Scene", create=True) as mock_scene:
            mock_scene.return_value = "intent"
            await executor.execute(
                node_id="llm-1",
                config={
                    "prompt": "分析意图",
                    "scene": "intent",
                    "response_format": "json",
                },
                context={},
            )

        # 验证 generate 调用参数包含 json_mode
        call_kwargs = mock_router.generate.call_args[1]
        assert call_kwargs["json_mode"] is True

    @pytest.mark.asyncio
    async def test_cancel(self) -> None:
        """取消任务。"""
        executor = LLMTaskExecutor()
        result = await executor.cancel("llm-1")
        assert result is True
        assert "llm-1" in executor._cancelled_tasks

    @pytest.mark.asyncio
    async def test_execute_cancelled_node_raises(self) -> None:
        """已取消的节点执行时抛出异常。"""
        executor = LLMTaskExecutor()
        await executor.cancel("llm-1")

        with pytest.raises(RuntimeError, match="已被取消"):
            await executor.execute(
                node_id="llm-1",
                config={"prompt": "test", "scene": "chitchat", "response_format": "text"},
                context={},
            )

    def test_mock_result_text(self) -> None:
        """文本格式 mock 结果。"""
        result = LLMTaskExecutor._mock_result("你好", "chitchat", "text")
        assert result["mock"] is True
        assert "content" in result
        assert result["scene"] == "chitchat"
        assert "你好" in result["content"]

    def test_mock_result_json(self) -> None:
        """JSON 格式 mock 结果。"""
        result = LLMTaskExecutor._mock_result("分析", "intent", "json")
        assert result["mock"] is True
        assert "content" in result
        assert "result" in result["content"]

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        """健康检查默认返回 True。"""
        executor = LLMTaskExecutor()
        result = await executor.health_check()
        assert result is True
