"""场景化纠错 Prompt 模板。

为每种 ErrorCategory 定义专用的纠错 Prompt，包含错误上下文、可用元数据，
以及期望的 JSON 输出格式。通过差异化 Prompt 提升纠错准确率。
"""

from __future__ import annotations

from typing import Any

import structlog

from .models import ErrorCategory

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# System Prompt — 纠错角色的通用设定
# ---------------------------------------------------------------------------

_CORRECTION_SYSTEM_PROMPT = """你是一个专业的 SQL 纠错专家。当 SQL 执行失败时，你需要根据错误信息和上下文，给出修正后的 SQL。

## 规则
1. 只修正导致错误的部分，不要改变查询的业务意图
2. 修正后的 SQL 必须语法正确且可执行
3. 如果提供了可用表/列信息，只能使用其中列出的表名和列名
4. 不要添加不必要的注释或说明

## 输出格式
严格返回如下 JSON 格式（不要包含其他内容）：
```json
{
  "sql": "修正后的 SQL",
  "fix_explanation": "修复说明"
}
```"""

# ---------------------------------------------------------------------------
# 各错误类别的用户 Prompt 模板
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATES: dict[ErrorCategory, str] = {
    # --- syntax_error: SQL 语法错误 ---
    ErrorCategory.SYNTAX_ERROR: """## 错误类型：SQL 语法错误

以下 SQL 执行时出现语法错误，请修复语法问题。

### 原始 SQL
```sql
{sql}
```

### 错误信息
```
{error_message}
```

{context_section}

请修正上述 SQL 的语法错误，返回修正后的 SQL 和修复说明。""",
    # --- table_not_found: 表不存在 ---
    ErrorCategory.TABLE_NOT_FOUND: """## 错误类型：表不存在

以下 SQL 引用了不存在的表，请替换为正确的表名。

### 原始 SQL
```sql
{sql}
```

### 错误信息
```
{error_message}
```

### 可用的表列表
{available_tables}

{context_section}

请根据可用的表列表修正 SQL，替换不存在的表名，返回修正后的 SQL 和修复说明。""",
    # --- column_not_found: 列不存在 ---
    ErrorCategory.COLUMN_NOT_FOUND: """## 错误类型：列不存在

以下 SQL 引用了不存在的列，请替换为正确的列名。

### 原始 SQL
```sql
{sql}
```

### 错误信息
```
{error_message}
```

### 可用的列信息
{available_columns}

{context_section}

请根据可用的列信息修正 SQL，替换不存在的列名或解决歧义列问题，返回修正后的 SQL 和修复说明。""",
    # --- empty_result: 结果为空 ---
    ErrorCategory.EMPTY_RESULT: """## 错误类型：查询结果为空

以下 SQL 执行成功但返回了空结果，请尝试放宽查询条件。

### 原始 SQL
```sql
{sql}
```

### 背景说明
```
{error_message}
```

{context_section}

请尝试以下策略修正 SQL（按优先级）：
1. 放宽 WHERE 条件（如扩大时间范围、移除过严的过滤条件）
2. 如果使用了 JOIN，尝试改为 LEFT JOIN
3. 如果 GROUP BY 后结果为空，检查聚合逻辑是否合理

返回修正后的 SQL 和修复说明。""",
    # --- timeout: 执行超时 ---
    ErrorCategory.TIMEOUT: """## 错误类型：执行超时

以下 SQL 执行超时，请优化查询性能。

### 原始 SQL
```sql
{sql}
```

### 错误信息
```
{error_message}
```

{context_section}

请尝试以下策略修正 SQL（按优先级）：
1. 添加 LIMIT 限制返回行数
2. 缩小时间范围
3. 移除不必要的 JOIN
4. 在 WHERE 子句中添加更多过滤条件
5. 使用子查询替代复杂的关联

返回修正后的 SQL 和修复说明。""",
    # --- other: 其他错误 ---
    ErrorCategory.OTHER: """## 错误类型：执行错误

以下 SQL 执行时出现错误，请尝试修正。

### 原始 SQL
```sql
{sql}
```

### 错误信息
```
{error_message}
```

{context_section}

请分析错误原因并修正 SQL，返回修正后的 SQL 和修复说明。""",
}


class CorrectionPromptBuilder:
    """纠错 Prompt 构建器。

    根据错误类型选择对应的 Prompt 模板，注入错误信息和上下文，
    生成完整的纠错 Prompt（system + user）。

    Usage::

        builder = CorrectionPromptBuilder()
        system_prompt, user_prompt = builder.build(
            category=ErrorCategory.TABLE_NOT_FOUND,
            sql="SELECT * FROM orderz",
            error_message='relation "orderz" does not exist',
            context={"available_tables": ["orders", "users"]},
        )
    """

    def build(
        self,
        category: ErrorCategory,
        sql: str,
        error_message: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """构建纠错 Prompt。

        Args:
            category: 错误类别。
            sql: 出错的原始 SQL。
            error_message: 数据库返回的错误信息。
            context: 额外上下文，支持以下字段：
                - available_tables: list[str] 可用表名列表
                - available_columns: dict[str, list[str]] 表名到列名的映射
                - dialect: str SQL 方言（如 "mysql"、"postgres"）
                - attempt_number: int 当前纠错轮次编号

        Returns:
            (system_prompt, user_prompt) 元组。
        """
        context = context or {}

        # 格式化上下文段落
        context_section = self._format_context_section(context)

        # 获取对应类别的模板
        template = _PROMPT_TEMPLATES.get(category, _PROMPT_TEMPLATES[ErrorCategory.OTHER])

        # 格式化可用表/列信息
        available_tables = self._format_available_tables(context.get("available_tables"))
        available_columns = self._format_available_columns(context.get("available_columns"))

        # 如果是多轮纠错，在 user prompt 开头追加轮次提示
        attempt_prefix = ""
        attempt_number = context.get("attempt_number", 1)
        if attempt_number > 1:
            attempt_prefix = f"**注意：这是第 {attempt_number} 轮纠错，前几轮均未通过验证。请仔细分析错误原因，避免重复相同的错误。**\n\n"

        # 渲染 user prompt
        user_prompt = template.format(
            sql=sql,
            error_message=error_message,
            available_tables=available_tables,
            available_columns=available_columns,
            context_section=context_section,
        )

        # 在 user prompt 开头插入轮次提示
        if attempt_prefix:
            user_prompt = attempt_prefix + user_prompt

        logger.debug(
            "correction_prompt_built",
            category=category.value,
            sql_length=len(sql),
            prompt_length=len(user_prompt),
            attempt_number=attempt_number,
        )

        return _CORRECTION_SYSTEM_PROMPT, user_prompt

    @staticmethod
    def _format_context_section(context: dict[str, Any]) -> str:
        """格式化额外上下文为 Prompt 文本段落。"""
        if not context:
            return ""

        sections: list[str] = []

        if "dialect" in context:
            sections.append(f"### SQL 方言\n使用 `{context['dialect']}` 语法。")

        if context.get("previous_corrections"):
            sections.append("### 历史纠错记录（已失败的修正）")
            for idx, corr in enumerate(context["previous_corrections"], start=1):
                sections.append(f"{idx}. {corr}")

        return "\n".join(sections) if sections else ""

    @staticmethod
    def _format_available_tables(tables: Any) -> str:
        """格式化可用表列表为 Markdown 文本。"""
        if not tables:
            return "（未提供可用表信息）"

        if isinstance(tables, list):
            lines = [f"- `{t}`" for t in tables]
            return "\n".join(lines)

        return str(tables)

    @staticmethod
    def _format_available_columns(columns: Any) -> str:
        """格式化可用列信息为 Markdown 文本。"""
        if not columns:
            return "（未提供可用列信息）"

        if isinstance(columns, dict):
            lines: list[str] = []
            for table_name, cols in columns.items():
                if isinstance(cols, list):
                    col_list = ", ".join(f"`{c}`" for c in cols)
                    lines.append(f"- **{table_name}**: {col_list}")
                else:
                    lines.append(f"- **{table_name}**: {cols}")
            return "\n".join(lines)

        return str(columns)
