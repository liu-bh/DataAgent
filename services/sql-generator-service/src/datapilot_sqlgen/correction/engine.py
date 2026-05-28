"""Self-Correction 引擎 — SQL 自纠错核心流程。

接收出错的 SQL 和错误信息，经过最多 N 轮的 "分类 -> 生成 Prompt -> LLM 修正 -> AST 验证"
循环，输出修正后的 SQL 或降级结果。
"""

from __future__ import annotations

import contextlib
import json
import re
from typing import Any

import structlog

from .error_classifier import ErrorClassifier
from .models import CorrectionResult
from .prompts import CorrectionPromptBuilder

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# SQL 提取工具函数
# ---------------------------------------------------------------------------

# JSON 输出中 sql 字段的正则模式
_SQL_FIELD_PATTERN = re.compile(r'"sql"\s*:\s*"((?:[^"\\]|\\.)*)"\s*[,}]')
# Markdown 代码块中的 SQL
_SQL_CODE_BLOCK_PATTERN = re.compile(r"```(?:sql)?\s*\n(.*?)\n```", re.DOTALL)


def _extract_sql_from_llm_response(response_text: str) -> str | None:
    """从 LLM 响应文本中提取 SQL。

    依次尝试以下策略：
    1. JSON 中提取 "sql" 字段
    2. Markdown SQL 代码块提取
    3. 直接取去除首尾空白的第一行

    Args:
        response_text: LLM 返回的文本。

    Returns:
        提取到的 SQL，如果无法提取则返回 None。
    """
    if not response_text:
        return None

    text = response_text.strip()

    # 策略 1: JSON 中提取 sql 字段
    json_match = _SQL_FIELD_PATTERN.search(text)
    if json_match:
        sql = json_match.group(1)
        # 反转义 JSON 字符串中的转义字符
        with contextlib.suppress(json.JSONDecodeError):
            sql = json.loads(f'"{sql}"')
        sql = sql.strip()
        if sql:
            return sql

    # 策略 2: Markdown SQL 代码块
    code_block_match = _SQL_CODE_BLOCK_PATTERN.search(text)
    if code_block_match:
        sql = code_block_match.group(1).strip()
        if sql:
            return sql

    # 策略 3: 整体作为 SQL 解析（至少包含 SELECT）
    upper_text = text.upper()
    if "SELECT" in upper_text:
        # 取第一个 SELECT 到结尾
        select_idx = upper_text.index("SELECT")
        sql = text[select_idx:].strip()
        # 截断可能的后缀说明文字
        if sql:
            return sql

    return None


# ---------------------------------------------------------------------------
# AST 验证
# ---------------------------------------------------------------------------


def _validate_sql_syntax(sql: str) -> tuple[bool, str]:
    """使用 sqlglot AST 验证 SQL 语法。

    Args:
        sql: 待验证的 SQL 语句。

    Returns:
        (是否有效, 错误描述) 元组。有效时错误描述为空。
    """
    if not sql or not sql.strip():
        return False, "SQL 为空"

    try:
        import sqlglot
    except ImportError:
        logger.warning("sqlglot_not_installed")
        # sqlglot 不可用时跳过验证
        return True, ""

    try:
        sqlglot.parse(sql, error_level=sqlglot.ErrorLevel.RAISE)
        return True, ""
    except sqlglot.errors.ParseError as exc:
        return False, f"AST 解析失败: {exc}"
    except Exception as exc:
        return False, f"验证异常: {exc}"


# ---------------------------------------------------------------------------
# Self-Correction 引擎
# ---------------------------------------------------------------------------


class SelfCorrectionEngine:
    """SQL 自纠错引擎。

    接收执行失败的 SQL 和错误信息，在最多 max_rounds 轮内完成：
    1. 错误分类
    2. 场景化 Prompt 构建
    3. LLM 生成修正 SQL
    4. AST 语法验证
    5. 验证通过则返回成功，否则继续下一轮

    当未配置 LLM 路由器时，直接返回降级结果（success=False）。

    Usage::

        engine = SelfCorrectionEngine(llm_router=router, max_rounds=3)
        result = await engine.correct(
            sql="SELECT * FROM orderz",
            error_message='relation "orderz" does not exist',
            context={"available_tables": ["orders", "users"]},
        )
    """

    def __init__(
        self,
        llm_router: Any | None = None,
        max_rounds: int = 3,
    ) -> None:
        """初始化纠错引擎。

        Args:
            llm_router: LLM 路由器实例（来自 datapilot-llm），为 None 时启用降级模式。
            max_rounds: 最大纠错轮次，默认 3。
        """
        self._llm_router = llm_router
        self._max_rounds = max(1, min(max_rounds, 10))
        self._classifier = ErrorClassifier()
        self._prompt_builder = CorrectionPromptBuilder()

        logger.info(
            "self_correction_engine_initialized",
            max_rounds=self._max_rounds,
            has_llm=llm_router is not None,
        )

    async def correct(
        self,
        sql: str,
        error_message: str,
        context: dict[str, Any] | None = None,
    ) -> CorrectionResult:
        """执行 SQL 自纠错。

        Args:
            sql: 执行失败的原始 SQL。
            error_message: 数据库返回的错误信息。
            context: 纠错上下文，支持以下字段：
                - available_tables: list[str] 可用表名列表
                - available_columns: dict[str, list[str]] 表名到列名的映射
                - dialect: str SQL 方言
                - previous_corrections: list[str] 历史纠错记录

        Returns:
            CorrectionResult 纠错结果，包含修正后的 SQL 和状态信息。
        """
        context = context or {}

        # 步骤 1: 错误分类
        category = self._classifier.classify(error_message)

        logger.info(
            "correction_started",
            error_category=category.value,
            sql_preview=sql[:100],
            error_preview=error_message[:200],
        )

        # 降级模式：无 LLM 路由器，直接返回失败
        if self._llm_router is None:
            logger.warning(
                "correction_degraded_no_llm",
                error_category=category.value,
            )
            return CorrectionResult(
                success=False,
                corrected_sql=sql,
                attempts=0,
                error_category=category.value,
                original_error=error_message,
                corrections_history=[],
            )

        # 步骤 2-5: 纠错循环
        corrections_history: list[str] = []
        current_sql = sql

        for attempt in range(1, self._max_rounds + 1):
            logger.info(
                "correction_attempt",
                attempt=attempt,
                max_rounds=self._max_rounds,
                error_category=category.value,
            )

            # 构建纠错上下文（包含历史记录）
            attempt_context = dict(context)
            attempt_context["attempt_number"] = attempt
            if corrections_history:
                attempt_context["previous_corrections"] = corrections_history

            # 步骤 2: 构建纠错 Prompt
            system_prompt, user_prompt = self._prompt_builder.build(
                category=category,
                sql=current_sql,
                error_message=error_message,
                context=attempt_context,
            )

            # 步骤 3: 调用 LLM 生成修正 SQL
            corrected_sql = await self._call_llm(system_prompt, user_prompt)

            if not corrected_sql:
                logger.warning(
                    "correction_llm_no_sql",
                    attempt=attempt,
                )
                corrections_history.append(f"[轮次 {attempt}] LLM 未返回有效 SQL")
                continue

            logger.debug(
                "correction_llm_response",
                attempt=attempt,
                corrected_sql_preview=corrected_sql[:200],
            )

            # 步骤 4: AST 语法验证
            is_valid, validation_msg = _validate_sql_syntax(corrected_sql)

            if is_valid:
                logger.info(
                    "correction_success",
                    attempt=attempt,
                    total_attempts=attempt,
                    error_category=category.value,
                )
                corrections_history.append(f"[轮次 {attempt}] {corrected_sql}")
                return CorrectionResult(
                    success=True,
                    corrected_sql=corrected_sql,
                    attempts=attempt,
                    error_category=category.value,
                    original_error=error_message,
                    corrections_history=corrections_history,
                )

            # 验证失败，记录并继续下一轮
            logger.warning(
                "correction_validation_failed",
                attempt=attempt,
                validation_message=validation_msg,
            )
            corrections_history.append(
                f"[轮次 {attempt}] SQL: {corrected_sql} | 验证失败: {validation_msg}"
            )
            # 下一轮使用 LLM 返回的 SQL 作为输入（附带新的验证错误）
            current_sql = corrected_sql
            error_message = validation_msg

        # 达到最大轮次仍未成功
        logger.warning(
            "correction_max_rounds_exceeded",
            max_rounds=self._max_rounds,
            error_category=category.value,
        )
        return CorrectionResult(
            success=False,
            corrected_sql=current_sql,
            attempts=self._max_rounds,
            error_category=category.value,
            original_error=error_message,
            corrections_history=corrections_history,
        )

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str | None:
        """调用 LLM 生成修正 SQL。

        Args:
            system_prompt: 系统提示词。
            user_prompt: 用户提示词。

        Returns:
            提取到的修正 SQL，调用失败时返回 None。
        """
        try:
            # 调用 LLM 路由器（使用 CORRECTION 场景）
            from datapilot_llm.router import Scene

            response = await self._llm_router.generate(
                scene=Scene.CORRECTION,
                prompt=user_prompt,
                system=system_prompt,
                json_mode=True,
            )

            # 从 LLM 响应中提取 SQL
            content = getattr(response, "content", None) or str(response)
            return _extract_sql_from_llm_response(content)

        except Exception as exc:
            logger.error(
                "correction_llm_call_failed",
                error=str(exc),
            )
            return None
