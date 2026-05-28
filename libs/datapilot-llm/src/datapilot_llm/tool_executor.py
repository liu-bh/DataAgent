"""Function Calling 执行器。

编排 LLM 和工具调用的循环，实现完整的 Function Calling 流程：
构建消息 -> 调用 LLM -> 判断是否需要工具调用 -> 执行工具 -> 回传结果 -> 继续循环。
"""
from __future__ import annotations

import json
import time
from typing import Any

import structlog

from datapilot_llm.function_calling import (
    FunctionCallRequest,
    FunctionCallResult,
    ToolCall,
)
from datapilot_llm.prompts.tool_prompts import TOOL_SYSTEM_PROMPT

logger = structlog.get_logger(__name__)


class FunctionCallingExecutor:
    """Function Calling 执行器。

    管理 LLM 与工具之间的多轮交互循环，将用户自然语言请求
    转化为工具调用，收集结果并生成最终回答。

    Args:
        registry: 工具注册表，提供工具的查找和执行能力。
        llm_router: LLM 路由器，用于调用大模型。
        default_max_rounds: 默认最大工具调用轮次。
    """

    def __init__(
        self,
        registry: Any,
        llm_router: Any,
        *,
        default_max_rounds: int = 5,
    ) -> None:
        self._registry = registry
        self._llm_router = llm_router
        self._default_max_rounds = default_max_rounds

    async def execute(self, request: FunctionCallRequest) -> FunctionCallResult:
        """执行 Function Calling 循环。

        流程：
        1. 构建 messages（system + tools + user）
        2. 调用 LLM
        3. 如果 LLM 返回 tool_calls -> 执行工具 -> 追加结果到 messages -> 重新调用
        4. 最多 max_rounds 轮
        5. 返回结果

        Args:
            request: Function Calling 请求。

        Returns:
            FunctionCallResult 包含所有工具调用记录和最终回答。
        """
        start_time = time.perf_counter()
        max_rounds = min(request.max_rounds, self._default_max_rounds)
        messages = self._build_messages(request)
        tool_schemas = self._build_tool_schemas(request)

        all_tool_calls: list[ToolCall] = []
        all_results: list[dict[str, Any]] = []
        errors: list[str] = []
        rounds_used = 0
        final_message = ""

        for round_num in range(1, max_rounds + 1):
            rounds_used = round_num
            logger.debug(
                "function_calling_round_start",
                round=round_num,
                max_rounds=max_rounds,
            )

            # 调用 LLM
            try:
                response = await self._call_llm(messages, tool_schemas, request)
            except Exception as exc:
                error_msg = f"LLM 调用失败（第 {round_num} 轮）: {exc}"
                logger.error(
                    "function_calling_llm_error",
                    round=round_num,
                    error=str(exc),
                )
                errors.append(error_msg)
                break

            # 提取 tool_calls
            llm_tool_calls = self._extract_tool_calls(response)

            if not llm_tool_calls:
                # LLM 不再请求工具调用，获取最终回答
                final_message = self._extract_content(response)
                logger.debug(
                    "function_calling_completed",
                    rounds=rounds_used,
                    total_tool_calls=len(all_tool_calls),
                )
                break

            # 执行工具调用
            logger.debug(
                "function_calling_executing_tools",
                round=round_num,
                tool_count=len(llm_tool_calls),
            )

            # 将 LLM 的 assistant 消息（含 tool_calls）追加到 messages
            messages.append({
                "role": "assistant",
                "content": response.get("content") or "",
                "tool_calls": llm_tool_calls,
            })

            try:
                tool_results = await self._execute_tool_calls(llm_tool_calls, request)
            except Exception as exc:
                error_msg = f"工具执行失败（第 {round_num} 轮）: {exc}"
                logger.error(
                    "function_calling_tool_error",
                    round=round_num,
                    error=str(exc),
                )
                errors.append(error_msg)
                break

            # 记录工具调用和结果
            for tc_data in llm_tool_calls:
                tool_call = ToolCall(
                    id=tc_data["id"],
                    name=tc_data["function"]["name"],
                    arguments=json.loads(tc_data["function"]["arguments"]),
                )
                all_tool_calls.append(tool_call)

            all_results.extend(tool_results)

            # 将工具结果追加到 messages
            for tc_data, result in zip(llm_tool_calls, tool_results, strict=True):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_data["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                })

        total_time_ms = (time.perf_counter() - start_time) * 1000

        return FunctionCallResult(
            tool_calls=all_tool_calls,
            results=all_results,
            final_message=final_message,
            total_time_ms=round(total_time_ms, 2),
            errors=errors,
            rounds_used=rounds_used,
        )

    def _build_messages(self, request: FunctionCallRequest) -> list[dict[str, Any]]:
        """构建 OpenAI 格式的 messages 列表。

        Args:
            request: Function Calling 请求。

        Returns:
            包含 system 和 user 消息的列表。
        """
        messages: list[dict[str, Any]] = []

        # 系统提示
        system_prompt = request.system_prompt or TOOL_SYSTEM_PROMPT
        messages.append({"role": "system", "content": system_prompt})

        # 用户消息
        user_content = request.user_message

        # 如果有额外上下文，追加到用户消息中
        if request.context:
            context_str = json.dumps(request.context, ensure_ascii=False)
            user_content = f"{user_content}\n\n上下文信息：\n{context_str}"

        messages.append({"role": "user", "content": user_content})

        return messages

    def _build_tool_schemas(self, request: FunctionCallRequest) -> list[dict[str, Any]]:
        """构建 tools 参数（OpenAI function calling 格式）。

        Args:
            request: Function Calling 请求。

        Returns:
            工具 schema 列表。
        """
        return [
            {
                "type": "function",
                "function": schema,
            }
            for schema in request.tool_schemas
        ]

    async def _call_llm(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        request: FunctionCallRequest,
    ) -> dict[str, Any]:
        """调用 LLM（通过 router 的 chat_completion 接口）。

        Args:
            messages: 对话消息列表。
            tools: 工具 schema 列表。
            request: 原始请求（用于传递 temperature 等参数）。

        Returns:
            LLM 原始响应字典。
        """
        response = await self._llm_router.generate(
            scene="function_calling",
            prompt=messages,
            tools=tools,
        )
        return response

    def _extract_tool_calls(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """从 LLM 响应中提取 tool_calls。

        Args:
            response: LLM 响应字典。

        Returns:
            tool_calls 列表，如果没有则为空列表。
        """
        choices = response.get("choices", [])
        if not choices:
            return []

        message = choices[0].get("message", {})
        return message.get("tool_calls", []) or []

    def _extract_content(self, response: dict[str, Any]) -> str:
        """从 LLM 响应中提取文本内容。

        Args:
            response: LLM 响应字典。

        Returns:
            文本内容，如果没有则为空字符串。
        """
        choices = response.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return message.get("content", "") or ""

    def _should_continue(self, response: dict[str, Any]) -> bool:
        """判断是否需要继续循环。

        当 LLM 返回 tool_calls 时需要继续，否则结束。

        Args:
            response: LLM 响应字典。

        Returns:
            True 表示需要继续工具调用循环。
        """
        return bool(self._extract_tool_calls(response))

    async def _execute_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
        request: FunctionCallRequest,
    ) -> list[dict[str, Any]]:
        """执行工具调用并收集结果。

        Args:
            tool_calls: LLM 返回的工具调用列表。
            request: 原始请求，可能携带额外上下文。

        Returns:
            每个工具调用的执行结果列表。
        """
        results: list[dict[str, Any]] = []

        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            tool_args = json.loads(tc["function"]["arguments"])
            tool_call_id = tc["id"]

            logger.debug(
                "executing_tool",
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                args_keys=list(tool_args.keys()),
            )

            try:
                result = await self._registry.execute_tool(
                    tool_name,
                    tool_args,
                    context=request.context,
                )
                results.append({
                    "success": True,
                    "data": result,
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                })
            except Exception as exc:
                logger.warning(
                    "tool_execution_failed",
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    error=str(exc),
                )
                results.append({
                    "success": False,
                    "error": str(exc),
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                })

        return results
