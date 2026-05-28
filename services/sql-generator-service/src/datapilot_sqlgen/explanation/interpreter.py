"""SQL 解释器 — 将 SQL 转换为自然语言解释。

支持两种模式：
1. LLM 增强模式：通过 LLM Router 调用大模型生成自然语言解释。
2. AST 基础分析模式：当没有 LLM Router 时，基于 sqlglot AST 提取 SQL 结构信息，
   生成模板化的解释文本。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import structlog

from .models import SQLExplanation
from .prompts import build_explain_prompt

logger = structlog.get_logger(__name__)

# 尝试导入 LLM Scene 枚举，失败时使用 None（降级到 AST 模式）
try:
    from datapilot_llm.router import Scene  # type: ignore[no-redef]

    _SCENE_EXPLANATION = Scene.EXPLANATION
except ImportError:
    _SCENE_EXPLANATION = None


@dataclass
class _ASTInfo:
    """AST 分析提取的结构信息容器。"""

    select_columns: list[str] = field(default_factory=list)
    from_table: str = ""
    join_tables: list[str] = field(default_factory=list)
    where_conditions: list[str] = field(default_factory=list)
    group_by_columns: list[str] = field(default_factory=list)
    order_by_columns: list[str] = field(default_factory=list)
    has_limit: bool = False
    has_aggregation: bool = False


class SQLInterpreter:
    """SQL 解释器。

    Args:
        llm_router: LLM 路由器实例（可选）。
            如果为 None，将使用 AST 基础分析模式。
    """

    def __init__(self, llm_router: Any | None = None) -> None:
        self._llm_router = llm_router

    async def explain(
        self,
        sql: str,
        dialect: str = "mysql",
        context: str = "",
    ) -> SQLExplanation:
        """解释 SQL 语句。

        如果提供了 LLM Router，则调用 LLM 生成解释；
        否则使用 AST 基础分析模式。

        Args:
            sql: 待解释的 SQL 语句。
            dialect: SQL 方言（如 mysql、postgresql）。
            context: 数据库上下文信息。

        Returns:
            SQLExplanation 解释结果。
        """
        if not sql or not sql.strip():
            return SQLExplanation(
                summary="SQL 语句为空",
                key_points=[],
                potential_issues=["无法解析空 SQL"],
            )

        if self._llm_router is not None:
            return await self._explain_with_llm(sql, dialect, context)

        return self._explain_with_ast(sql, dialect)

    async def _explain_with_llm(
        self,
        sql: str,
        dialect: str,
        context: str,
    ) -> SQLExplanation:
        """通过 LLM 生成 SQL 解释。

        Args:
            sql: 待解释的 SQL 语句。
            dialect: SQL 方言。
            context: 数据库上下文信息。

        Returns:
            SQLExplanation 解释结果。
        """
        try:
            prompt = build_explain_prompt(sql, dialect, context)

            if _SCENE_EXPLANATION is None:
                raise ImportError("LLM Scene 不可用")

            response = await self._llm_router.generate(
                _SCENE_EXPLANATION,
                prompt,
                json_mode=True,
            )

            return self._parse_llm_response(response.content)

        except Exception as e:
            logger.warning(
                "LLM 解释失败，降级到 AST 分析",
                error=str(e),
                sql=sql[:100],
            )
            return self._explain_with_ast(sql, dialect)

    def _explain_with_ast(
        self,
        sql: str,
        dialect: str,
    ) -> SQLExplanation:
        """基于 sqlglot AST 的基础 SQL 分析。

        提取 SELECT 列、FROM 表、JOIN 表、WHERE 条件、GROUP BY、ORDER BY 等，
        生成模板化的解释文本。

        Args:
            sql: 待解释的 SQL 语句。
            dialect: SQL 方言。

        Returns:
            SQLExplanation 基于模板的解释结果。
        """
        try:
            import sqlglot
            from sqlglot import expressions as exp  # noqa: F401
        except ImportError:
            return SQLExplanation(
                summary="（sqlglot 未安装，无法分析 SQL）",
                key_points=[],
                potential_issues=["缺少 sqlglot 依赖"],
            )

        try:
            ast = sqlglot.parse_one(sql, read=dialect)
        except Exception as e:
            logger.warning("AST 解析失败", sql=sql[:100], error=str(e))
            return SQLExplanation(
                summary="SQL 语法可能有误，无法解析",
                key_points=[f"原始 SQL: {sql[:200]}"],
                potential_issues=[f"解析错误: {e}"],
            )

        # 提取 SQL 各子句信息
        info = self._extract_ast_info(ast)

        # 构建解释
        key_points: list[str] = []
        potential_issues: list[str] = []

        # 主查询描述
        if info.from_table:
            desc = f"查询 {info.from_table} 表"
            if info.select_columns:
                desc += f"，选取列: {', '.join(info.select_columns)}"
            summary = desc + "。"
        else:
            summary = "执行 SQL 查询。"

        # 关键信息点
        if info.select_columns:
            key_points.append(f"查询列: {', '.join(info.select_columns)}")
        if info.from_table:
            key_points.append(f"数据来源: {info.from_table} 表")
        if info.join_tables:
            key_points.append(f"关联表: {', '.join(info.join_tables)}")
        if info.where_conditions:
            key_points.append(f"过滤条件: {'; '.join(info.where_conditions)}")
        if info.group_by_columns:
            key_points.append(f"分组依据: {', '.join(info.group_by_columns)}")
        if info.order_by_columns:
            key_points.append(f"排序依据: {', '.join(info.order_by_columns)}")
        if info.has_aggregation:
            key_points.append("包含聚合函数")
        if info.has_limit:
            key_points.append("包含 LIMIT 限制")
        if not info.has_limit:
            potential_issues.append("SQL 未包含 LIMIT，可能导致全表扫描")
        if "SELECT *" in sql.upper() or "select *" in sql:
            potential_issues.append("使用了 SELECT *，建议指定具体列名")

        return SQLExplanation(
            summary=summary,
            key_points=key_points,
            potential_issues=potential_issues,
        )

    def _extract_ast_info(self, ast: Any) -> _ASTInfo:
        """从 sqlglot AST 中提取 SQL 结构信息。

        Args:
            ast: sqlglot AST 对象。

        Returns:
            _ASTInfo 提取的结构信息。
        """
        info = _ASTInfo()

        try:
            from sqlglot import expressions as exp
        except ImportError:
            return info

        # 只处理 SELECT 语句
        select_node: Any = ast
        if isinstance(ast, exp.Subquery):
            select_node = ast.find(exp.Select)
            if select_node is None:
                return info
        elif not isinstance(ast, exp.Select):
            return info

        # 提取 SELECT 列
        for expr in select_node.expressions:
            if isinstance(expr, exp.Star):
                info.select_columns.append("*")
            elif isinstance(expr, exp.Column):
                info.select_columns.append(expr.alias_or_name)
            elif isinstance(expr, exp.Alias):
                info.select_columns.append(expr.alias)
            else:
                col_name = expr.alias_or_name
                info.select_columns.append(col_name)

            # 检查聚合函数
            if isinstance(expr, (exp.Sum, exp.Count, exp.Avg, exp.Min, exp.Max)):
                info.has_aggregation = True
            for _agg_node in expr.find_all((exp.Sum, exp.Count, exp.Avg, exp.Min, exp.Max)):
                info.has_aggregation = True

        # 限制显示的列数量
        if len(info.select_columns) > 5:
            cols_str = ", ".join(info.select_columns[:5])
            total_count = len(info.select_columns)
            info.select_columns = [f"{cols_str}, ...（共 {total_count} 列）"]

        # 提取 FROM 表
        from_clause = select_node.find(exp.From)
        if from_clause:
            from_table_ref = from_clause.this
            if hasattr(from_table_ref, "alias_or_name"):
                info.from_table = from_table_ref.alias_or_name
            else:
                info.from_table = str(from_table_ref)

        # 提取 JOIN 表
        for join in select_node.find_all(exp.Join):
            join_table_ref = join.this
            if hasattr(join_table_ref, "alias_or_name"):
                join_table_name = join_table_ref.alias_or_name
            elif hasattr(join_table_ref, "this"):
                inner = join_table_ref.this
                join_table_name = (
                    inner.alias_or_name if hasattr(inner, "alias_or_name") else str(inner)
                )
            else:
                join_table_name = str(join_table_ref)

            # 获取 JOIN 类型
            join_kind = ""
            if join.kind:
                join_kind = f"{join.kind.upper()} "
            if join_table_name not in info.join_tables:
                info.join_tables.append(f"{join_kind}{join_table_name}")

        # 提取 WHERE 条件
        where_clause = select_node.find(exp.Where)
        if where_clause:
            where_str = str(where_clause.this).strip()
            # 截断过长的条件
            if len(where_str) > 200:
                where_str = where_str[:200] + "..."
            info.where_conditions.append(where_str)

        # 提取 GROUP BY
        group_clause = select_node.find(exp.Group)
        if group_clause:
            for group_expr in group_clause.expressions:
                info.group_by_columns.append(str(group_expr).strip())

        # 提取 ORDER BY
        order_clause = select_node.find(exp.Order)
        if order_clause:
            for ordered in order_clause.expressions:
                col_str = str(ordered.this).strip()
                if ordered.args.get("desc"):
                    col_str += " DESC"
                info.order_by_columns.append(col_str)

        # 检查 LIMIT
        limit_clause = select_node.find(exp.Limit)
        if limit_clause is not None:
            info.has_limit = True

        return info

    @staticmethod
    def _parse_llm_response(content: str) -> SQLExplanation:
        """解析 LLM 返回的 JSON 内容为 SQLExplanation。

        Args:
            content: LLM 返回的 JSON 字符串。

        Returns:
            SQLExplanation 解析结果。
        """
        try:
            # 尝试直接解析 JSON
            data = json.loads(content)
        except json.JSONDecodeError:
            # 尝试从文本中提取 JSON 块
            json_match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    return SQLExplanation(
                        summary="LLM 返回格式异常，无法解析",
                        key_points=[],
                        potential_issues=["LLM 返回内容无法解析为 JSON"],
                    )
            else:
                return SQLExplanation(
                    summary=content[:200] if content else "LLM 返回为空",
                    key_points=[],
                    potential_issues=["LLM 未返回有效 JSON"],
                )

        return SQLExplanation(
            summary=data.get("summary", ""),
            key_points=data.get("key_points", []),
            potential_issues=data.get("potential_issues", []),
        )
