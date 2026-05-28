"""SQL Dry-run 预执行模块。

在只读事务中对 SQL 执行 EXPLAIN（非 ANALYZE）以验证表/列存在性，
无需实际运行查询。当数据库连接不可用时，降级为 AST 级别的静态检查。
"""

from __future__ import annotations

import re

import structlog

from datapilot_sqlgen.validation.models import DryRunResult

logger = structlog.get_logger(__name__)

# 需要排除的 sqlglot 内置虚拟表
_BUILTIN_TABLES = frozenset({"dual", "information_schema", "sys", "performance_schema"})

# 方言名映射：DataPilot 标准名 -> sqlglot 方言名
_DIALECT_MAP: dict[str, str] = {
    "postgresql": "postgres",
    "mysql": "mysql",
    "doris": "mysql",
    "starrocks": "mysql",
    "clickhouse": "clickhouse",
}


class SQLDryRunner:
    """SQL Dry-run 预执行器。

    如果提供了数据库连接串，在只读事务中执行 EXPLAIN 以验证 SQL；
    否则使用 sqlglot AST 进行静态语法检查。

    Args:
        connection_url: 可选的数据库连接串。
    """

    def __init__(self, connection_url: str | None = None) -> None:
        self._connection_url = connection_url

    async def check(self, sql: str, dialect: str = "mysql") -> DryRunResult:
        """对 SQL 执行 Dry-run 检查。

        Args:
            sql: 待检查的 SQL 字符串。
            dialect: SQL 方言。

        Returns:
            DryRunResult 包含检查结果。
        """
        if not sql or not sql.strip():
            return DryRunResult(success=False, error="SQL 为空")

        if self._connection_url:
            return await self._check_with_connection(sql, dialect)
        return self._check_with_ast(sql, dialect)

    # ------------------------------------------------------------------
    # 有数据库连接时的 EXPLAIN 检查
    # ------------------------------------------------------------------

    async def _check_with_connection(self, sql: str, dialect: str) -> DryRunResult:
        """使用数据库连接执行 EXPLAIN 检查。"""
        try:
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

            engine = create_async_engine(self._connection_url)
            checked_tables: list[str] = []
            warnings: list[str] = []

            try:
                async with engine.begin() as conn:
                    # 使用只读事务
                    if dialect == "postgresql":
                        await conn.execute(text("SET TRANSACTION READ ONLY"))

                    # 获取 SQL 引用的表名
                    tables = self._extract_table_names(sql, dialect)
                    checked_tables = list(tables)

                    # 逐表检查是否存在
                    for table in tables:
                        if table.lower() in _BUILTIN_TABLES:
                            continue
                        try:
                            await conn.execute(
                                text(
                                    f"SELECT 1 FROM {_quote_identifier(table, dialect)} LIMIT 0"
                                )
                            )
                        except Exception as exc:  # noqa: BLE001
                            warnings.append(f"表 '{table}' 可能不存在: {exc}")

                    # 执行 EXPLAIN（非 ANALYZE）
                    explain_sql = self._build_explain_sql(sql, dialect)
                    try:
                        result = await conn.execute(text(explain_sql))
                        explain_rows = result.fetchall()
                        logger.debug(
                            "EXPLAIN 执行成功",
                            tables=checked_tables,
                            explain_rows=len(explain_rows),
                        )
                    except Exception as exc:  # noqa: BLE001
                        error_msg = str(exc)
                        # 提取友好错误信息
                        friendly_msg = self._extract_friendly_error(error_msg)
                        return DryRunResult(
                            success=False,
                            error=friendly_msg,
                            checked_tables=checked_tables,
                        )

                return DryRunResult(
                    success=True,
                    checked_tables=checked_tables,
                    warnings=warnings,
                )
            finally:
                await engine.dispose()

        except ImportError:
            logger.warning("sqlalchemy 未安装，降级为 AST 检查")
            return self._check_with_ast(sql, dialect)
        except Exception as exc:  # noqa: BLE001
            logger.error("Dry-run 数据库检查异常", error=str(exc))
            return DryRunResult(
                success=False,
                error=f"数据库连接失败: {exc}",
                warnings=[],
            )

    # ------------------------------------------------------------------
    # 无数据库连接时的 AST 检查
    # ------------------------------------------------------------------

    @staticmethod
    def _check_with_ast(sql: str, dialect: str) -> DryRunResult:
        """使用 sqlglot AST 进行静态语法检查。"""
        try:
            import sqlglot

            # 将 DataPilot 方言名转换为 sqlglot 方言名
            sqlglot_dialect = _DIALECT_MAP.get(dialect, dialect)
            ast = sqlglot.parse_one(sql, read=sqlglot_dialect)
            # 提取引用的表名
            tables: set[str] = set()
            from sqlglot import expressions as exp

            for node in ast.walk():
                if isinstance(node, exp.Table):
                    name = node.name
                    if name.lower() not in _BUILTIN_TABLES:
                        tables.add(name)

            return DryRunResult(
                success=True,
                checked_tables=sorted(tables),
                warnings=["未连接数据库，仅执行 AST 级别检查"],
            )
        except Exception as exc:  # noqa: BLE001
            return DryRunResult(
                success=False,
                error=f"SQL 语法解析失败: {exc}",
            )

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_table_names(sql: str, dialect: str) -> set[str]:
        """从 SQL 中提取表名。

        Args:
            sql: SQL 字符串。
            dialect: SQL 方言。

        Returns:
            去重后的表名集合。
        """
        try:
            import sqlglot
            from sqlglot import expressions as exp

            # 将 DataPilot 方言名转换为 sqlglot 方言名
            sqlglot_dialect = _DIALECT_MAP.get(dialect, dialect)
            ast = sqlglot.parse_one(sql, read=sqlglot_dialect)
            tables: set[str] = set()
            for node in ast.walk():
                if isinstance(node, exp.Table):
                    name = node.name
                    if name.lower() not in _BUILTIN_TABLES:
                        tables.add(name)
            return tables
        except Exception:  # noqa: BLE001
            return set()

    @staticmethod
    def _build_explain_sql(sql: str, dialect: str) -> str:
        """构建 EXPLAIN SQL（不使用 ANALYZE，避免实际执行）。"""
        # 确保是 SELECT 语句才 EXPLAIN
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            # 对非 SELECT 语句，仍尝试 EXPLAIN
            pass

        if dialect == "postgresql":
            return f"EXPLAIN {sql}"
        return f"EXPLAIN {sql}"

    @staticmethod
    def _extract_friendly_error(error_msg: str) -> str:
        """从数据库错误信息中提取友好描述。

        Args:
            error_msg: 原始数据库错误消息。

        Returns:
            友好的错误描述。
        """
        # 常见错误模式匹配
        patterns = [
            (r"table.*?\"?(\w+)\"?\.?\"?(\w+)\"?\s+doesn't exist", r"表 '\1.\2' 不存在"),
            (r"relation.*?\"?(\w+)\"?\"?(\w+)\"?\s+does not exist", r"表 '\1.\2' 不存在"),
            (r"column.*?\"?(\w+)\"?\.?\"?(\w+)\"?\s+does not exist", r"列 '\1.\2' 不存在"),
            (r"unknown column.*?['\"]?(\w+)['\"]?", r"未知列 '\1'"),
            (r"Table.*?'(\w+\.\w+)'.*?doesn't exist", r"表 '\1' 不存在"),
        ]
        for pattern, replacement in patterns:
            match = re.search(pattern, error_msg, re.IGNORECASE)
            if match:
                return match.expand(replacement)

        # 截断过长信息
        if len(error_msg) > 200:
            return error_msg[:200] + "..."
        return error_msg


def _quote_identifier(name: str, dialect: str) -> str:
    """根据方言引用标识符。

    Args:
        name: 标识符名称。
        dialect: SQL 方言。

    Returns:
        引用后的标识符。
    """
    if dialect == "postgresql":
        return f'"{name}"'
    return f"`{name}`"
