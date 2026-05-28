"""SQL 解释场景 Prompt 模板。

为 LLM 生成 SQL 自然语言解释提供标准化的 Prompt。
"""

from __future__ import annotations

EXPLAIN_SYSTEM_PROMPT: str = """你是一个 SQL 解释助手。请用简洁的中文解释以下 SQL 查询的功能。

## SQL
{sql}

## 方言
{dialect}

## 数据库上下文
{context}

请返回如下 JSON 格式：
{{
  "summary": "一句话解释这个查询的功能",
  "key_points": ["关键信息点1", "关键信息点2", ...],
  "potential_issues": ["潜在问题1", ...]
}}
"""


def build_explain_prompt(
    sql: str,
    dialect: str = "mysql",
    context: str = "",
) -> str:
    """构建 SQL 解释 Prompt。

    Args:
        sql: 待解释的 SQL 语句。
        dialect: SQL 方言（如 mysql、postgresql）。
        context: 数据库上下文信息（如表结构、业务含义等）。

    Returns:
        组装完成后的 Prompt 字符串。
    """
    return EXPLAIN_SYSTEM_PROMPT.format(
        sql=sql,
        dialect=dialect,
        context=context or "（无额外上下文）",
    )
