"""SQL 解释 Prompt 模板单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 确保项目源码路径可被导入
project_root = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "services"
    / "sql-generator-service"
    / "src"
)
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from datapilot_sqlgen.explanation.prompts import (
    EXPLAIN_SYSTEM_PROMPT,
    build_explain_prompt,
)


class TestExplainPrompt:
    """SQL 解释 Prompt 模板测试。"""

    def test_system_prompt_template_exists(self) -> None:
        """系统 Prompt 模板应存在且包含必要占位符。"""
        assert EXPLAIN_SYSTEM_PROMPT
        assert "{sql}" in EXPLAIN_SYSTEM_PROMPT
        assert "{dialect}" in EXPLAIN_SYSTEM_PROMPT
        assert "{context}" in EXPLAIN_SYSTEM_PROMPT

    def test_build_prompt_basic(self) -> None:
        """基础 Prompt 构建应正确填充模板。"""
        sql = "SELECT id, name FROM users WHERE status = 'active'"
        prompt = build_explain_prompt(sql=sql, dialect="mysql")

        assert "SELECT id, name FROM users" in prompt
        assert "mysql" in prompt
        # 未提供 context 时应显示默认提示
        assert "无额外上下文" in prompt

    def test_build_prompt_with_context(self) -> None:
        """带上下文的 Prompt 应正确填充。"""
        sql = "SELECT COUNT(*) FROM orders"
        context = "orders 表存储电商订单信息，包含 id, amount, status, created_at 列"
        prompt = build_explain_prompt(sql=sql, dialect="mysql", context=context)

        assert "SELECT COUNT(*) FROM orders" in prompt
        assert "mysql" in prompt
        assert "orders 表存储电商订单信息" in prompt
        assert "无额外上下文" not in prompt

    def test_build_prompt_postgresql(self) -> None:
        """PostgreSQL 方言应正确填充。"""
        sql = "SELECT id FROM users WHERE created_at > NOW()"
        prompt = build_explain_prompt(sql=sql, dialect="postgresql")

        assert "SELECT id FROM users" in prompt
        assert "postgresql" in prompt

    def test_build_prompt_empty_context(self) -> None:
        """空字符串上下文应显示默认提示。"""
        prompt = build_explain_prompt(
            sql="SELECT 1",
            dialect="mysql",
            context="",
        )
        assert "无额外上下文" in prompt

    def test_prompt_requires_json_format(self) -> None:
        """Prompt 应要求返回 JSON 格式。"""
        prompt = build_explain_prompt(sql="SELECT 1")
        assert "JSON" in prompt or "json" in prompt
        assert "summary" in prompt
        assert "key_points" in prompt
        assert "potential_issues" in prompt

    def test_prompt_is_chinese(self) -> None:
        """Prompt 应使用中文。"""
        prompt = build_explain_prompt(sql="SELECT 1")
        assert "解释" in prompt or "SQL" in prompt

    def test_build_prompt_multiline_sql(self) -> None:
        """多行 SQL 应正确嵌入 Prompt。"""
        sql = """SELECT u.name, SUM(o.amount) AS total
FROM orders o
JOIN users u ON o.user_id = u.id
GROUP BY u.name
ORDER BY total DESC
LIMIT 10"""
        prompt = build_explain_prompt(sql=sql, dialect="mysql")

        assert "SELECT u.name" in prompt
        assert "orders o" in prompt
        assert "GROUP BY" in prompt
