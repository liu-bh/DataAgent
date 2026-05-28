"""Function Calling Prompt 模板单元测试。

验证 Prompt 模板内容、占位符和关键约束。
"""
from __future__ import annotations

import re

import pytest

from datapilot_llm.prompts.tool_prompts import (
    FINAL_ANSWER_PROMPT,
    TOOL_ERROR_PROMPT,
    TOOL_RESULT_PROMPT,
    TOOL_SYSTEM_PROMPT,
)


class TestToolSystemPrompt:
    """系统提示词测试。"""

    def test_prompt_not_empty(self) -> None:
        """系统提示词不为空。"""
        assert TOOL_SYSTEM_PROMPT.strip() != ""

    def test_contains_tool_rules(self) -> None:
        """包含工具使用规则。"""
        assert "工具使用规则" in TOOL_SYSTEM_PROMPT

    def test_contains_max_rounds_constraint(self) -> None:
        """包含最大轮次约束。"""
        assert "5" in TOOL_SYSTEM_PROMPT

    def test_contains_sql_safety_rule(self) -> None:
        """包含 SQL 安全规则（禁止 DDL/DML）。"""
        assert "DDL" in TOOL_SYSTEM_PROMPT or "DDL" in TOOL_SYSTEM_PROMPT
        assert "SELECT" in TOOL_SYSTEM_PROMPT

    def test_contains_timeout_constraint(self) -> None:
        """包含 Python 执行超时约束。"""
        assert "30" in TOOL_SYSTEM_PROMPT

    def test_contains_data_analysis_role(self) -> None:
        """声明数据分析助手角色。"""
        assert "数据分析" in TOOL_SYSTEM_PROMPT


class TestToolResultPrompt:
    """工具结果提示词测试。"""

    def test_has_tool_name_placeholder(self) -> None:
        """包含工具名称占位符。"""
        assert "{tool_name}" in TOOL_RESULT_PROMPT

    def test_has_result_placeholder(self) -> None:
        """包含结果占位符。"""
        assert "{result}" in TOOL_RESULT_PROMPT

    def test_format_with_values(self) -> None:
        """可以用实际值格式化。"""
        formatted = TOOL_RESULT_PROMPT.format(
            tool_name="sql_query",
            result="总销售额: 100 万",
        )
        assert "sql_query" in formatted
        assert "总销售额: 100 万" in formatted


class TestToolErrorPrompt:
    """工具错误提示词测试。"""

    def test_has_error_placeholder(self) -> None:
        """包含错误信息占位符。"""
        assert "{error}" in TOOL_ERROR_PROMPT

    def test_promotes_retry(self) -> None:
        """鼓励重试。"""
        assert "重试" in TOOL_ERROR_PROMPT


class TestFinalAnswerPrompt:
    """最终回答提示词测试。"""

    def test_not_empty(self) -> None:
        """不为空。"""
        assert FINAL_ANSWER_PROMPT.strip() != ""

    def test_requires_natural_language(self) -> None:
        """要求使用自然语言回答。"""
        assert "自然语言" in FINAL_ANSWER_PROMPT

    def test_requires_data_source_annotation(self) -> None:
        """要求标注数据来源。"""
        assert "来源" in FINAL_ANSWER_PROMPT


class TestPromptConsistency:
    """Prompt 模板一致性测试。"""

    def test_all_placeholders_are_brace_format(self) -> None:
        """所有占位符使用 Python brace format 风格。"""
        for name, template in [
            ("TOOL_RESULT_PROMPT", TOOL_RESULT_PROMPT),
            ("TOOL_ERROR_PROMPT", TOOL_ERROR_PROMPT),
        ]:
            # 查找所有 {xxx} 占位符
            placeholders = re.findall(r"\{(\w+)\}", template)
            # 尝试用空字符串格式化，验证占位符有效
            try:
                template.format(**{p: "" for p in placeholders})
            except KeyError as exc:
                pytest.fail(f"{name} 包含无效占位符: {exc}")
