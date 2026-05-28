"""datapilot_sql.transformer 单元测试。

覆盖 WHERE 注入、列移除、方言转换、LIMIT 添加。
"""

from __future__ import annotations

import sqlglot

from datapilot_sql.builder import SQLBuilder
from datapilot_sql.dialect import Dialect
from datapilot_sql.transformer import SQLTransformer


class TestInjectWhere:
    """RBAC WHERE 条件注入测试。"""

    def test_inject_into_query_without_where(self) -> None:
        """对没有 WHERE 的查询注入条件。"""
        ast = sqlglot.parse_one("SELECT * FROM orders")
        transformer = SQLTransformer()
        result = transformer.inject_where(ast, "region IN ('华东', '华南')")
        sql = result.sql()
        assert "WHERE" in sql.upper()
        assert "region" in sql

    def test_inject_into_query_with_existing_where(self) -> None:
        """对已有 WHERE 的查询追加条件（AND 组合）。"""
        ast = sqlglot.parse_one("SELECT * FROM orders WHERE status = 'active'")
        transformer = SQLTransformer()
        result = transformer.inject_where(ast, "region = '华东'")
        sql = result.sql()
        assert "AND" in sql.upper()
        assert "status" in sql
        assert "region" in sql

    def test_inject_multiple_conditions(self) -> None:
        """多次注入条件。"""
        ast = sqlglot.parse_one("SELECT * FROM orders")
        transformer = SQLTransformer()
        result = transformer.inject_where(ast, "region = '华东'")
        result = transformer.inject_where(result, "status = 'active'")
        sql = result.sql()
        assert "AND" in sql.upper()

    def test_inject_does_not_modify_original(self) -> None:
        """注入不修改原始 AST。"""
        ast = sqlglot.parse_one("SELECT * FROM orders")
        original_sql = ast.sql()
        transformer = SQLTransformer()
        transformer.inject_where(ast, "region = '华东'")
        assert ast.sql() == original_sql

    def test_inject_with_expression(self) -> None:
        """使用 sqlglot 表达式注入条件。"""
        ast = sqlglot.parse_one("SELECT * FROM orders")
        condition = sqlglot.parse_one("amount > 100")
        transformer = SQLTransformer()
        result = transformer.inject_where(ast, condition)
        sql = result.sql()
        assert "amount" in sql


class TestRemoveColumns:
    """列移除测试。"""

    def test_remove_single_column(self) -> None:
        """移除单个列。"""
        ast = sqlglot.parse_one("SELECT id, name, phone FROM users")
        transformer = SQLTransformer()
        result = transformer.remove_columns(ast, ["phone"])
        sql = result.sql()
        assert "phone" not in sql
        assert "id" in sql
        assert "name" in sql

    def test_remove_multiple_columns(self) -> None:
        """移除多个列。"""
        ast = sqlglot.parse_one("SELECT id, name, phone, email, id_card FROM users")
        transformer = SQLTransformer()
        result = transformer.remove_columns(ast, ["phone", "id_card"])
        sql = result.sql()
        assert "phone" not in sql
        assert "id_card" not in sql
        assert "id" in sql
        assert "email" in sql

    def test_remove_column_with_alias(self) -> None:
        """移除带别名的列。"""
        ast = sqlglot.parse_one("SELECT id, name AS user_name, phone FROM users")
        transformer = SQLTransformer()
        result = transformer.remove_columns(ast, ["name"])
        sql = result.sql()
        assert "user_name" not in sql
        assert "id" in sql

    def test_remove_nonexistent_column_no_effect(self) -> None:
        """移除不存在的列不影响其他列。"""
        ast = sqlglot.parse_one("SELECT id, name FROM users")
        transformer = SQLTransformer()
        result = transformer.remove_columns(ast, ["nonexistent"])
        sql = result.sql()
        assert "id" in sql
        assert "name" in sql

    def test_remove_does_not_modify_original(self) -> None:
        """移除不修改原始 AST。"""
        ast = sqlglot.parse_one("SELECT id, name, phone FROM users")
        original_sql = ast.sql()
        transformer = SQLTransformer()
        transformer.remove_columns(ast, ["phone"])
        assert ast.sql() == original_sql


class TestConvertDialect:
    """方言转换测试。"""

    def test_pg_to_mysql(self) -> None:
        """PostgreSQL → MySQL 方言转换。"""
        ast = sqlglot.parse_one(
            "SELECT id, name FROM users WHERE created_at >= '2026-01-01' LIMIT 10",
            read="postgres",
        )
        transformer = SQLTransformer()
        result = transformer.convert_dialect(ast, Dialect.POSTGRESQL, Dialect.MYSQL)
        sql = result.sql(dialect="mysql")
        assert "SELECT" in sql.upper()
        assert "id" in sql

    def test_pg_to_doris(self) -> None:
        """PostgreSQL → Doris 方言转换。"""
        ast = sqlglot.parse_one(
            "SELECT category, SUM(amount) AS total FROM orders GROUP BY category",
            read="postgres",
        )
        transformer = SQLTransformer()
        result = transformer.convert_dialect(ast, Dialect.POSTGRESQL, Dialect.DORIS)
        sql = result.sql(dialect="doris")
        assert "SELECT" in sql.upper()
        assert "SUM" in sql.upper()

    def test_mysql_to_postgresql(self) -> None:
        """MySQL → PostgreSQL 方言转换。"""
        ast = sqlglot.parse_one(
            "SELECT id, name FROM users LIMIT 10",
            read="mysql",
        )
        transformer = SQLTransformer()
        result = transformer.convert_dialect(ast, Dialect.MYSQL, Dialect.POSTGRESQL)
        sql = result.sql(dialect="postgres")
        assert "SELECT" in sql.upper()

    def test_pg_to_clickhouse(self) -> None:
        """PostgreSQL → ClickHouse 方言转换。"""
        ast = sqlglot.parse_one(
            "SELECT id, SUM(amount) AS total FROM orders GROUP BY id",
            read="postgres",
        )
        transformer = SQLTransformer()
        result = transformer.convert_dialect(ast, Dialect.POSTGRESQL, Dialect.CLICKHOUSE)
        sql = result.sql(dialect="clickhouse")
        assert "SELECT" in sql.upper()


class TestAddLimitIfMissing:
    """自动添加 LIMIT 测试。"""

    def test_add_limit_to_query_without(self) -> None:
        """对没有 LIMIT 的查询添加默认 LIMIT。"""
        ast = sqlglot.parse_one("SELECT * FROM users")
        transformer = SQLTransformer()
        result = transformer.add_limit_if_missing(ast, default=1000)
        sql = result.sql()
        assert "LIMIT" in sql.upper()
        assert "1000" in sql

    def test_no_add_limit_to_query_with(self) -> None:
        """已有 LIMIT 的查询不再添加。"""
        ast = sqlglot.parse_one("SELECT * FROM users LIMIT 100")
        transformer = SQLTransformer()
        result = transformer.add_limit_if_missing(ast, default=1000)
        sql = result.sql()
        assert "100" in sql
        assert "1000" not in sql

    def test_custom_default_limit(self) -> None:
        """自定义默认 LIMIT 值。"""
        ast = sqlglot.parse_one("SELECT * FROM users")
        transformer = SQLTransformer()
        result = transformer.add_limit_if_missing(ast, default=500)
        sql = result.sql()
        assert "500" in sql

    def test_add_limit_does_not_modify_original(self) -> None:
        """添加 LIMIT 不修改原始 AST。"""
        ast = sqlglot.parse_one("SELECT * FROM users")
        original_sql = ast.sql()
        transformer = SQLTransformer()
        transformer.add_limit_if_missing(ast, default=1000)
        assert ast.sql() == original_sql


class TestTransformerWithBuilder:
    """Transformer 配合 SQLBuilder 使用测试。"""

    def test_builder_and_inject_where(self) -> None:
        """SQLBuilder 构建的 AST + WHERE 注入。"""
        ast = (
            SQLBuilder()
            .select(["id", "amount"])
            .from_table("orders")
            .where("status = 'completed'")
            .build()
        )
        transformer = SQLTransformer()
        result = transformer.inject_where(ast, "tenant_id = 't001'")
        sql = result.sql()
        assert "tenant_id" in sql
        assert "status" in sql

    def test_builder_and_remove_columns(self) -> None:
        """SQLBuilder 构建的 AST + 列移除。"""
        ast = (
            SQLBuilder()
            .select(["id", "name", "phone", "email"])
            .from_table("users")
            .build()
        )
        transformer = SQLTransformer()
        result = transformer.remove_columns(ast, ["phone"])
        sql = result.sql()
        assert "phone" not in sql
        assert "id" in sql
