"""Function Calling 数据模型单元测试。

测试 ToolCall、FunctionCallRequest、FunctionCallResult 的构造、默认值和行为。
"""
from __future__ import annotations

import json

import pytest

from datapilot_llm.function_calling import (
    FunctionCallRequest,
    FunctionCallResult,
    ToolCall,
)


# ---------- ToolCall 测试 ----------


class TestToolCall:
    """ToolCall 数据模型测试。"""

    def test_basic_construction(self) -> None:
        """基本构造。"""
        tc = ToolCall(
            id="call_001",
            name="sql_query",
            arguments={"sql": "SELECT 1"},
        )
        assert tc.id == "call_001"
        assert tc.name == "sql_query"
        assert tc.arguments == {"sql": "SELECT 1"}

    def test_empty_arguments(self) -> None:
        """空参数字典。"""
        tc = ToolCall(id="call_002", name="list_tables", arguments={})
        assert tc.arguments == {}

    def test_nested_arguments(self) -> None:
        """嵌套参数结构。"""
        args = {
            "filter": {"column": "age", "op": "gt", "value": 18},
            "limit": 100,
        }
        tc = ToolCall(id="call_003", name="search_data", arguments=args)
        assert tc.arguments["filter"]["column"] == "age"
        assert tc.arguments["limit"] == 100

    def test_arguments_serializable(self) -> None:
        """arguments 可以 JSON 序列化。"""
        tc = ToolCall(
            id="call_004",
            name="python_exec",
            arguments={"code": "print('hello')"},
        )
        serialized = json.dumps(tc.arguments)
        assert json.loads(serialized) == tc.arguments

    def test_equality(self) -> None:
        """相同属性的 ToolCall 应该相等。"""
        tc1 = ToolCall(id="call_005", name="tool_a", arguments={"x": 1})
        tc2 = ToolCall(id="call_005", name="tool_a", arguments={"x": 1})
        assert tc1 == tc2

    def test_inequality(self) -> None:
        """不同属性的 ToolCall 不应相等。"""
        tc1 = ToolCall(id="call_005", name="tool_a", arguments={"x": 1})
        tc2 = ToolCall(id="call_006", name="tool_a", arguments={"x": 1})
        assert tc1 != tc2


# ---------- FunctionCallRequest 测试 ----------


class TestFunctionCallRequest:
    """FunctionCallRequest 数据模型测试。"""

    def test_basic_construction(self) -> None:
        """基本构造。"""
        req = FunctionCallRequest(
            user_message="查询上月销售额",
            tool_schemas=[{"name": "sql_query"}],
        )
        assert req.user_message == "查询上月销售额"
        assert req.tool_schemas == [{"name": "sql_query"}]

    def test_default_max_rounds(self) -> None:
        """默认最大轮次为 5。"""
        req = FunctionCallRequest(
            user_message="test",
            tool_schemas=[],
        )
        assert req.max_rounds == 5

    def test_default_context_none(self) -> None:
        """默认上下文为 None。"""
        req = FunctionCallRequest(
            user_message="test",
            tool_schemas=[],
        )
        assert req.context is None

    def test_default_system_prompt_none(self) -> None:
        """默认系统提示词为 None。"""
        req = FunctionCallRequest(
            user_message="test",
            tool_schemas=[],
        )
        assert req.system_prompt is None

    def test_custom_max_rounds(self) -> None:
        """自定义最大轮次。"""
        req = FunctionCallRequest(
            user_message="test",
            tool_schemas=[],
            max_rounds=10,
        )
        assert req.max_rounds == 10

    def test_with_context(self) -> None:
        """携带上下文。"""
        ctx = {"tenant_id": "t001", "datasource": "pg_main"}
        req = FunctionCallRequest(
            user_message="test",
            tool_schemas=[],
            context=ctx,
        )
        assert req.context == ctx

    def test_with_system_prompt(self) -> None:
        """自定义系统提示词。"""
        req = FunctionCallRequest(
            user_message="test",
            tool_schemas=[],
            system_prompt="你是一个 SQL 专家",
        )
        assert req.system_prompt == "你是一个 SQL 专家"

    def test_full_openai_schemas(self) -> None:
        """完整的 OpenAI 工具 schema 格式。"""
        schema = {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SQL 查询语句"},
            },
            "required": ["sql"],
        }
        req = FunctionCallRequest(
            user_message="test",
            tool_schemas=[schema],
        )
        assert len(req.tool_schemas) == 1
        assert req.tool_schemas[0]["type"] == "object"


# ---------- FunctionCallResult 测试 ----------


class TestFunctionCallResult:
    """FunctionCallResult 数据模型测试。"""

    def test_default_construction(self) -> None:
        """默认构造，所有字段为空/零值。"""
        result = FunctionCallResult()
        assert result.tool_calls == []
        assert result.results == []
        assert result.final_message == ""
        assert result.total_time_ms == 0.0
        assert result.errors == []
        assert result.rounds_used == 0

    def test_with_tool_calls(self) -> None:
        """包含工具调用记录。"""
        tc = ToolCall(id="call_001", name="sql_query", arguments={"sql": "SELECT 1"})
        result = FunctionCallResult(
            tool_calls=[tc],
            rounds_used=1,
        )
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "sql_query"

    def test_with_results(self) -> None:
        """包含工具执行结果。"""
        results = [
            {"success": True, "data": [{"id": 1}]},
            {"success": True, "data": [{"id": 2}]},
        ]
        result = FunctionCallResult(results=results)
        assert len(result.results) == 2

    def test_with_final_message(self) -> None:
        """包含最终回答。"""
        result = FunctionCallResult(
            final_message="上月销售额为 100 万元",
        )
        assert result.final_message == "上月销售额为 100 万元"

    def test_with_errors(self) -> None:
        """包含错误信息。"""
        result = FunctionCallResult(
            errors=["工具执行超时", "参数格式错误"],
        )
        assert len(result.errors) == 2

    def test_total_time_ms(self) -> None:
        """记录总耗时。"""
        result = FunctionCallResult(total_time_ms=1234.56)
        assert result.total_time_ms == 1234.56

    def test_rounds_used(self) -> None:
        """记录使用轮次。"""
        result = FunctionCallResult(rounds_used=3)
        assert result.rounds_used == 3

    def test_mutable_defaults_are_independent(self) -> None:
        """不同实例的默认列表互不影响。"""
        r1 = FunctionCallResult()
        r2 = FunctionCallResult()
        r1.tool_calls.append(
            ToolCall(id="call_001", name="tool", arguments={})
        )
        assert len(r2.tool_calls) == 0

    def test_full_result(self) -> None:
        """完整的结果对象。"""
        tc = ToolCall(
            id="call_001",
            name="sql_query",
            arguments={"sql": "SELECT SUM(amount) FROM orders"},
        )
        result = FunctionCallResult(
            tool_calls=[tc],
            results=[{"success": True, "data": [{"total": 99999}]}],
            final_message="总销售额为 99,999 元",
            total_time_ms=2500.0,
            errors=[],
            rounds_used=1,
        )
        assert len(result.tool_calls) == 1
        assert result.results[0]["data"][0]["total"] == 99999
        assert result.rounds_used == 1
