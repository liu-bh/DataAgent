"""SQL 成本预估模块。

通过 EXPLAIN ANALYZE（有数据库连接时）或 AST 启发式分析（无连接时）
估算 SQL 的执行成本，包括预估行数、执行时间和成本等级。
"""

from __future__ import annotations

import re

import structlog

from datapilot_sqlgen.validation.models import CostEstimate

logger = structlog.get_logger(__name__)

# 方言名映射：DataPilot 标准名 -> sqlglot 方言名
_DIALECT_MAP: dict[str, str] = {
    "postgresql": "postgres",
    "mysql": "mysql",
    "doris": "mysql",
    "starrocks": "mysql",
    "clickhouse": "clickhouse",
}

# 成本等级阈值
_COST_THRESHOLD_LOW = 1000
_COST_THRESHOLD_HIGH = 100000

# 启发式行数因子（用于无连接时的估算）
_HEURISTIC_MULTIPLIERS: dict[str, float] = {
    "count": 1.0,       # COUNT 聚合通常只返回 1 行
    "sum": 1.0,         # SUM 聚合通常只返回 1 行
    "avg": 1.0,         # AVG 聚合通常只返回 1 行
    "min": 1.0,         # MIN 聚合通常只返回 1 行
    "max": 1.0,         # MAX 聚合通常只返回 1 行
    "group_by": 100.0,  # GROUP BY 通常返回中等行数
    "join": 500.0,      # JOIN 可能产生较多行
    "subquery": 200.0,  # 子查询可能增加行数
    "plain_select": 10000.0,  # 普通查询默认假设行数
}


class SQLCostEstimator:
    """SQL 成本预估器。

    如果提供了数据库连接串，执行 EXPLAIN ANALYZE 获取精确预估；
    否则通过 AST 启发式规则进行估算。

    Args:
        connection_url: 可选的数据库连接串。
    """

    def __init__(self, connection_url: str | None = None) -> None:
        self._connection_url = connection_url

    async def estimate(self, sql: str, dialect: str = "mysql") -> CostEstimate:
        """估算 SQL 的执行成本。

        Args:
            sql: 待估算的 SQL 字符串。
            dialect: SQL 方言。

        Returns:
            CostEstimate 成本预估结果。
        """
        if not sql or not sql.strip():
            return CostEstimate(estimated_rows=0, cost_level="low")

        if self._connection_url:
            return await self._estimate_with_connection(sql, dialect)
        return self._estimate_with_ast(sql, dialect)

    # ------------------------------------------------------------------
    # 有数据库连接时的 EXPLAIN ANALYZE
    # ------------------------------------------------------------------

    async def _estimate_with_connection(self, sql: str, dialect: str) -> CostEstimate:
        """使用数据库连接执行 EXPLAIN ANALYZE 获取成本预估。"""
        try:
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

            engine = create_async_engine(self._connection_url)

            try:
                async with engine.begin() as conn:
                    # 检查是否为 SELECT 语句
                    sql_upper = sql.strip().upper()
                    if not sql_upper.startswith("SELECT"):
                        # 非 SELECT 语句不执行 ANALYZE（可能修改数据）
                        return self._estimate_with_ast(sql, dialect)

                    # 构建 EXPLAIN ANALYZE
                    explain_sql = self._build_explain_analyze_sql(sql, dialect)
                    try:
                        result = await conn.execute(text(explain_sql))
                        rows = result.fetchall()
                        explain_output = "\n".join(
                            str(row) for row in rows
                        )
                        return self._parse_explain_analyze(explain_output)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "EXPLAIN ANALYZE 失败，降级为 AST 估算",
                            error=str(exc),
                        )
                        return self._estimate_with_ast(sql, dialect)
            finally:
                await engine.dispose()

        except ImportError:
            logger.warning("sqlalchemy 未安装，降级为 AST 估算")
            return self._estimate_with_ast(sql, dialect)
        except Exception as exc:  # noqa: BLE001
            logger.error("成本预估数据库异常", error=str(exc))
            return self._estimate_with_ast(sql, dialect)

    # ------------------------------------------------------------------
    # 无数据库连接时的 AST 启发式估算
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_with_ast(sql: str, dialect: str) -> CostEstimate:
        """使用 AST 启发式规则估算 SQL 成本。"""
        try:
            import sqlglot
            from sqlglot import expressions as exp

            # 将 DataPilot 方言名转换为 sqlglot 方言名
            sqlglot_dialect = _DIALECT_MAP.get(dialect, dialect)
            ast = sqlglot.parse_one(sql, read=sqlglot_dialect)

            # 基础行数和时间
            estimated_rows = _HEURISTIC_MULTIPLIERS["plain_select"]
            estimated_time_ms = 50.0

            select_node = ast if isinstance(ast, exp.Select) else None

            # 步骤 1：检查聚合函数（聚合显著降低行数）
            has_aggregation = False
            for node in ast.walk():
                if isinstance(node, (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)):
                    has_aggregation = True
                    break

            # 步骤 2：检查 GROUP BY（GROUP BY 决定最终分组数）
            has_group_by = select_node is not None and select_node.args.get("group") is not None

            # 步骤 3：检查 JOIN（增加扫描成本）
            has_join = False
            for node in ast.walk():
                if isinstance(node, exp.Join):
                    has_join = True
                    break

            # 步骤 4：检查子查询（增加复杂度）
            has_subquery = False
            for node in ast.walk():
                if isinstance(node, exp.Subquery):
                    has_subquery = True
                    break

            # 步骤 5：检查 LIMIT
            limit_num: int | None = None
            if select_node and select_node.args.get("limit"):
                limit_node = select_node.args["limit"]
                # sqlglot Limit 节点的值在 .expression.this 属性中
                try:
                    limit_expr = getattr(limit_node, "expression", None)
                    if limit_expr is not None:
                        limit_str = getattr(limit_expr, "this", None)
                        if limit_str is not None:
                            limit_num = int(limit_str)
                except (ValueError, TypeError, AttributeError):
                    pass

            # ---- 根据特征计算预估行数 ----
            if has_aggregation and not has_group_by:
                # 无 GROUP BY 的聚合，返回单行
                estimated_rows = 1
                estimated_time_ms = 20.0
            elif has_group_by:
                # GROUP BY 返回分组行数
                estimated_rows = int(_HEURISTIC_MULTIPLIERS["group_by"])
                estimated_time_ms = 100.0

            # JOIN 增加行数（作为乘数叠加）
            if has_join:
                estimated_rows = int(estimated_rows * 1.5)
                estimated_time_ms *= 2.0

            # 子查询增加复杂度（作为乘数叠加）
            if has_subquery:
                estimated_rows = int(estimated_rows * 1.2)
                estimated_time_ms *= 1.5

            # LIMIT 限制最终行数
            if limit_num is not None:
                estimated_rows = min(estimated_rows, limit_num)

            cost_level = _determine_cost_level(int(estimated_rows))
            explain_output = "启发式估算（未连接数据库）"

            return CostEstimate(
                estimated_rows=int(estimated_rows),
                estimated_time_ms=round(estimated_time_ms, 2),
                cost_level=cost_level,
                explain_output=explain_output,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("AST 启发式估算失败", error=str(exc))
            return CostEstimate(
                estimated_rows=0,
                estimated_time_ms=0.0,
                cost_level="medium",
                explain_output=f"估算失败: {exc}",
            )

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _build_explain_analyze_sql(sql: str, dialect: str) -> str:
        """构建 EXPLAIN ANALYZE SQL。

        Args:
            sql: 原始 SQL。
            dialect: SQL 方言。

        Returns:
            EXPLAIN ANALYZE SQL 字符串。
        """
        if dialect == "postgresql":
            return f"EXPLAIN (ANALYZE, FORMAT TEXT) {sql}"
        if dialect == "clickhouse":
            return f"EXPLAIN PIPELINE {sql}"
        return f"EXPLAIN ANALYZE {sql}"

    @staticmethod
    def _parse_explain_analyze(explain_output: str) -> CostEstimate:
        """解析 EXPLAIN ANALYZE 的输出。

        从 PostgreSQL 的 EXPLAIN ANALYZE 输出中提取行数和执行时间。

        Args:
            explain_output: EXPLAIN ANALYZE 原始输出。

        Returns:
            CostEstimate 预估结果。
        """
        estimated_rows = 0
        estimated_time_ms = 0.0

        # PostgreSQL 格式: "rows=123" 或 "actual rows=123"
        rows_match = re.search(r"(?:actual\s+)?rows\s*=\s*(\d+)", explain_output)
        if rows_match:
            estimated_rows = int(rows_match.group(1))

        # PostgreSQL 格式: "actual time=0.123..0.456" 或 "Execution Time: 12.345 ms"
        time_match = re.search(
            r"(?:actual\s+)?time\s*=\s*[\d.]+\.\.([\d.]+)", explain_output
        )
        if time_match:
            estimated_time_ms = float(time_match.group(1))

        if estimated_time_ms == 0.0:
            exec_match = re.search(
                r"Execution Time:\s*([\d.]+)\s*ms", explain_output
            )
            if exec_match:
                estimated_time_ms = float(exec_match.group(1))

        # MySQL 格式: "rows examined N" 或通过 "cost" 提示
        if estimated_rows == 0:
            mysql_rows = re.search(r"rows(?:\s+examined)?\s*[:=]\s*(\d+)", explain_output, re.IGNORECASE)
            if mysql_rows:
                estimated_rows = int(mysql_rows.group(1))

        cost_level = _determine_cost_level(estimated_rows)

        return CostEstimate(
            estimated_rows=estimated_rows,
            estimated_time_ms=round(estimated_time_ms, 2),
            cost_level=cost_level,
            explain_output=explain_output,
        )


def _determine_cost_level(estimated_rows: int) -> str:
    """根据预估行数确定成本等级。

    Args:
        estimated_rows: 预估影响行数。

    Returns:
        成本等级: "low" / "medium" / "high"。
    """
    if estimated_rows < _COST_THRESHOLD_LOW:
        return "low"
    if estimated_rows <= _COST_THRESHOLD_HIGH:
        return "medium"
    return "high"
