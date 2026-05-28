"""PromptBuilder 组装器单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from datapilot_sqlgen.generator.models import (
    FewShotExample,
    SemanticContext,
)
from datapilot_sqlgen.generator.prompt_builder import (
    FEWSHOT_MAX_COUNT,
    FEWSHOT_MAX_TOKENS,
    PromptBuilder,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def prompt_builder(mock_budget_manager: MagicMock) -> PromptBuilder:
    """创建 PromptBuilder 实例。"""
    return PromptBuilder(budget_manager=mock_budget_manager)


# ---------------------------------------------------------------------------
# 基本组装测试
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    """build_nl2sql_prompt 组装测试。"""

    def test_basic_assembly(
        self,
        prompt_builder: PromptBuilder,
        sample_semantic_context: SemanticContext,
        sample_few_shots: list[FewShotExample],
    ) -> None:
        """基本组装 — 包含所有部分。"""
        prompt, used = prompt_builder.build_nl2sql_prompt(
            semantic_context=sample_semantic_context,
            few_shots=sample_few_shots,
            question="上个月销售额是多少？",
            dialect="mysql",
        )

        # 验证 Prompt 包含关键部分
        assert "SQL 生成助手" in prompt
        assert "orders" in prompt
        assert "GMV" in prompt
        assert "上个月销售额" in prompt
        assert "mysql" in prompt

    def test_no_few_shots(
        self,
        prompt_builder: PromptBuilder,
        sample_semantic_context: SemanticContext,
    ) -> None:
        """没有 Few-shot 时应正常组装。"""
        prompt, used = prompt_builder.build_nl2sql_prompt(
            semantic_context=sample_semantic_context,
            few_shots=[],
            question="销售额多少",
            dialect="mysql",
        )

        assert "无参考示例" in prompt
        assert used == []

    def test_few_shot_count_limit(
        self,
        prompt_builder: PromptBuilder,
        sample_semantic_context: SemanticContext,
    ) -> None:
        """Few-shot 数量不应超过最大限制。"""
        # 创建超过限制的 Few-shot 列表
        many_shots = [
            FewShotExample(
                question=f"测试问题 {i}",
                sql=f"SELECT {i}",
                similarity_score=0.9 - i * 0.1,
            )
            for i in range(10)
        ]

        prompt, used = prompt_builder.build_nl2sql_prompt(
            semantic_context=sample_semantic_context,
            few_shots=many_shots,
            question="销售额多少",
            dialect="mysql",
        )

        assert len(used) <= FEWSHOT_MAX_COUNT

    def test_token_budget_truncation(
        self,
        prompt_builder: PromptBuilder,
        sample_semantic_context: SemanticContext,
        mock_budget_manager: MagicMock,
    ) -> None:
        """超 Token 预算时应裁剪 Few-shot。"""
        # 设置每个示例的 token 很大，触发预算裁剪
        mock_budget_manager.estimate_tokens.return_value = 1500

        shots = [
            FewShotExample(question=f"问题 {i}", sql=f"SQL {i}", similarity_score=0.9 - i * 0.1)
            for i in range(5)
        ]

        prompt, used = prompt_builder.build_nl2sql_prompt(
            semantic_context=sample_semantic_context,
            few_shots=shots,
            question="查询",
            dialect="mysql",
        )

        # 预算为 2000，每个示例 1500 token，最多只能容纳 1 个
        assert len(used) <= 1

    def test_dialect_in_prompt(
        self,
        prompt_builder: PromptBuilder,
        sample_semantic_context: SemanticContext,
    ) -> None:
        """Prompt 应包含方言信息。"""
        prompt, _ = prompt_builder.build_nl2sql_prompt(
            semantic_context=sample_semantic_context,
            few_shots=[],
            question="查询",
            dialect="postgresql",
        )

        assert "postgresql" in prompt

    def test_semantic_context_in_markdown(
        self,
        prompt_builder: PromptBuilder,
        sample_semantic_context: SemanticContext,
    ) -> None:
        """语义上下文应格式化为 Markdown。"""
        prompt, _ = prompt_builder.build_nl2sql_prompt(
            semantic_context=sample_semantic_context,
            few_shots=[],
            question="查询",
            dialect="mysql",
        )

        # 验证 Markdown 表格格式
        assert "可用表" in prompt
        assert "orders" in prompt
        assert "BIGINT" in prompt
        assert "表关联关系" in prompt
        assert "可用指标" in prompt
        assert "可用维度" in prompt

    def test_few_shot_order_preserved(
        self,
        prompt_builder: PromptBuilder,
        sample_semantic_context: SemanticContext,
    ) -> None:
        """Few-shot 示例应按输入顺序保留。"""
        shots = [
            FewShotExample(question="问题A", sql="SQL A", similarity_score=0.9),
            FewShotExample(question="问题B", sql="SQL B", similarity_score=0.8),
            FewShotExample(question="问题C", sql="SQL C", similarity_score=0.7),
        ]

        prompt, used = prompt_builder.build_nl2sql_prompt(
            semantic_context=sample_semantic_context,
            few_shots=shots,
            question="测试",
            dialect="mysql",
        )

        # 验证顺序保持
        assert used[0].question == "问题A"
        assert used[1].question == "问题B"
        assert used[2].question == "问题C"


# ---------------------------------------------------------------------------
# 自定义模板测试
# ---------------------------------------------------------------------------


class TestCustomTemplate:
    """自定义 Prompt 模板测试。"""

    def test_custom_template_used(
        self,
        mock_budget_manager: MagicMock,
        sample_semantic_context: SemanticContext,
    ) -> None:
        """应使用自定义模板。"""
        custom_template = "自定义模板: {question} {semantic_context} {few_shot_examples} {dialect}"
        builder = PromptBuilder(
            budget_manager=mock_budget_manager,
            system_prompt_template=custom_template,
        )

        prompt, _ = builder.build_nl2sql_prompt(
            semantic_context=sample_semantic_context,
            few_shots=[],
            question="测试",
            dialect="mysql",
        )

        assert "自定义模板" in prompt
        assert "{question}" not in prompt


# ---------------------------------------------------------------------------
# SemanticContext Markdown 格式化测试
# ---------------------------------------------------------------------------


class TestSemanticContextMarkdown:
    """SemanticContext.to_markdown() 测试。"""

    def test_empty_context(self) -> None:
        """空上下文应返回空字符串。"""
        ctx = SemanticContext()
        md = ctx.to_markdown()
        assert md == ""

    def test_tables_only(self) -> None:
        """只有表信息的上下文格式化。"""
        from datapilot_sqlgen.generator.models import ColumnInfo, TableInfo

        ctx = SemanticContext(
            tables=[
                TableInfo(
                    table_name="test_table",
                    description="测试表",
                    columns=[
                        ColumnInfo(name="id", col_type="INT", description="ID"),
                        ColumnInfo(name="name", col_type="VARCHAR(100)", description="名称"),
                    ],
                ),
            ],
        )
        md = ctx.to_markdown()
        assert "test_table" in md
        assert "测试表" in md
        assert "id" in md
        assert "INT" in md

    def test_metrics_only(self) -> None:
        """只有指标信息的上下文格式化。"""
        from datapilot_sqlgen.generator.models import MetricInfo

        ctx = SemanticContext(
            metrics=[
                MetricInfo(name="GMV", calculation="SUM(amount)", unit="元"),
            ],
        )
        md = ctx.to_markdown()
        assert "GMV" in md
        assert "SUM(amount)" in md
        assert "元" in md

    def test_relationships_only(self) -> None:
        """只有关系的上下文格式化。"""
        from datapilot_sqlgen.generator.models import TableRelationship

        ctx = SemanticContext(
            relationships=[
                TableRelationship(
                    left_table="orders",
                    right_table="users",
                    join_condition="orders.user_id = users.id",
                    join_type="left",
                ),
            ],
        )
        md = ctx.to_markdown()
        assert "orders" in md
        assert "users" in md
        assert "LEFT JOIN" in md
