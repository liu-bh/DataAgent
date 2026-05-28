"""CorrectionPromptBuilder Prompt 模板单元测试。"""

from __future__ import annotations

import pytest

from datapilot_sqlgen.correction.models import ErrorCategory
from datapilot_sqlgen.correction.prompts import CorrectionPromptBuilder

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def builder() -> CorrectionPromptBuilder:
    """创建 CorrectionPromptBuilder 实例。"""
    return CorrectionPromptBuilder()


# ---------------------------------------------------------------------------
# 通用行为测试
# ---------------------------------------------------------------------------


class TestBuildGeneralBehavior:
    """Prompt 构建通用行为测试。"""

    @pytest.mark.parametrize("category", list(ErrorCategory))
    def test_returns_system_and_user_prompt(
        self, builder: CorrectionPromptBuilder, category: ErrorCategory
    ) -> None:
        """所有错误类别都应返回 (system_prompt, user_prompt) 元组。"""
        system_prompt, user_prompt = builder.build(
            category=category,
            sql="SELECT 1",
            error_message="test error",
        )
        assert isinstance(system_prompt, str)
        assert isinstance(user_prompt, str)
        assert len(system_prompt) > 0
        assert len(user_prompt) > 0

    def test_system_prompt_contains_role_definition(self, builder: CorrectionPromptBuilder) -> None:
        """System Prompt 应包含角色定义。"""
        system_prompt, _ = builder.build(
            category=ErrorCategory.OTHER,
            sql="SELECT 1",
            error_message="test",
        )
        assert "SQL" in system_prompt
        assert "纠错" in system_prompt

    def test_system_prompt_contains_output_format(self, builder: CorrectionPromptBuilder) -> None:
        """System Prompt 应包含 JSON 输出格式说明。"""
        system_prompt, _ = builder.build(
            category=ErrorCategory.OTHER,
            sql="SELECT 1",
            error_message="test",
        )
        assert '"sql"' in system_prompt
        assert '"fix_explanation"' in system_prompt

    def test_user_prompt_contains_sql(self, builder: CorrectionPromptBuilder) -> None:
        """User Prompt 应包含原始 SQL。"""
        _, user_prompt = builder.build(
            category=ErrorCategory.OTHER,
            sql="SELECT * FROM orders",
            error_message="test error",
        )
        assert "SELECT * FROM orders" in user_prompt

    def test_user_prompt_contains_error_message(self, builder: CorrectionPromptBuilder) -> None:
        """User Prompt 应包含错误信息。"""
        _, user_prompt = builder.build(
            category=ErrorCategory.OTHER,
            sql="SELECT 1",
            error_message='relation "orderz" does not exist',
        )
        assert 'relation "orderz" does not exist' in user_prompt


# ---------------------------------------------------------------------------
# 各类别专用测试
# ---------------------------------------------------------------------------


class TestSyntaxErrorPrompt:
    """SYNTAX_ERROR 类别 Prompt 测试。"""

    def test_contains_syntax_error_label(self, builder: CorrectionPromptBuilder) -> None:
        """应包含语法错误标签。"""
        _, user_prompt = builder.build(
            category=ErrorCategory.SYNTAX_ERROR,
            sql="SELECT * FORM orders",
            error_message='syntax error at or near "FORM"',
        )
        assert "语法错误" in user_prompt
        assert "SYNTAX ERROR" in user_prompt.upper() or "语法错误" in user_prompt


class TestTableNotFoundPrompt:
    """TABLE_NOT_FOUND 类别 Prompt 测试。"""

    def test_contains_available_tables(self, builder: CorrectionPromptBuilder) -> None:
        """应包含可用表列表。"""
        _, user_prompt = builder.build(
            category=ErrorCategory.TABLE_NOT_FOUND,
            sql="SELECT * FROM orderz",
            error_message='relation "orderz" does not exist',
            context={"available_tables": ["orders", "users", "products"]},
        )
        assert "orders" in user_prompt
        assert "users" in user_prompt
        assert "products" in user_prompt

    def test_missing_tables_shows_placeholder(self, builder: CorrectionPromptBuilder) -> None:
        """未提供表列表时应显示占位符。"""
        _, user_prompt = builder.build(
            category=ErrorCategory.TABLE_NOT_FOUND,
            sql="SELECT * FROM orderz",
            error_message='relation "orderz" does not exist',
        )
        assert "未提供" in user_prompt


class TestColumnNotFoundPrompt:
    """COLUMN_NOT_FOUND 类别 Prompt 测试。"""

    def test_contains_available_columns(self, builder: CorrectionPromptBuilder) -> None:
        """应包含可用列信息。"""
        _, user_prompt = builder.build(
            category=ErrorCategory.COLUMN_NOT_FOUND,
            sql="SELECT user_name FROM orders",
            error_message='column "user_name" does not exist',
            context={
                "available_columns": {
                    "orders": ["id", "user_id", "amount", "status"],
                    "users": ["id", "name", "region"],
                },
            },
        )
        assert "orders" in user_prompt
        assert "user_id" in user_prompt
        assert "name" in user_prompt


class TestEmptyResultPrompt:
    """EMPTY_RESULT 类别 Prompt 测试。"""

    def test_contains_suggestion_hint(self, builder: CorrectionPromptBuilder) -> None:
        """应包含放宽条件的建议提示。"""
        _, user_prompt = builder.build(
            category=ErrorCategory.EMPTY_RESULT,
            sql="SELECT * FROM orders WHERE status = 'pending' AND amount > 10000",
            error_message="查询结果为空",
        )
        assert "放宽" in user_prompt
        assert "WHERE" in user_prompt.upper() or "where" in user_prompt


class TestTimeoutPrompt:
    """TIMEOUT 类别 Prompt 测试。"""

    def test_contains_optimization_hint(self, builder: CorrectionPromptBuilder) -> None:
        """应包含查询优化建议提示。"""
        _, user_prompt = builder.build(
            category=ErrorCategory.TIMEOUT,
            sql="SELECT * FROM orders o JOIN users u ON o.user_id = u.id JOIN products p ON ...",
            error_message="canceling statement due to statement timeout",
        )
        assert "LIMIT" in user_prompt
        assert "优化" in user_prompt


class TestOtherPrompt:
    """OTHER 类别 Prompt 测试。"""

    def test_contains_error_message(self, builder: CorrectionPromptBuilder) -> None:
        """应包含原始错误信息。"""
        _, user_prompt = builder.build(
            category=ErrorCategory.OTHER,
            sql="SELECT 1/0",
            error_message="division by zero",
        )
        assert "division by zero" in user_prompt


# ---------------------------------------------------------------------------
# 上下文注入测试
# ---------------------------------------------------------------------------


class TestContextInjection:
    """上下文信息注入测试。"""

    def test_dialect_in_context(self, builder: CorrectionPromptBuilder) -> None:
        """提供 dialect 时应出现在 Prompt 中。"""
        _, user_prompt = builder.build(
            category=ErrorCategory.OTHER,
            sql="SELECT 1",
            error_message="test",
            context={"dialect": "postgres"},
        )
        assert "postgres" in user_prompt

    def test_multi_attempt_prefix(self, builder: CorrectionPromptBuilder) -> None:
        """多轮纠错时应包含轮次提示。"""
        _, user_prompt = builder.build(
            category=ErrorCategory.OTHER,
            sql="SELECT 1",
            error_message="test",
            context={"attempt_number": 2},
        )
        assert "第 2 轮" in user_prompt
        assert "避免重复" in user_prompt

    def test_first_attempt_no_prefix(self, builder: CorrectionPromptBuilder) -> None:
        """第一轮纠错时不应包含轮次提示。"""
        _, user_prompt = builder.build(
            category=ErrorCategory.OTHER,
            sql="SELECT 1",
            error_message="test",
            context={"attempt_number": 1},
        )
        assert "第 1 轮" not in user_prompt

    def test_previous_corrections_in_context(self, builder: CorrectionPromptBuilder) -> None:
        """历史纠错记录应出现在 Prompt 中。"""
        _, user_prompt = builder.build(
            category=ErrorCategory.OTHER,
            sql="SELECT 1",
            error_message="test",
            context={
                "attempt_number": 3,
                "previous_corrections": [
                    "SELECT * FORM orders",
                    "SELECT * FROMM orders",
                ],
            },
        )
        assert "历史纠错记录" in user_prompt
        assert "FORM orders" in user_prompt

    def test_none_context_graceful(self, builder: CorrectionPromptBuilder) -> None:
        """context 为 None 时不应报错。"""
        system_prompt, user_prompt = builder.build(
            category=ErrorCategory.OTHER,
            sql="SELECT 1",
            error_message="test",
            context=None,
        )
        assert isinstance(system_prompt, str)
        assert isinstance(user_prompt, str)
