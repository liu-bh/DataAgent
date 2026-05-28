"""FunctionCallingExecutor 单元测试。

使用 mock LLM 和 mock registry 测试 Function Calling 执行循环。
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datapilot_llm.function_calling import (
    FunctionCallRequest,
    FunctionCallResult,
    ToolCall,
)
from datapilot_llm.tool_executor import FunctionCallingExecutor


# ---------- helpers ----------


def _make_llm_response(
    *,
    content: str = "",
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """构建模拟的 LLM 响应。"""
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "choices": [
            {"message": message, "finish_reason": "tool_calls" if tool_calls else "stop"},
        ],
    }


def _make_tool_call(
    call_id: str = "call_001",
    name: str = "sql_query",
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建模拟的 tool_call 字典。"""
    args = arguments or {"sql": "SELECT 1"}
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(args, ensure_ascii=False),
        },
    }


def _make_request(
    user_message: str = "查询销售额",
    tool_schemas: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> FunctionCallRequest:
    """构建测试请求。"""
    default_schemas = [
        {
            "name": "sql_query",
            "description": "执行 SQL",
            "parameters": {"type": "object", "properties": {"sql": {"type": "string"}}},
        },
    ]
    schemas = tool_schemas if tool_schemas is not None else default_schemas
    return FunctionCallRequest(user_message=user_message, tool_schemas=schemas, **kwargs)


# ---------- _build_messages 测试 ----------


class TestBuildMessages:
    """消息构建测试。"""

    def _make_executor(self) -> FunctionCallingExecutor:
        return FunctionCallingExecutor(
            registry=MagicMock(),
            llm_router=MagicMock(),
        )

    def test_basic_messages(self) -> None:
        """包含 system 和 user 消息。"""
        executor = self._make_executor()
        req = _make_request("查询数据")
        messages = executor._build_messages(req)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "查询数据" in messages[1]["content"]

    def test_custom_system_prompt(self) -> None:
        """使用自定义系统提示词。"""
        executor = self._make_executor()
        req = _make_request("test", system_prompt="自定义提示")
        messages = executor._build_messages(req)
        assert messages[0]["content"] == "自定义提示"

    def test_context_appended_to_user_message(self) -> None:
        """上下文信息追加到用户消息。"""
        executor = self._make_executor()
        req = _make_request("查询数据", context={"tenant_id": "t001"})
        messages = executor._build_messages(req)
        assert "tenant_id" in messages[1]["content"]
        assert "t001" in messages[1]["content"]

    def test_no_context_no_append(self) -> None:
        """无上下文时不追加。"""
        executor = self._make_executor()
        req = _make_request("查询数据")
        messages = executor._build_messages(req)
        assert "上下文信息" not in messages[1]["content"]


# ---------- _build_tool_schemas 测试 ----------


class TestBuildToolSchemas:
    """工具 schema 构建测试。"""

    def _make_executor(self) -> FunctionCallingExecutor:
        return FunctionCallingExecutor(
            registry=MagicMock(),
            llm_router=MagicMock(),
        )

    def test_wraps_in_function_type(self) -> None:
        """工具 schema 被包装为 OpenAI 格式。"""
        executor = self._make_executor()
        req = _make_request(tool_schemas=[{"name": "t1"}])
        schemas = executor._build_tool_schemas(req)
        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "t1"

    def test_multiple_schemas(self) -> None:
        """多个工具 schema。"""
        executor = self._make_executor()
        req = _make_request(
            tool_schemas=[{"name": "t1"}, {"name": "t2"}, {"name": "t3"}]
        )
        schemas = executor._build_tool_schemas(req)
        assert len(schemas) == 3

    def test_empty_schemas(self) -> None:
        """空 schema 列表。"""
        executor = self._make_executor()
        req = _make_request(tool_schemas=[])
        schemas = executor._build_tool_schemas(req)
        assert schemas == []


# ---------- _should_continue 测试 ----------


class TestShouldContinue:
    """循环继续条件测试。"""

    def _make_executor(self) -> FunctionCallingExecutor:
        return FunctionCallingExecutor(
            registry=MagicMock(),
            llm_router=MagicMock(),
        )

    def test_continue_with_tool_calls(self) -> None:
        """有 tool_calls 时继续循环。"""
        executor = self._make_executor()
        response = _make_llm_response(
            tool_calls=[_make_tool_call()]
        )
        assert executor._should_continue(response) is True

    def test_stop_without_tool_calls(self) -> None:
        """无 tool_calls 时停止循环。"""
        executor = self._make_executor()
        response = _make_llm_response(content="最终回答")
        assert executor._should_continue(response) is False

    def test_stop_with_empty_choices(self) -> None:
        """空 choices 时停止循环。"""
        executor = self._make_executor()
        response = {"choices": []}
        assert executor._should_continue(response) is False

    def test_stop_with_none_tool_calls(self) -> None:
        """tool_calls 为 None 时停止。"""
        executor = self._make_executor()
        response = {
            "choices": [
                {"message": {"role": "assistant", "content": "answer", "tool_calls": None}},
            ]
        }
        assert executor._should_continue(response) is False


# ---------- _extract_content 测试 ----------


class TestExtractContent:
    """内容提取测试。"""

    def _make_executor(self) -> FunctionCallingExecutor:
        return FunctionCallingExecutor(
            registry=MagicMock(),
            llm_router=MagicMock(),
        )

    def test_extract_text_content(self) -> None:
        """提取文本内容。"""
        executor = self._make_executor()
        response = _make_llm_response(content="这是最终回答")
        assert executor._extract_content(response) == "这是最终回答"

    def test_empty_content(self) -> None:
        """空内容返回空字符串。"""
        executor = self._make_executor()
        response = _make_llm_response(content="")
        assert executor._extract_content(response) == ""

    def test_none_content(self) -> None:
        """None 内容返回空字符串。"""
        executor = self._make_executor()
        response = {
            "choices": [
                {"message": {"role": "assistant", "content": None}},
            ]
        }
        assert executor._extract_content(response) == ""

    def test_empty_choices(self) -> None:
        """空 choices 返回空字符串。"""
        executor = self._make_executor()
        response = {"choices": []}
        assert executor._extract_content(response) == ""


# ---------- execute 循环测试 ----------


class TestExecuteLoop:
    """execute 完整执行循环测试。"""

    def _make_executor(
        self,
        llm_responses: list[dict[str, Any]] | None = None,
        tool_result: dict[str, Any] | None = None,
    ) -> FunctionCallingExecutor:
        """创建测试用执行器，支持预设 LLM 响应。"""
        mock_router = MagicMock()
        mock_registry = MagicMock()

        # 设置 LLM 响应序列
        responses = llm_responses or []
        mock_router.generate = AsyncMock(side_effect=responses)

        # 设置工具执行结果
        if tool_result is None:
            tool_result = {"success": True, "data": [{"total": 100}]}
        mock_registry.execute_tool = AsyncMock(return_value=tool_result)

        return FunctionCallingExecutor(
            registry=mock_registry,
            llm_router=mock_router,
        )

    @pytest.mark.asyncio
    async def test_single_round_no_tool_call(self) -> None:
        """LLM 直接回答，不需要工具调用。"""
        response = _make_llm_response(content="销售额为 100 万元")
        executor = self._make_executor(llm_responses=[response])

        req = _make_request("查询销售额")
        result = await executor.execute(req)

        assert result.final_message == "销售额为 100 万元"
        assert result.tool_calls == []
        assert result.results == []
        assert result.rounds_used == 1
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_two_rounds_tool_then_answer(self) -> None:
        """两轮循环：工具调用 -> 最终回答。"""
        # 第一轮：LLM 请求调用工具
        first_response = _make_llm_response(
            tool_calls=[_make_tool_call(call_id="call_001")]
        )
        # 第二轮：LLM 基于工具结果回答
        second_response = _make_llm_response(content="查询结果：总销售额 100 万")

        executor = self._make_executor(llm_responses=[first_response, second_response])
        req = _make_request("查询销售额")
        result = await executor.execute(req)

        assert result.rounds_used == 2
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "sql_query"
        assert result.final_message == "查询结果：总销售额 100 万"
        assert len(result.results) == 1

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_in_one_round(self) -> None:
        """一轮中多个工具调用。"""
        tool_calls = [
            _make_tool_call(call_id="call_001", name="sql_query", arguments={"sql": "SELECT 1"}),
            _make_tool_call(call_id="call_002", name="list_tables", arguments={}),
        ]
        first_response = _make_llm_response(tool_calls=tool_calls)
        second_response = _make_llm_response(content="分析完成")

        executor = self._make_executor(
            llm_responses=[first_response, second_response],
            tool_result={"success": True, "data": []},
        )
        req = _make_request("分析数据")
        result = await executor.execute(req)

        assert len(result.tool_calls) == 2
        assert result.tool_calls[0].name == "sql_query"
        assert result.tool_calls[1].name == "list_tables"
        assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_max_rounds_limit(self) -> None:
        """达到最大轮次后停止。"""
        # 所有轮都返回 tool_calls，直到 max_rounds
        tool_response = _make_llm_response(
            tool_calls=[_make_tool_call(call_id="call_001")]
        )
        # 提供 max_rounds + 1 个响应，但执行器应该在 max_rounds 处停止
        executor = self._make_executor(
            llm_responses=[tool_response] * 10,
        )
        req = _make_request("查询数据", max_rounds=3)
        result = await executor.execute(req)

        assert result.rounds_used == 3

    @pytest.mark.asyncio
    async def test_tool_execution_failure_captured(self) -> None:
        """工具执行失败被记录到 errors 中。"""
        first_response = _make_llm_response(
            tool_calls=[_make_tool_call(call_id="call_001")]
        )
        second_response = _make_llm_response(content="部分结果")

        mock_router = MagicMock()
        mock_router.generate = AsyncMock(side_effect=[first_response, second_response])

        mock_registry = MagicMock()
        mock_registry.execute_tool = AsyncMock(
            return_value={"success": True, "data": "ok"}
        )

        executor = FunctionCallingExecutor(
            registry=mock_registry,
            llm_router=mock_router,
        )
        req = _make_request("查询数据")
        result = await executor.execute(req)

        # 不应有执行错误（工具返回了 success=True）
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_llm_error_captured(self) -> None:
        """LLM 调用失败被记录到 errors 中。"""
        mock_router = MagicMock()
        mock_router.generate = AsyncMock(side_effect=Exception("API 超时"))

        executor = FunctionCallingExecutor(
            registry=MagicMock(),
            llm_router=mock_router,
        )
        req = _make_request("查询数据")
        result = await executor.execute(req)

        assert len(result.errors) == 1
        assert "API 超时" in result.errors[0]

    @pytest.mark.asyncio
    async def test_total_time_ms_recorded(self) -> None:
        """记录总耗时。"""
        response = _make_llm_response(content="答案")
        executor = self._make_executor(llm_responses=[response])

        req = _make_request("问题")
        result = await executor.execute(req)

        assert result.total_time_ms > 0

    @pytest.mark.asyncio
    async def test_context_passed_to_tool_execution(self) -> None:
        """上下文传递给工具执行。"""
        first_response = _make_llm_response(
            tool_calls=[_make_tool_call(call_id="call_001")]
        )
        second_response = _make_llm_response(content="结果")

        mock_router = MagicMock()
        mock_router.generate = AsyncMock(side_effect=[first_response, second_response])

        mock_registry = MagicMock()
        mock_registry.execute_tool = AsyncMock(
            return_value={"success": True, "data": "result"}
        )

        executor = FunctionCallingExecutor(
            registry=mock_registry,
            llm_router=mock_router,
        )

        ctx = {"tenant_id": "t001"}
        req = _make_request("查询", context=ctx)
        await executor.execute(req)

        # 验证 execute_tool 被调用时传递了 context
        call_args = mock_registry.execute_tool.call_args
        assert call_args[1]["context"] == ctx

    @pytest.mark.asyncio
    async def test_tool_error_result_in_results(self) -> None:
        """工具执行异常时返回错误结果对象。"""
        first_response = _make_llm_response(
            tool_calls=[_make_tool_call(call_id="call_001", name="bad_tool")]
        )
        second_response = _make_llm_response(content="已处理")

        mock_router = MagicMock()
        mock_router.generate = AsyncMock(side_effect=[first_response, second_response])

        mock_registry = MagicMock()
        mock_registry.execute_tool = AsyncMock(
            side_effect=RuntimeError("工具不存在")
        )

        executor = FunctionCallingExecutor(
            registry=mock_registry,
            llm_router=mock_router,
        )
        req = _make_request("执行工具")
        result = await executor.execute(req)

        # 工具失败的结果应包含在 results 中（带 success=False）
        assert len(result.results) == 1
        assert result.results[0]["success"] is False


# ---------- _execute_tool_calls 测试 ----------


class TestExecuteToolCalls:
    """工具调用执行测试。"""

    @pytest.mark.asyncio
    async def test_successful_execution(self) -> None:
        """成功执行工具调用。"""
        mock_registry = MagicMock()
        mock_registry.execute_tool = AsyncMock(
            return_value={"rows": [{"id": 1}]}
        )
        executor = FunctionCallingExecutor(
            registry=mock_registry,
            llm_router=MagicMock(),
        )

        req = _make_request("test")
        tool_calls = [_make_tool_call(call_id="c1", name="sql_query")]
        results = await executor._execute_tool_calls(tool_calls, req)

        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["data"] == {"rows": [{"id": 1}]}

    @pytest.mark.asyncio
    async def test_failed_execution(self) -> None:
        """工具执行失败返回错误结果。"""
        mock_registry = MagicMock()
        mock_registry.execute_tool = AsyncMock(
            side_effect=PermissionError("无权限")
        )
        executor = FunctionCallingExecutor(
            registry=mock_registry,
            llm_router=MagicMock(),
        )

        req = _make_request("test")
        tool_calls = [_make_tool_call(call_id="c1", name="sql_query")]
        results = await executor._execute_tool_calls(tool_calls, req)

        assert len(results) == 1
        assert results[0]["success"] is False
        assert "无权限" in results[0]["error"]

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_mixed_results(self) -> None:
        """多个工具调用，部分成功部分失败。"""
        call_count = 0

        async def mock_execute(name: str, args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"data": "ok"}
            raise ValueError("参数错误")

        mock_registry = MagicMock()
        mock_registry.execute_tool = AsyncMock(side_effect=mock_execute)
        executor = FunctionCallingExecutor(
            registry=mock_registry,
            llm_router=MagicMock(),
        )

        req = _make_request("test")
        tool_calls = [
            _make_tool_call(call_id="c1", name="tool_a"),
            _make_tool_call(call_id="c2", name="tool_b"),
        ]
        results = await executor._execute_tool_calls(tool_calls, req)

        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is False
