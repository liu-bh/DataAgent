"""LLM SQL 后处理器。

从 LLM JSON 输出中提取 SQL，解析为 sqlglot AST 进行语法验证，
并执行方言转换、添加 LIMIT、移除 SELECT * 等后处理。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)

# 默认 LIMIT 值
DEFAULT_LIMIT = 1000
# 支持 SQL 的 Dialect 列表
SUPPORTED_DIALECTS = ("mysql", "postgresql", "doris", "starrocks", "clickhouse")


@dataclass
class ProcessedSQL:
    """SQL 后处理结果。

    Attributes:
        sql: 最终处理后的 SQL 字符串。
        ast: sqlglot AST 对象（如果解析成功）。
        dialect: 目标 SQL 方言。
        warnings: 处理过程中的警告信息列表。
    """

    sql: str
    ast: object | None = None
    dialect: str = "mysql"
    warnings: list[str] = field(default_factory=list)


class SQLPostProcessor:
    """SQL 后处理器。

    处理流程：
    1. 从 LLM JSON 输出中提取 SQL 字符串
    2. 解析为 sqlglot AST 验证语法
    3. 转换为目标方言
    4. 添加 LIMIT（如果没有）
    5. 移除 SELECT *（替换为显式列名，如果上下文提供了列信息）
    """

    def __init__(self, default_limit: int = DEFAULT_LIMIT) -> None:
        self._default_limit = default_limit

    def process(
        self,
        llm_output: str,
        dialect: str = "mysql",
        available_columns: dict[str, list[str]] | None = None,
    ) -> ProcessedSQL:
        """处理 LLM 输出，提取并验证 SQL。

        Args:
            llm_output: LLM 的原始输出（JSON 格式）。
            dialect: 目标 SQL 方言。
            available_columns: 可用列映射 {table_name: [col1, col2, ...]}，
                用于替换 SELECT *。

        Returns:
            ProcessedSQL 后处理结果。
        """
        warnings: list[str] = []

        # 步骤 1：从 JSON 提取 SQL
        sql = self._extract_sql_from_json(llm_output)
        if sql is None:
            # 尝试直接作为 SQL
            sql = self._clean_sql(llm_output)
            warnings.append("未能从 JSON 中提取 SQL，直接使用原始输出")

        if not sql or not sql.strip():
            return ProcessedSQL(
                sql="",
                dialect=dialect,
                warnings=["LLM 输出为空或无法解析"],
            )

        # 步骤 2：解析为 sqlglot AST
        ast = self._parse_ast(sql, dialect)
        if ast is None:
            # AST 解析失败，返回原始 SQL 并附带警告
            warnings.append("sqlglot AST 解析失败，返回原始 SQL")
            return ProcessedSQL(sql=sql, dialect=dialect, warnings=warnings)

        # 步骤 3：转换为目标方言
        sql = self._render_ast(ast, dialect)

        # 步骤 4：添加 LIMIT（如果没有）
        sql = self._ensure_limit(sql, ast, dialect, warnings)

        # 步骤 5：移除 SELECT *
        sql = self._replace_select_star(sql, available_columns, warnings)

        return ProcessedSQL(
            sql=sql,
            ast=ast,
            dialect=dialect,
            warnings=warnings,
        )

    def _extract_sql_from_json(self, llm_output: str) -> str | None:
        """从 LLM JSON 输出中提取 SQL 字符串。

        支持多种 JSON 格式：
        - 纯 JSON: {"sql": "..."}
        - Markdown 代码块包裹的 JSON

        Args:
            llm_output: LLM 原始输出。

        Returns:
            提取的 SQL 字符串，提取失败返回 None。
        """
        # 移除 Markdown 代码块包裹
        cleaned = re.sub(r"```json\s*", "", llm_output)
        cleaned = re.sub(r"```\s*$", "", cleaned)
        cleaned = cleaned.strip()

        # 尝试解析 JSON
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict) and "sql" in data:
                sql = data["sql"]
                if isinstance(sql, str) and sql.strip():
                    return sql.strip()
        except json.JSONDecodeError:
            pass

        # 尝试在文本中查找 JSON 块
        json_match = re.search(r'\{[^{}]*"sql"\s*:\s*"([^"]+)"[^{}]*\}', llm_output, re.DOTALL)
        if json_match:
            sql = json_match.group(1)
            if sql.strip():
                return sql.strip()

        # 尝试查找 SQL 关键字开头的代码块
        sql_block_match = re.search(
            r"```sql\s*(.*?)```",
            llm_output,
            re.DOTALL,
        )
        if sql_block_match:
            sql = sql_block_match.group(1).strip()
            if sql:
                return sql

        return None

    @staticmethod
    def _clean_sql(text: str) -> str:
        """清理可能的 SQL 文本，去除多余空白和引号。

        Args:
            text: 原始文本。

        Returns:
            清理后的 SQL 字符串。
        """
        sql = text.strip()
        # 去除首尾引号
        if (sql.startswith('"') and sql.endswith('"')) or (
            sql.startswith("'") and sql.endswith("'")
        ):
            sql = sql[1:-1]
        # 去除转义字符
        sql = sql.replace('\\"', '"').replace("\\'", "'")
        # 去除多余换行
        sql = re.sub(r"\n{3,}", "\n\n", sql)
        return sql.strip()

    def _parse_ast(self, sql: str, dialect: str) -> object | None:
        """使用 sqlglot 解析 SQL 为 AST。

        Args:
            sql: SQL 字符串。
            dialect: SQL 方言。

        Returns:
            sqlglot AST 表达式对象，解析失败返回 None。
        """
        try:
            import sqlglot
            from datapilot_sql import SQLBuilder

            # 通过 datapilot-sql 的 SQLBuilder 解析
            builder = SQLBuilder(dialect=dialect)  # type: ignore[no-untyped-call]
            return builder.parse(sql)  # type: ignore[no-untyped-call]
        except ImportError:
            # 降级：直接使用 sqlglot
            try:
                import sqlglot
                return sqlglot.parse_one(sql, read=dialect)
            except Exception as e:
                logger.warning("sqlglot AST 解析失败", sql=sql[:100], error=str(e))
                return None
        except Exception as e:
            logger.warning("SQL AST 解析失败", sql=sql[:100], error=str(e))
            return None

    def _render_ast(self, ast: object, dialect: str) -> str:
        """将 AST 渲染为目标方言的 SQL 字符串。

        Args:
            ast: sqlglot AST 对象。
            dialect: 目标方言。

        Returns:
            渲染后的 SQL 字符串。
        """
        try:
            from datapilot_sql import SQLRenderer

            renderer = SQLRenderer(dialect=dialect)  # type: ignore[no-untyped-call]
            return renderer.render(ast)  # type: ignore[no-untyped-call]
        except ImportError:
            try:
                return ast.sql(dialect=dialect)  # type: ignore[union-attr]
            except Exception as e:
                logger.warning("AST 渲染失败，返回原始 AST str", error=str(e))
                return str(ast)
        except Exception as e:
            logger.warning("AST 渲染失败", error=str(e))
            return str(ast)

    def _ensure_limit(
        self,
        sql: str,
        ast: object,
        dialect: str,
        warnings: list[str],
    ) -> str:
        """检查 SQL 是否包含 LIMIT，如果没有则添加。

        Args:
            sql: 当前 SQL 字符串。
            ast: sqlglot AST 对象。
            dialect: SQL 方言。
            warnings: 警告列表（会被修改）。

        Returns:
            处理后的 SQL 字符串。
        """
        # 检查 SQL 是否已包含 LIMIT 子句
        limit_pattern = re.compile(r"\bLIMIT\s+\d+", re.IGNORECASE)
        if limit_pattern.search(sql):
            return sql

        # 没有包含 LIMIT，添加默认 LIMIT
        try:
            import sqlglot
            parsed = sqlglot.parse_one(sql, read=dialect)
            # 尝试添加 LIMIT
            limited = parsed.limit(self._default_limit)
            warnings.append(f"SQL 未包含 LIMIT，已自动添加 LIMIT {self._default_limit}")
            return limited.sql(dialect=dialect)
        except Exception as e:
            logger.warning("添加 LIMIT 失败", error=str(e))
            # 降级：直接在末尾追加
            warnings.append(f"SQL 未包含 LIMIT，已追加 LIMIT {self._default_limit}（降级处理）")
            return f"{sql}\nLIMIT {self._default_limit}"

    @staticmethod
    def _replace_select_star(
        sql: str,
        available_columns: dict[str, list[str]] | None,
        warnings: list[str],
    ) -> str:
        """检查并尝试替换 SELECT *。

        如果提供了可用列信息且 SQL 中存在 SELECT *，替换为显式列名。

        Args:
            sql: 当前 SQL 字符串。
            available_columns: 可用列映射。
            warnings: 警告列表。

        Returns:
            处理后的 SQL 字符串。
        """
        if not available_columns:
            return sql

        # 检查是否包含 SELECT *
        if "SELECT *" not in sql.upper() and "select *" not in sql:
            return sql

        # 尝试替换第一个 SELECT *
        try:
            import sqlglot
            parsed = sqlglot.parse_one(sql)

            # 找到 SELECT *
            from sqlglot import expressions as exp

            for select in parsed.find_all(exp.Select):
                if any(isinstance(col, exp.Star) for col in select.expressions):
                    # 尝试获取表名
                    table_name = None
                    from_expr = select.find(exp.From)
                    if from_expr:
                        table_name = from_expr.this.alias_or_name

                    if table_name and table_name in available_columns:
                        cols = available_columns[table_name]
                        # 替换 * 为显式列名
                        new_expressions = []
                        for expr in select.expressions:
                            if isinstance(expr, exp.Star):
                                new_expressions.extend(
                                    [sqlglot.exp.Column(this=col) for col in cols]
                                )
                            else:
                                new_expressions.append(expr)
                        select.set("expressions", new_expressions)
                        warnings.append(
                            f"已将 SELECT * 替换为 {table_name} 表的 {len(cols)} 个显式列"
                        )
                        return parsed.sql()

            # 无法确定表名，仅添加警告
            warnings.append("SQL 包含 SELECT *，建议替换为显式列名")
        except Exception as e:
            logger.warning("替换 SELECT * 失败", error=str(e))
            warnings.append("SQL 包含 SELECT *，但替换失败")

        return sql
