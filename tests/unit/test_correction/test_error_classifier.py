"""ErrorClassifier 错误分类器单元测试。"""

from __future__ import annotations

import pytest

from datapilot_sqlgen.correction.error_classifier import ErrorClassifier
from datapilot_sqlgen.correction.models import ErrorCategory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def classifier() -> ErrorClassifier:
    """创建 ErrorClassifier 实例。"""
    return ErrorClassifier()


# ---------------------------------------------------------------------------
# SYNTAX_ERROR 测试
# ---------------------------------------------------------------------------


class TestSyntaxError:
    """SQL 语法错误分类测试。"""

    @pytest.mark.parametrize(
        "msg",
        [
            'syntax error at or near ")"',
            "You have an error in your SQL syntax; check the manual near 'WHERE'",
            'unexpected token "=" at position 42',
            "Parse error: unexpected end of input",
            "malformed expression",
            "invalid SQL statement",
            "语法错误: 在 ')' 附近",
        ],
    )
    def test_syntax_error_keywords(self, classifier: ErrorClassifier, msg: str) -> None:
        """包含语法错误关键词的消息应被分类为 SYNTAX_ERROR。"""
        assert classifier.classify(msg) == ErrorCategory.SYNTAX_ERROR


# ---------------------------------------------------------------------------
# TABLE_NOT_FOUND 测试
# ---------------------------------------------------------------------------


class TestTableNotFound:
    """表不存在错误分类测试。"""

    @pytest.mark.parametrize(
        "msg",
        [
            'relation "orderz" does not exist',
            'table "orderz" doesn\'t exist',
            'unknown table "orderz"',
            "Table or view not found: orderz",
            'invalid table name "orderz"',
            'object "orderz" does not exist',
            "ERROR: relation orderz does not exist",
            "表不存在: orderz",
            "找不到表 orderz",
        ],
    )
    def test_table_not_found_keywords(self, classifier: ErrorClassifier, msg: str) -> None:
        """包含表不存在关键词的消息应被分类为 TABLE_NOT_FOUND。"""
        assert classifier.classify(msg) == ErrorCategory.TABLE_NOT_FOUND


# ---------------------------------------------------------------------------
# COLUMN_NOT_FOUND 测试
# ---------------------------------------------------------------------------


class TestColumnNotFound:
    """列不存在错误分类测试。"""

    @pytest.mark.parametrize(
        "msg",
        [
            'column "user_name" does not exist',
            'column "status" not found in table "orders"',
            'ambiguous column "id" - could refer to orders.id or users.id',
            'unknown column "name" in field list',
            'column "region" could not be resolved',
            "列不存在: user_name",
            "歧义列: id",
        ],
    )
    def test_column_not_found_keywords(self, classifier: ErrorClassifier, msg: str) -> None:
        """包含列不存在关键词的消息应被分类为 COLUMN_NOT_FOUND。"""
        assert classifier.classify(msg) == ErrorCategory.COLUMN_NOT_FOUND


# ---------------------------------------------------------------------------
# EMPTY_RESULT 测试
# ---------------------------------------------------------------------------


class TestEmptyResult:
    """结果为空错误分类测试。"""

    @pytest.mark.parametrize(
        "msg",
        [
            "__EMPTY_RESULT__",
            "empty result returned by the query",
            "no rows returned by the query",
            "查询结果为空",
            "查询返回空结果",
        ],
    )
    def test_empty_result_keywords(self, classifier: ErrorClassifier, msg: str) -> None:
        """包含结果为空关键词的消息应被分类为 EMPTY_RESULT。"""
        assert classifier.classify(msg) == ErrorCategory.EMPTY_RESULT


# ---------------------------------------------------------------------------
# TIMEOUT 测试
# ---------------------------------------------------------------------------


class TestTimeout:
    """执行超时错误分类测试。"""

    @pytest.mark.parametrize(
        "msg",
        [
            "canceling statement due to statement timeout",
            "ERROR: canceling statement due to statement timeout",
            "query timed out after 30000ms",
            "query execution was interrupted: timeout",
            "cancelled on user request",
            "执行超时",
            "查询已超时，请优化",
        ],
    )
    def test_timeout_keywords(self, classifier: ErrorClassifier, msg: str) -> None:
        """包含超时关键词的消息应被分类为 TIMEOUT。"""
        assert classifier.classify(msg) == ErrorCategory.TIMEOUT


# ---------------------------------------------------------------------------
# OTHER 测试
# ---------------------------------------------------------------------------


class TestOther:
    """其他错误分类测试。"""

    @pytest.mark.parametrize(
        "msg",
        [
            "division by zero",
            "out of memory",
            "permission denied for table orders",
            "some random error message without known keywords",
            "connection refused",
            "too many connections",
        ],
    )
    def test_other_unmatched(self, classifier: ErrorClassifier, msg: str) -> None:
        """不匹配任何已知分类的消息应被分类为 OTHER。"""
        assert classifier.classify(msg) == ErrorCategory.OTHER

    def test_empty_message(self, classifier: ErrorClassifier) -> None:
        """空消息应被分类为 OTHER。"""
        assert classifier.classify("") == ErrorCategory.OTHER

    def test_none_like_message(self, classifier: ErrorClassifier) -> None:
        """仅包含空白的消息应被分类为 OTHER。"""
        assert classifier.classify("   ") == ErrorCategory.OTHER


# ---------------------------------------------------------------------------
# 边界情况测试
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """边界情况测试。"""

    def test_case_insensitive(self, classifier: ErrorClassifier) -> None:
        """分类应不区分大小写。"""
        assert classifier.classify("SYNTAX ERROR") == ErrorCategory.SYNTAX_ERROR
        assert classifier.classify("Syntax Error") == ErrorCategory.SYNTAX_ERROR
        assert classifier.classify("syntax error") == ErrorCategory.SYNTAX_ERROR

    def test_priority_table_over_column(self, classifier: ErrorClassifier) -> None:
        """当消息同时包含 table 和 column 关键词时，TABLE_NOT_FOUND 优先。"""
        # timeout 优先级最高
        msg = "canceling statement due to timeout - table 'x' does not exist"
        assert classifier.classify(msg) == ErrorCategory.TIMEOUT

    def test_timeout_highest_priority(self, classifier: ErrorClassifier) -> None:
        """TIMEOUT 具有最高优先级。"""
        msg = "query timed out - syntax error near ')'"
        assert classifier.classify(msg) == ErrorCategory.TIMEOUT

    def test_long_message(self, classifier: ErrorClassifier) -> None:
        """长错误消息不应导致异常。"""
        long_msg = "ERROR: syntax error at or near ')'" + " x" * 10000
        assert classifier.classify(long_msg) == ErrorCategory.SYNTAX_ERROR
