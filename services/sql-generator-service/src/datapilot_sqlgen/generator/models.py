"""NL2SQL 流程数据模型。

定义 Pipeline 各阶段使用的数据类，包括 NL2SQLResult、SemanticContext 等。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# 意图类型使用 intent/types.py 中的 IntentType（StrEnum）
# 此处不再重复定义


# ---------------------------------------------------------------------------
# 语义上下文
# ---------------------------------------------------------------------------


@dataclass
class ColumnInfo:
    """列信息。"""

    name: str
    col_type: str
    description: str = ""
    is_primary_key: bool = False


@dataclass
class TableInfo:
    """表信息。"""

    table_name: str
    description: str = ""
    columns: list[ColumnInfo] = field(default_factory=list)


@dataclass
class TableRelationship:
    """表关联关系。"""

    left_table: str
    right_table: str
    join_condition: str
    join_type: str = "inner"  # inner / left / right / full


@dataclass
class MetricInfo:
    """业务指标定义。"""

    name: str
    calculation: str
    unit: str = ""
    description: str = ""


@dataclass
class DimensionInfo:
    """分析维度定义。"""

    name: str
    column_name: str
    table_name: str = ""
    synonyms: list[str] = field(default_factory=list)


@dataclass
class SemanticContext:
    """语义上下文 — 从语义层获取的表结构、指标、维度和关系信息。"""

    tables: list[TableInfo] = field(default_factory=list)
    relationships: list[TableRelationship] = field(default_factory=list)
    metrics: list[MetricInfo] = field(default_factory=list)
    dimensions: list[DimensionInfo] = field(default_factory=list)
    dialect: str = "mysql"

    def to_markdown(self) -> str:
        """将语义上下文格式化为 Markdown 文本（用于 Prompt 注入）。

        按照 prompt-engineering.md 规范，使用 Markdown 表格格式。

        Returns:
            Markdown 格式的语义上下文文本。
        """
        sections: list[str] = []

        # 可用表
        if self.tables:
            sections.append("## 可用表\n")
            for table in self.tables:
                sections.append(f"\n### {table.table_name}（{table.description}）\n")
                sections.append("| 列名 | 类型 | 说明 |")
                sections.append("|------|------|------|")
                if table.columns:
                    for col in table.columns:
                        desc = col.description or ""
                        sections.append(f"| {col.name} | {col.col_type} | {desc} |")

        # 表关联关系
        if self.relationships:
            sections.append("\n## 表关联关系")
            for rel in self.relationships:
                sections.append(
                    f"- {rel.left_table} {rel.join_type.upper()} JOIN {rel.right_table} "
                    f"ON {rel.join_condition}"
                )

        # 可用指标
        if self.metrics:
            sections.append("\n## 可用指标")
            for metric in self.metrics:
                unit_str = f"（{metric.unit}）" if metric.unit else ""
                sections.append(f"- {metric.name}{unit_str} = {metric.calculation}")

        # 可用维度
        if self.dimensions:
            sections.append("\n## 可用维度")
            for dim in self.dimensions:
                table_str = f"（{dim.table_name}.{dim.column_name}）"
                synonyms_str = ""
                if dim.synonyms:
                    synonyms_str = f"，同义词：{', '.join(dim.synonyms)}"
                sections.append(f"- {dim.name}{table_str}{synonyms_str}")

        return "\n".join(sections)


# ---------------------------------------------------------------------------
# NL2SQL 结果
# ---------------------------------------------------------------------------


@dataclass
class NL2SQLResult:
    """NL2SQL Pipeline 输出结果。"""

    sql: str
    sql_dialect: str
    explanation: str = ""
    confidence: float = 0.0
    used_few_shots: list[str] = field(default_factory=list)
    latency_ms: int = 0
    intent: str = "sql_query"
    # 超出范围或闲聊时的文本回复
    text_response: str = ""
    # 警告信息（如 SELECT * 被替换、添加了 LIMIT 等）
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Few-shot 示例
# ---------------------------------------------------------------------------


@dataclass
class FewShotExample:
    """Few-shot 示例。"""

    question: str
    sql: str
    domain: str = ""
    difficulty: Literal["simple", "medium", "complex"] = "simple"
    similarity_score: float = 0.0

    def to_prompt_text(self) -> str:
        """格式化为 Prompt 可用的文本。"""
        return f"问题：{self.question}\nSQL：\n{self.sql}"
