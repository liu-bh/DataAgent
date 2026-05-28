"""SQLDryRunner 单元测试（无连接时的 AST 级别检查）。"""

from __future__ import annotations

import pytest

from datapilot_sqlgen.validation.dryrun import SQLDryRunner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dry_runner() -> SQLDryRunner:
    """创建无连接的 SQLDryRunner 实例。"""
    return SQLDryRunner(connection_url=None)


# ---------------------------------------------------------------------------
# AST 级别检查测试
# ---------------------------------------------------------------------------


class TestASTDryRun:
    """无数据库连接时的 AST 级别 Dry-run 测试。"""

    @pytest.mark.asyncio
    async def test_valid_select_sql(self, dry_runner: SQLDryRunner) -> None:
        """有效的 SELECT 语句应返回成功。"""
        result = await dry_runner.check("SELECT id, name FROM users", dialect="mysql")
        assert result.success is True
        assert "users" in result.checked_tables

    @pytest.mark.asyncio
    async def test_valid_join_sql(self, dry_runner: SQLDryRunner) -> None:
        """包含 JOIN 的 SQL 应识别多个表。"""
        result = await dry_runner.check(
            "SELECT o.id, u.name FROM orders o JOIN users u ON o.user_id = u.id",
            dialect="mysql",
        )
        assert result.success is True
        assert "orders" in result.checked_tables
        assert "users" in result.checked_tables

    @pytest.mark.asyncio
    async def test_empty_sql(self, dry_runner: SQLDryRunner) -> None:
        """空 SQL 应返回失败。"""
        result = await dry_runner.check("", dialect="mysql")
        assert result.success is False
        assert "空" in result.error

    @pytest.mark.asyncio
    async def test_whitespace_sql(self, dry_runner: SQLDryRunner) -> None:
        """仅空白的 SQL 应返回失败。"""
        result = await dry_runner.check("   \n\t  ", dialect="mysql")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_invalid_sql_syntax(self, dry_runner: SQLDryRunner) -> None:
        """无效 SQL 语法应返回失败。

        注意：sqlglot 会将某些无效 SQL 解析为表达式（如 Mul），而非语法错误。
        使用明确的非法输入来触发解析失败。
        """
        result = await dry_runner.check("SELECT WHERE FROM HAVING GROUP", dialect="mysql")
        assert result.success is False
        assert "解析失败" in result.error

    @pytest.mark.asyncio
    async def test_no_connection_warning(self, dry_runner: SQLDryRunner) -> None:
        """无连接时应包含 AST 级别检查的警告。"""
        result = await dry_runner.check("SELECT 1", dialect="mysql")
        assert result.success is True
        assert any("AST" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_builtin_table_excluded(self, dry_runner: SQLDryRunner) -> None:
        """内置虚拟表（如 dual）应从检查列表中排除。"""
        result = await dry_runner.check("SELECT 1 FROM dual", dialect="mysql")
        assert result.success is True
        assert "dual" not in result.checked_tables

    @pytest.mark.asyncio
    async def test_postgresql_dialect(self, dry_runner: SQLDryRunner) -> None:
        """PostgreSQL 方言应正常解析（内部映射为 sqlglot 的 'postgres'）。"""
        result = await dry_runner.check(
            "SELECT id, name FROM users WHERE created_at > NOW()",
            dialect="postgresql",
        )
        assert result.success is True
        assert "users" in result.checked_tables

    @pytest.mark.asyncio
    async def test_subquery_tables(self, dry_runner: SQLDryRunner) -> None:
        """子查询中引用的表应被识别。"""
        result = await dry_runner.check(
            "SELECT * FROM (SELECT id FROM orders WHERE amount > 100) sub",
            dialect="mysql",
        )
        assert result.success is True
        assert "orders" in result.checked_tables

    @pytest.mark.asyncio
    async def test_aggregation_sql(self, dry_runner: SQLDryRunner) -> None:
        """包含聚合函数的 SQL 应正常解析。"""
        result = await dry_runner.check(
            "SELECT COUNT(*), SUM(amount) FROM orders GROUP BY status",
            dialect="mysql",
        )
        assert result.success is True
        assert "orders" in result.checked_tables

    @pytest.mark.asyncio
    async def test_checked_tables_sorted(self, dry_runner: SQLDryRunner) -> None:
        """检查的表名列表应按字母排序。"""
        result = await dry_runner.check(
            "SELECT * FROM users u JOIN orders o ON u.id = o.user_id",
            dialect="mysql",
        )
        assert result.checked_tables == sorted(result.checked_tables)


# ---------------------------------------------------------------------------
# _extract_table_names 静态方法测试
# ---------------------------------------------------------------------------


class TestExtractTableNames:
    """_extract_table_names 静态方法测试。"""

    def test_simple_select(self) -> None:
        """简单 SELECT 应提取表名。"""
        tables = SQLDryRunner._extract_table_names("SELECT * FROM users", "mysql")
        assert "users" in tables

    def test_multiple_tables(self) -> None:
        """多表 JOIN 应提取所有表名。"""
        tables = SQLDryRunner._extract_table_names(
            "SELECT * FROM orders o JOIN users u ON o.user_id = u.id",
            "mysql",
        )
        assert "orders" in tables
        assert "users" in tables

    def test_empty_invalid_sql(self) -> None:
        """无效 SQL 应返回空集合。"""
        tables = SQLDryRunner._extract_table_names("NOT SQL", "mysql")
        assert tables == set()


# ---------------------------------------------------------------------------
# _extract_friendly_error 静态方法测试
# ---------------------------------------------------------------------------


class TestExtractFriendlyError:
    """_extract_friendly_error 静态方法测试。"""

    def test_mysql_table_not_exists(self) -> None:
        """MySQL 表不存在错误应提取友好信息。"""
        error = "Table 'mydb.orders' doesn't exist"
        result = SQLDryRunner._extract_friendly_error(error)
        assert "不存在" in result

    def test_postgres_table_not_exists(self) -> None:
        """PostgreSQL 表不存在错误应提取友好信息。"""
        error = 'relation "public.orders" does not exist'
        result = SQLDryRunner._extract_friendly_error(error)
        assert "不存在" in result

    def test_unknown_error(self) -> None:
        """未知错误应截断过长信息。"""
        long_error = "X" * 300
        result = SQLDryRunner._extract_friendly_error(long_error)
        assert len(result) <= 210

    def test_short_error_unchanged(self) -> None:
        """短错误信息应保持原样。"""
        error = "some short error"
        result = SQLDryRunner._extract_friendly_error(error)
        assert result == error
