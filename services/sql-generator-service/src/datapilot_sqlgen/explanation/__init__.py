"""SQL 自然语言解释模块。

提供 SQL 语句的自然语言解释能力，支持 LLM 增强解释和 AST 基础分析两种模式。
"""

from .interpreter import SQLInterpreter
from .models import SQLExplanation
from .prompts import EXPLAIN_SYSTEM_PROMPT, build_explain_prompt

__all__ = [
    "SQLInterpreter",
    "SQLExplanation",
    "EXPLAIN_SYSTEM_PROMPT",
    "build_explain_prompt",
]
