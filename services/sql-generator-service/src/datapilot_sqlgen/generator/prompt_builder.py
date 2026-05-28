"""Prompt 组装器。

将语义上下文、Few-shot 示例和用户问题组装为完整的 NL2SQL Prompt。
遵循 prompt-engineering.md 的 Prompt 编写规范。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from datapilot_prompt.budget import TokenBudgetManager

    from .models import (
        FewShotExample,
        SemanticContext,
    )

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# 默认 NL2SQL System Prompt 模板
# ---------------------------------------------------------------------------

DEFAULT_NL2SQL_SYSTEM_PROMPT = """你是一个专业的 SQL 生成助手。根据用户的自然语言问题和提供的数据库结构信息，生成准确的 SQL 查询。

## 规则
1. 只使用提供的表和列，不要编造不存在的表名或列名
2. 时间范围需要明确指定 WHERE 条件
3. 聚合查询必须包含 GROUP BY
4. TOP N 查询必须包含 ORDER BY 和 LIMIT
5. JOIN 时必须使用正确的关联条件
6. 不要使用 SELECT *，明确列出需要的列
7. 生成的 SQL 必须语法正确且可执行

## SQL 方言
使用 {dialect} 语法。

## 数据库结构
{semantic_context}

## 参考 SQL 示例
{few_shot_examples}

## 用户问题
{question}

请返回如下 JSON 格式:
```json
{{
  "sql": "生成的 SQL 语句",
  "explanation": "用一句话解释这个 SQL 的功能",
  "confidence": 0.95
}}
```"""

# Few-shot 最大 token 预算
FEWSHOT_MAX_TOKENS = 2000
# Few-shot 最大数量
FEWSHOT_MAX_COUNT = 3


class PromptBuilder:
    """Prompt 组装器。

    负责将语义上下文、Few-shot 示例和用户问题组装为完整的 Prompt，
    并通过 TokenBudgetManager 确保不超出 Token 预算。

    Args:
        budget_manager: Token 预算管理器（来自 datapilot-prompt）。
        system_prompt_template: 可选的自定义系统 Prompt 模板。
    """

    def __init__(
        self,
        budget_manager: TokenBudgetManager,
        system_prompt_template: str | None = None,
    ) -> None:
        self._budget_manager = budget_manager
        self._system_prompt_template = system_prompt_template or DEFAULT_NL2SQL_SYSTEM_PROMPT

    def build_nl2sql_prompt(
        self,
        semantic_context: SemanticContext,
        few_shots: list[FewShotExample],
        question: str,
        dialect: str = "mysql",
    ) -> tuple[str, list[FewShotExample]]:
        """构建 NL2SQL Prompt。

        组装顺序：
        1. System Prompt（角色定义+规则+方言说明）
        2. SemanticContext（表结构+指标+维度+关系）
        3. Few-shot Examples（最多 3 个，总 token <= 2000）
        4. User Question

        Args:
            semantic_context: 语义上下文（表结构、指标、维度等）。
            few_shots: Few-shot 示例列表（已按相似度排序）。
            question: 用户问题。
            dialect: 目标 SQL 方言。

        Returns:
            (prompt, used_few_shots)：组装后的 Prompt 和实际使用的 Few-shot 列表。
        """
        # 格式化语义上下文为 Markdown
        context_md = semantic_context.to_markdown()

        # Token 预算检查并裁剪 Few-shot
        used_few_shots = self._apply_token_budget(
            few_shots=few_shots,
            context_md=context_md,
            question=question,
            dialect=dialect,
        )

        # 格式化 Few-shot 为 Prompt 文本
        few_shot_texts = self._format_few_shots(used_few_shots)
        few_shot_section = "\n\n".join(few_shot_texts) if few_shot_texts else "（无参考示例）"

        # 组装 Prompt
        prompt = self._system_prompt_template.format(
            dialect=dialect,
            semantic_context=context_md,
            few_shot_examples=few_shot_section,
            question=question,
        )

        logger.debug(
            "Prompt 组装完成",
            question=question,
            few_shot_count=len(used_few_shots),
            prompt_length=len(prompt),
        )

        return prompt, used_few_shots

    def _apply_token_budget(
        self,
        few_shots: list[FewShotExample],
        context_md: str,
        question: str,
        dialect: str,
    ) -> list[FewShotExample]:
        """应用 Token 预算裁剪 Few-shot 列表。

        策略：
        1. 限制最多 FEWSHOT_MAX_COUNT 个
        2. 累计 Token 不超过 FEWSHOT_MAX_TOKENS
        3. 优先保留相似度高的示例

        Args:
            few_shots: 候选 Few-shot 列表。
            context_md: 语义上下文 Markdown 文本。
            question: 用户问题。
            dialect: SQL 方言。

        Returns:
            裁剪后的 Few-shot 列表。
        """
        if not few_shots:
            return []

        # 按 top_k 截取
        candidates = few_shots[:FEWSHOT_MAX_COUNT]

        # 逐个添加，检查 token 预算
        result: list[FewShotExample] = []
        total_tokens = 0

        for example in candidates:
            example_text = example.to_prompt_text()
            example_tokens = self._budget_manager.estimate_tokens(example_text)

            if total_tokens + example_tokens > FEWSHOT_MAX_TOKENS:
                logger.debug(
                    "Few-shot Token 超预算，跳过示例",
                    question=example.question,
                    example_tokens=example_tokens,
                    total_tokens=total_tokens,
                    max_tokens=FEWSHOT_MAX_TOKENS,
                )
                break

            result.append(example)
            total_tokens += example_tokens

        return result

    @staticmethod
    def _format_few_shots(few_shots: list[FewShotExample]) -> list[str]:
        """将 Few-shot 列表格式化为 Prompt 文本段落。"""
        texts: list[str] = []
        for idx, example in enumerate(few_shots, start=1):
            texts.append(f"### 示例 {idx}\n{example.to_prompt_text()}")
        return texts
