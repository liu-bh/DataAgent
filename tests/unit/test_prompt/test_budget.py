"""Token 预算管理单元测试。

测试 TokenBudgetManager 的 Token 估算、预算检查和 Prompt 组装逻辑。
"""

from __future__ import annotations

import pytest

from datapilot_prompt.budget import TokenBudgetManager, BudgetCheckResult, TOKEN_BUDGETS


@pytest.fixture
def manager() -> TokenBudgetManager:
    """创建 TokenBudgetManager 实例。"""
    return TokenBudgetManager()


class TestEstimateTokens:
    """estimate_tokens Token 估算测试。"""

    def test_empty_string(self, manager: TokenBudgetManager) -> None:
        """空字符串返回 0。"""
        assert manager.estimate_tokens("") == 0

    def test_pure_chinese(self, manager: TokenBudgetManager) -> None:
        """纯中文估算 — 约 1.5 字符/token。"""
        text = "这是一段纯中文测试文本用于验证Token估算的准确性"
        tokens = manager.estimate_tokens(text)
        # 22 个中文字符，约 22/1.5 ≈ 14-15 tokens
        assert 10 < tokens < 20

    def test_pure_english(self, manager: TokenBudgetManager) -> None:
        """纯英文估算 — 约 4 字符/token。"""
        text = "This is a pure English text for testing token estimation accuracy"
        tokens = manager.estimate_tokens(text)
        # 66 个字符，约 66/4 ≈ 16-17 tokens
        assert 10 < tokens < 25

    def test_mixed_text(self, manager: TokenBudgetManager) -> None:
        """中英文混合估算 — 取中间值。"""
        text = "请生成 SELECT * FROM 订单表 WHERE 金额 > 1000 的SQL查询"
        tokens = manager.estimate_tokens(text)
        # 应在纯中文和纯英文之间
        assert tokens > 0

    def test_long_text_proportional(self, manager: TokenBudgetManager) -> None:
        """长文本估算应与文本长度近似成正比。"""
        short = "你好世界" * 10
        long = "你好世界" * 100
        short_tokens = manager.estimate_tokens(short)
        long_tokens = manager.estimate_tokens(long)
        ratio = long_tokens / short_tokens
        # 比例应在 8~12 之间（理想 10）
        assert 7 < ratio < 13

    def test_single_character(self, manager: TokenBudgetManager) -> None:
        """单个字符至少返回 1 token。"""
        assert manager.estimate_tokens("a") == 1
        assert manager.estimate_tokens("你") == 1


class TestCheckBudget:
    """check_budget 预算检查测试。"""

    def test_within_budget_nl2sql(self, manager: TokenBudgetManager) -> None:
        """NL2SQL 场景在预算内。"""
        result = manager.check_budget(
            scene="nl2sql",
            system_prompt="你是 SQL 助手",
            context="订单表、用户表",
            few_shots=["示例1", "示例2"],
            question="上月营收",
        )

        assert result.scene == "nl2sql"
        assert result.budget == 8000
        assert result.within_budget is True
        assert result.total_tokens > 0

    def test_within_budget_intent(self, manager: TokenBudgetManager) -> None:
        """Intent 场景在预算内。"""
        result = manager.check_budget(
            scene="intent",
            system_prompt="你是意图识别助手",
            context="",
            few_shots=[],
            question="查询数据",
        )

        assert result.budget == 2000
        assert result.within_budget is True

    def test_over_budget(self, manager: TokenBudgetManager) -> None:
        """超预算检测。"""
        # 构造一个超长的内容
        long_content = "这是一段很长的内容" * 5000  # 约 40000 字符

        result = manager.check_budget(
            scene="intent",
            system_prompt="你是助手",
            context=long_content,
            few_shots=[],
            question="查询",
        )

        assert result.budget == 2000
        assert result.within_budget is False

    def test_all_budgets_configured(self) -> None:
        """验证所有场景的预算已配置。"""
        assert "nl2sql" in TOKEN_BUDGETS
        assert "intent" in TOKEN_BUDGETS
        assert "explanation" in TOKEN_BUDGETS
        assert "correction" in TOKEN_BUDGETS

    def test_token_breakdown(self, manager: TokenBudgetManager) -> None:
        """验证各部分 Token 明细。"""
        result = manager.check_budget(
            scene="nl2sql",
            system_prompt="系统提示词",
            context="上下文内容",
            few_shots=["示例1"],
            question="问题",
        )

        assert result.system_prompt_tokens > 0
        assert result.question_tokens > 0
        assert result.total_tokens == (
            result.system_prompt_tokens
            + result.context_tokens
            + result.few_shots_tokens
            + result.question_tokens
        )


class TestAssemblePrompt:
    """assemble_prompt Prompt 组装测试。"""

    def test_basic_assembly(self, manager: TokenBudgetManager) -> None:
        """基本组装 — 不超预算。"""
        template = "你是 SQL 助手\n{semantic_context}\n{few_shot_examples}\n{question}"
        context = "订单表结构"
        few_shots = ["示例1", "示例2"]
        question = "上月营收"

        assembled, result = manager.assemble_prompt(
            template=template,
            context=context,
            few_shots=few_shots,
            question=question,
            scene="nl2sql",
        )

        assert "你是 SQL 助手" in assembled
        assert "订单表结构" in assembled
        assert "上月营收" in assembled
        assert result.within_budget is True
        assert result.truncated is False

    def test_truncate_few_shots(self, manager: TokenBudgetManager) -> None:
        """超预算时减少 Few-shot 数量。"""
        template = "你是 SQL 助手\n{semantic_context}\n{few_shot_examples}\n{question}"
        context = "订单表结构"
        # 大量 few-shot 导致超预算（intent 场景预算仅 2000）
        long_shots = [f"示例{i}，这是一个很长的 Few-shot 示例内容" * 50 for i in range(10)]

        assembled, result = manager.assemble_prompt(
            template=template,
            context=context,
            few_shots=long_shots,
            question="查询",
            scene="intent",
        )

        assert result.truncated is True
        assert "Few-shot" in result.truncation_detail or "裁剪" in result.truncation_detail

    def test_truncate_context(self, manager: TokenBudgetManager) -> None:
        """Few-shot 裁剪后仍超预算时裁剪 Context。"""
        template = "你是 SQL 助手\n{semantic_context}\n{few_shot_examples}\n{question}"
        # 超长 context
        long_context = "这是一个很长的上下文内容" * 2000

        assembled, result = manager.assemble_prompt(
            template=template,
            context=long_context,
            few_shots=[],
            question="查询",
            scene="intent",
        )

        # 验证 context 被裁剪
        assert result.truncated is True
        # 组装后的 prompt 中不应包含完整的长 context
        assert len(assembled) < len(long_context) + 500

    def test_no_few_shots_section(self, manager: TokenBudgetManager) -> None:
        """没有 Few-shot 时不添加示例部分。"""
        template = "你是 SQL 助手\n{semantic_context}\n{few_shot_examples}\n{question}"
        context = "订单表"
        question = "营收"

        assembled, result = manager.assemble_prompt(
            template=template,
            context=context,
            few_shots=[],
            question=question,
            scene="nl2sql",
        )

        assert "参考 SQL 示例" not in assembled

    def test_with_few_shots_section(self, manager: TokenBudgetManager) -> None:
        """有 Few-shot 时添加示例部分。"""
        template = "你是 SQL 助手\n{semantic_context}\n{few_shot_examples}\n{question}"
        context = "订单表"

        assembled, _ = manager.assemble_prompt(
            template=template,
            context=context,
            few_shots=["示例问题：营收多少"],
            question="查询",
            scene="nl2sql",
        )

        assert "参考 SQL 示例" in assembled
        assert "示例问题：营收多少" in assembled

    def test_replaces_placeholders(self, manager: TokenBudgetManager) -> None:
        """验证所有占位符被替换。"""
        template = "Context: {semantic_context}\nExamples: {few_shot_examples}\nQ: {question}"

        assembled, _ = manager.assemble_prompt(
            template=template,
            context="表结构",
            few_shots=["示例"],
            question="问题",
            scene="nl2sql",
        )

        assert "{semantic_context}" not in assembled
        assert "{few_shot_examples}" not in assembled
        assert "{question}" not in assembled
