"""SQL 错误分类器。

通过关键词和正则表达式匹配，将 SQL 执行错误分为 6 种类别，
为后续的场景化纠错提供决策依据。
"""

from __future__ import annotations

import re

import structlog

from .models import ErrorCategory

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# 错误分类规则定义
# ---------------------------------------------------------------------------

# 每条规则: (ErrorCategory, [关键词/正则模式列表], 优先级)
# 优先级数值越小越先匹配，匹配成功后立即返回。
_CLASSIFICATION_RULES: list[tuple[ErrorCategory, list[str], int]] = [
    # --- timeout: 执行超时 ---
    (
        ErrorCategory.TIMEOUT,
        [
            r"\btimeout\b",
            r"\btimed?\s*out\b",
            r"\bcanceling\s+statement\b",
            r"\bquery\s+execution\s+was\s+interrupted\b",
            r"\bcancelled\s+on\s+user\s+request\b",
            r"超时",
            r"执行超时",
            r"已取消",
        ],
        10,
    ),
    # --- table_not_found: 表不存在 ---
    (
        ErrorCategory.TABLE_NOT_FOUND,
        [
            r"\btable\b.*\bdoesn'?t\s+exist\b",
            r"\brelation\b.*\bdoes\s+not\s+exist\b",
            r"\bunknown\s+table\b",
            r"\btable\b.*\bnot\s+found\b",
            r"\btable\s+or\s+view\s+not\s+found\b",
            r"\binvalid\s+table\s+name\b",
            r"\bobject\b.*\bdoes\s+not\s+exist\b",
            r"表不存在",
            r"找不到表",
        ],
        20,
    ),
    # --- column_not_found: 列不存在 ---
    (
        ErrorCategory.COLUMN_NOT_FOUND,
        [
            r"\bcolumn\b.*\bdoesn'?t\s+exist\b",
            r"\bcolumn\b.*\bdoes\s+not\s+exist\b",
            r"\bcolumn\b.*\bnot\s+found\b",
            r"\bambiguous\s+column\b",
            r"\bunknown\s+column\b",
            r"\bcolumn\b.*\bcould\s+not\s+be\s+resolved\b",
            r"\bcolumn\s+reference\b.*\bambiguous\b",
            r"列不存在",
            r"列名",
            r"歧义列",
        ],
        30,
    ),
    # --- syntax_error: SQL 语法错误 ---
    (
        ErrorCategory.SYNTAX_ERROR,
        [
            r"\bsyntax\s+error\b",
            r"\bnear\b.*['\"]",
            r"\bunexpected\b.*\btoken\b",
            r"\bunexpected\s+end\b.*\bof\s+input\b",
            r"\bparse\s+error\b",
            r"\bmalformed\b",
            r"\binvalid\s+sql\b",
            r"语法错误",
            r"解析错误",
        ],
        40,
    ),
    # --- empty_result: 结果为空（自定义标记，非数据库原生错误） ---
    (
        ErrorCategory.EMPTY_RESULT,
        [
            r"__EMPTY_RESULT__",
            r"\bempty\s+result\b",
            r"\bno\s+rows?\s+returned\b",
            r"返回.*空结果",
            r"查询结果为空",
        ],
        50,
    ),
]

# 预编译所有正则模式，提升匹配性能
_COMPILED_RULES: list[tuple[ErrorCategory, list[re.Pattern[str]], int]] = [
    (category, [re.compile(pattern, re.IGNORECASE) for pattern in patterns], priority)
    for category, patterns, priority in _CLASSIFICATION_RULES
]


class ErrorClassifier:
    """SQL 错误分类器。

    根据数据库执行错误消息，使用关键词和正则匹配策略将错误分为 6 类。

    Usage::

        classifier = ErrorClassifier()
        category = classifier.classify('relation "orders" does not exist')
        # => ErrorCategory.TABLE_NOT_FOUND
    """

    def classify(self, error_message: str) -> ErrorCategory:
        """对错误消息进行分类。

        按照优先级从高到低遍历分类规则，首个匹配成功的类别即为结果。
        若所有规则均未命中，返回 OTHER。

        Args:
            error_message: 数据库执行返回的错误消息文本。

        Returns:
            错误类别枚举值。
        """
        if not error_message:
            logger.warning("error_classifier_empty_message")
            return ErrorCategory.OTHER

        for category, patterns, priority in _COMPILED_RULES:
            for pattern in patterns:
                if pattern.search(error_message):
                    logger.debug(
                        "error_classified",
                        category=category.value,
                        priority=priority,
                        error_message=error_message[:200],
                    )
                    return category

        logger.debug(
            "error_classified_other",
            error_message=error_message[:200],
        )
        return ErrorCategory.OTHER
