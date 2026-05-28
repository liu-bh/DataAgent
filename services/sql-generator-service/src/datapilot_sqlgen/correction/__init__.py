"""Self-Correction 模块 — SQL 自纠错机制。

当 NL2SQL 生成的 SQL 执行失败时，自动分类错误类型，
使用场景化 Prompt 引导 LLM 修正 SQL，并通过 AST 验证确保修正后的 SQL 可解析。
"""

from .engine import SelfCorrectionEngine
from .error_classifier import ErrorClassifier
from .models import CorrectionResult, ErrorCategory
from .prompts import CorrectionPromptBuilder

__all__ = [
    "CorrectionResult",
    "SelfCorrectionEngine",
    "ErrorCategory",
    "ErrorClassifier",
    "CorrectionPromptBuilder",
]
