"""Token 预算管理器。

根据场景类型控制 Prompt 组装后的 Token 数量，超预算时自动裁剪。
中文约 1.5 字符/token，英文约 4 字符/token（混合文本取中间值）。
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Literal

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# 场景 Token 预算配置
# ---------------------------------------------------------------------------

SceneType = Literal["nl2sql", "intent", "explanation", "correction"]

TOKEN_BUDGETS: dict[SceneType, int] = {
    "nl2sql": 8000,
    "intent": 2000,
    "explanation": 2000,
    "correction": 4000,
}


@dataclass
class BudgetCheckResult:
    """Token 预算检查结果。

    Attributes:
        scene: 场景标识。
        budget: 场景总预算。
        system_prompt_tokens: 系统 Prompt token 数。
        context_tokens: 上下文 token 数。
        few_shots_tokens: Few-shot 示例 token 数。
        question_tokens: 用户问题 token 数。
        total_tokens: 实际总 token 数。
        within_budget: 是否在预算范围内。
        truncated: 是否进行了裁剪。
        truncation_detail: 裁剪详情。
    """

    scene: str
    budget: int
    system_prompt_tokens: int
    context_tokens: int
    few_shots_tokens: int
    question_tokens: int
    total_tokens: int
    within_budget: bool
    truncated: bool = False
    truncation_detail: str = ""


class TokenBudgetManager:
    """Token 预算管理器。

    负责 Token 估算、预算检查和 Prompt 组装时的超预算裁剪。

    超预算处理优先级:
    1. 减少 Few-shot 示例数量（3 → 2 → 1 → 0）
    2. 裁剪 Context（按字符比例截断）
    3. 如果仍超预算，返回降级提示
    """

    # Few-shot 最大数量
    MAX_FEW_SHOT_COUNT: int = 3
    # 预留余量（为输出 Token 预留空间），默认预留 10%
    RESERVE_RATIO: float = 0.1

    # ------------------------------------------------------------------
    # Token 估算
    # ------------------------------------------------------------------

    def estimate_tokens(self, text: str) -> int:
        """估算文本的 Token 数量。

        估算策略:
        - 纯中文：约 1.5 字符/token
        - 纯英文：约 4 字符/token
        - 混合文本：根据中文字符比例动态计算

        Args:
            text: 待估算文本。

        Returns:
            估算的 Token 数。
        """
        if not text:
            return 0

        total_chars = len(text)
        if total_chars == 0:
            return 0

        # 统计中文字符数（CJK 统一汉字范围）
        chinese_chars = sum(
            1
            for ch in text
            if unicodedata.category(ch).startswith("Lo")
            or (
                "\u4e00" <= ch <= "\u9fff"  # CJK 统一汉字
                or "\u3400" <= ch <= "\u4dbf"  # CJK 扩展 A
                or "\uf900" <= ch <= "\ufaff"  # CJK 兼容汉字
            )
        )

        chinese_ratio = chinese_chars / total_chars
        # 纯中文约 1.5 字符/token，纯英文约 4 字符/token
        chars_per_token = 4.0 - 2.5 * chinese_ratio

        return max(1, int(total_chars / chars_per_token))

    # ------------------------------------------------------------------
    # 预算检查
    # ------------------------------------------------------------------

    def check_budget(
        self,
        scene: SceneType,
        system_prompt: str,
        context: str,
        few_shots: list[str],
        question: str,
    ) -> BudgetCheckResult:
        """检查各部分 Token 是否在预算范围内。

        Args:
            scene: 场景标识。
            system_prompt: 系统 Prompt 内容。
            context: 语义上下文。
            few_shots: Few-shot 示例列表。
            question: 用户问题。

        Returns:
            BudgetCheckResult 检查结果。
        """
        budget = TOKEN_BUDGETS[scene]
        # 预留余量
        effective_budget = int(budget * (1 - self.RESERVE_RATIO))

        system_prompt_tokens = self.estimate_tokens(system_prompt)
        context_tokens = self.estimate_tokens(context)
        few_shots_text = "\n".join(few_shots)
        few_shots_tokens = self.estimate_tokens(few_shots_text)
        question_tokens = self.estimate_tokens(question)

        total_tokens = (
            system_prompt_tokens + context_tokens + few_shots_tokens + question_tokens
        )

        within_budget = total_tokens <= effective_budget

        return BudgetCheckResult(
            scene=scene,
            budget=budget,
            system_prompt_tokens=system_prompt_tokens,
            context_tokens=context_tokens,
            few_shots_tokens=few_shots_tokens,
            question_tokens=question_tokens,
            total_tokens=total_tokens,
            within_budget=within_budget,
        )

    # ------------------------------------------------------------------
    # Prompt 组装
    # ------------------------------------------------------------------

    def assemble_prompt(
        self,
        template: str,
        context: str,
        few_shots: list[str],
        question: str,
        scene: SceneType,
    ) -> tuple[str, BudgetCheckResult]:
        """组装 Prompt 并确保不超预算。

        超预算处理:
        1. 减少 Few-shot 示例数量（3 → 2 → 1 → 0）
        2. 裁剪 Context（按字符比例截断）
        3. 如果仍超预算，记录警告并返回

        Args:
            template: Prompt 模板（系统 Prompt）。
            context: 语义上下文文本。
            few_shots: Few-shot 示例列表。
            question: 用户问题。
            scene: 场景标识。

        Returns:
            (assembled_prompt, budget_result)：组装后的 Prompt 和预算检查结果。
        """
        budget = TOKEN_BUDGETS[scene]
        effective_budget = int(budget * (1 - self.RESERVE_RATIO))

        template_tokens = self.estimate_tokens(template)
        question_tokens = self.estimate_tokens(question)

        # 计算 context 和 few-shots 的可用预算
        remaining_budget = effective_budget - template_tokens - question_tokens

        truncated = False
        truncation_detail = ""

        # 第一步：检查 few-shots
        adjusted_few_shots = list(few_shots)
        few_shots_text = "\n".join(adjusted_few_shots)
        context_tokens = self.estimate_tokens(context)
        few_shots_tokens = self.estimate_tokens(few_shots_text)

        # 逐步减少 few-shot 数量直到不超预算
        while (
            len(adjusted_few_shots) > 0
            and context_tokens + self.estimate_tokens("\n".join(adjusted_few_shots)) > remaining_budget
        ):
            removed = adjusted_few_shots.pop()
            truncated = True
            truncation_detail += f"移除 Few-shot 示例（剩余 {len(adjusted_few_shots)} 个）; "
            logger.debug(
                "Token 超预算，减少 Few-shot",
                scene=scene,
                remaining=len(adjusted_few_shots),
            )

        few_shots_text = "\n".join(adjusted_few_shots)
        few_shots_tokens = self.estimate_tokens(few_shots_text)

        # 第二步：如果 context + few_shots 仍超预算，裁剪 context
        if context_tokens + few_shots_tokens > remaining_budget and remaining_budget > few_shots_tokens:
            available_for_context = remaining_budget - few_shots_tokens
            if available_for_context > 0:
                # 按比例裁剪 context
                ratio = available_for_context / max(context_tokens, 1)
                new_context_len = int(len(context) * ratio)
                context = context[:new_context_len]
                context_tokens = self.estimate_tokens(context)
                truncated = True
                truncation_detail += f"裁剪 Context 至 {new_context_len} 字符; "
                logger.debug(
                    "Token 超预算，裁剪 Context",
                    scene=scene,
                    new_context_len=new_context_len,
                )

        # 组装 Prompt
        few_shots_section = ""
        if adjusted_few_shots:
            few_shots_section = "\n\n## 参考 SQL 示例\n" + few_shots_text

        assembled = template.replace("{semantic_context}", context)
        assembled = assembled.replace("{few_shot_examples}", few_shots_section)
        assembled = assembled.replace("{question}", question)

        # 最终检查
        budget_result = self.check_budget(
            scene=scene,
            system_prompt=template,
            context=context,
            few_shots=adjusted_few_shots,
            question=question,
        )
        budget_result.truncated = truncated
        budget_result.truncation_detail = truncation_detail

        if not budget_result.within_budget and truncated:
            logger.warning(
                "Prompt 经裁剪后仍超预算",
                scene=scene,
                total_tokens=budget_result.total_tokens,
                budget=budget,
            )

        return assembled, budget_result
