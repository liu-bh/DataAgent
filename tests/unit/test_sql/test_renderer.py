"""datapilot_sql.renderer 单元测试。

覆盖 SQL 渲染和解析的各种场景。
"""

from __future__ import annotations

import pytest

from datapilot_sql.builder import SQLBuilder, Aggregate
from datapilot_sql.dialect import Dialect
from datapilot_sql.renderer import SQLRenderer


class TestRenderBasic:
    """基础渲染测试。"""

    def test_render_default_dialect(self) -> None:
        """默认方言渲染。"""
        renderer = SQLRenderer()
        ast = (
            SQLBuilder()
            .select(["id", "name"])
            .from_table("users")
            .build()
        )
        sql = renderer.render(ast)
        assert "SELECT" in sql.upper()
        assert "users" in sql

    def test_render_postgresql(self) -> None:
        """PostgreSQL 方言渲染。"""
        renderer = SQLRenderer()
        ast = (
            SQLBuilder()
            .select(["id", "name"])
            .from_table("users")
            .limit(10)
            .build()
        )
        sql = renderer.render(ast, dialect=Dialect.POSTGRESQL)
        assert "SELECT" in sql.upper()

    def test_render_mysql(self) -> None:
        """MySQL 方言渲染。"""
        renderer = SQLRenderer()
        ast = (
            SQLBuilder()
            .select(["id", "name"])
            .from_table("users")
            .limit(10)
            .build()
        )
        sql = renderer.render(ast, dialect=Dialect.MYSQL)
        assert "SELECT" in sql.upper()

    def test_render_clickhouse(self) -> None:
        """ClickHouse 方言渲染。"""
        renderer = SQLRenderer()
        ast = (
            SQLBuilder()
            .select(["id", Aggregate.sum("amount").as_("total")])
            .from_table("orders")
            .group_by("id")
            .build()
        )
        sql = renderer.render(ast, dialect=Dialect.CLICKHOUSE)
        assert "SELECT" in sql.upper()
        assert "SUM" in sql.upper()

    def test_render_doris(self) -> None:
        """Doris 方言渲染。"""
        renderer = SQLRenderer()
        ast = (
            SQLBuilder()
            .select(["id", "name"])
            .from_table("users")
            .build()
        )
        sql = renderer.render(ast, dialect=Dialect.DORIS)
        assert "SELECT" in sql.upper()

    def test_render_starrocks(self) -> None:
        """StarRocks 方言渲染。"""
        renderer = SQLRenderer()
        ast = (
            SQLBuilder()
            .select(["id", "name"])
            .from_table("users")
            .build()
        )
        sql = renderer.render(ast, dialect=Dialect.STARROCKS)
        assert "SELECT" in sql.upper()


class TestRenderPretty:
    """格式化渲染测试。"""

    def test_pretty_render(self) -> None:
        """格式化渲染输出多行 SQL。"""
        renderer = SQLRenderer()
        ast = (
            SQLBuilder()
            .select(["id", "name", "email"])
            .from_table("users")
            .where("age > 18")
            .order_by("name")
            .limit(100)
            .build()
        )
        sql = renderer.render_pretty(ast)
        # 格式化输出应包含换行
        assert "\n" in sql or "  " in sql
        assert "SELECT" in sql.upper()

    def test_pretty_render_with_join(self) -> None:
        """JOIN 的格式化渲染。"""
        renderer = SQLRenderer()
        ast = (
            SQLBuilder()
            .select(["o.id", "u.name"])
            .from_table("orders", alias="o")
            .join("users", "o.user_id = u.id", join_type="left", alias="u")
            .build()
        )
        sql = renderer.render_pretty(ast)
        assert "JOIN" in sql.upper()


class TestAstToString:
    """ast_to_string 测试。"""

    def test_ast_to_string(self) -> None:
        """默认方言 AST 转字符串。"""
        renderer = SQLRenderer()
        ast = (
            SQLBuilder()
            .select(["id"])
            .from_table("users")
            .build()
        )
        sql = renderer.ast_to_string(ast)
        assert "SELECT" in sql.upper()
        assert "users" in sql


class TestStringToAst:
    """string_to_ast 测试。"""

    def test_parse_simple_select(self) -> None:
        """解析简单 SELECT。"""
        renderer = SQLRenderer()
        ast = renderer.string_to_ast("SELECT id, name FROM users")
        sql = ast.sql()
        assert "SELECT" in sql.upper()
        assert "users" in sql

    def test_parse_with_where(self) -> None:
        """解析带 WHERE 的 SELECT。"""
        renderer = SQLRenderer()
        ast = renderer.string_to_ast("SELECT * FROM orders WHERE status = 'active'")
        sql = ast.sql()
        assert "WHERE" in sql.upper()

    def test_parse_with_join(self) -> None:
        """解析带 JOIN 的 SELECT。"""
        renderer = SQLRenderer()
        ast = renderer.string_to_ast(
            "SELECT o.id, u.name FROM orders o JOIN users u ON o.user_id = u.id"
        )
        sql = ast.sql()
        assert "JOIN" in sql.upper()

    def test_parse_with_aggregation(self) -> None:
        """解析聚合查询。"""
        renderer = SQLRenderer()
        ast = renderer.string_to_ast(
            "SELECT category, SUM(amount) AS total FROM orders GROUP BY category"
        )
        sql = ast.sql()
        assert "SUM" in sql.upper()
        assert "GROUP BY" in sql.upper()

    def test_parse_subquery(self) -> None:
        """解析子查询。"""
        renderer = SQLRenderer()
        ast = renderer.string_to_ast(
            "SELECT * FROM (SELECT id, name FROM users WHERE age > 18) AS sub"
        )
        sql = ast.sql()
        assert "SELECT" in sql.upper()

    def test_parse_case_when(self) -> None:
        """解析 CASE WHEN。"""
        renderer = SQLRenderer()
        ast = renderer.string_to_ast(
            "SELECT id, CASE WHEN amount > 1000 THEN 'high' ELSE 'low' END AS level FROM orders"
        )
        sql = ast.sql()
        assert "CASE" in sql.upper()

    def test_parse_invalid_sql_raises(self) -> None:
        """解析无效 SQL 抛出 ValueError。"""
        renderer = SQLRenderer()
        with pytest.raises(ValueError, match="SQL 解析失败"):
            renderer.string_to_ast("SELECT FROM WHERE")

    def test_parse_with_mysql_dialect(self) -> None:
        """使用 MySQL 方言解析。"""
        renderer = SQLRenderer()
        ast = renderer.string_to_ast(
            "SELECT id FROM users LIMIT 10",
            dialect=Dialect.MYSQL,
        )
        sql = ast.sql(dialect="mysql")
        assert "SELECT" in sql.upper()

    def test_round_trip(self) -> None:
        """SQL → AST → SQL 往返测试。"""
        renderer = SQLRenderer()
        original = "SELECT id, name FROM users WHERE age > 18 ORDER BY name LIMIT 100"
        ast = renderer.string_to_ast(original)
        result = renderer.ast_to_string(ast)
        # 验证关键元素保留
        assert "users" in result
        assert "age" in result
        assert "name" in result


class TestRenderComplexSQL:
    """复杂 SQL 模式渲染测试。"""

    def test_render_full_query(self) -> None:
        """渲染完整的聚合 + JOIN + 过滤查询。"""
        renderer = SQLRenderer()
        ast = (
            SQLBuilder()
            .select([
                ("u.name", ""),
                Aggregate.sum("o.amount").as_("total"),
                Aggregate.count().as_("cnt"),
            ])
            .from_table("orders", alias="o")
            .join("users", "o.user_id = u.id", join_type="left", alias="u")
            .where("o.created_at >= '2026-01-01'")
            .group_by("u.name")
            .having(Aggregate.sum("o.amount") > 1000)
            .order_by("total", desc=True)
            .limit(50)
            .build()
        )
        sql = renderer.render(ast)
        assert "SELECT" in sql.upper()
        assert "JOIN" in sql.upper()
        assert "WHERE" in sql.upper()
        assert "GROUP BY" in sql.upper()
        assert "HAVING" in sql.upper()
        assert "ORDER BY" in sql.upper()
        assert "LIMIT" in sql.upper()

    def test_render_case_when_from_string(self) -> None:
        """渲染解析自字符串的 CASE WHEN。"""
        renderer = SQLRenderer()
        ast = renderer.string_to_ast(
            "SELECT id, CASE WHEN status = 'active' THEN 1 ELSE 0 END AS is_active FROM orders"
        )
        sql = renderer.render(ast)
        assert "CASE" in sql.upper()
        assert "is_active" in sql

    def test_render_subquery_from_string(self) -> None:
        """渲染解析自字符串的子查询。"""
        renderer = SQLRenderer()
        ast = renderer.string_to_ast(
            "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders WHERE amount > 100)"
        )
        sql = renderer.render(ast)
        assert "IN" in sql.upper()

    def test_render_time_range_filter(self) -> None:
        """渲染时间范围过滤。"""
        renderer = SQLRenderer()
        ast = (
            SQLBuilder()
            .select(["id", "amount"])
            .from_table("orders")
            .where("created_at >= '2026-01-01'")
            .where("created_at < '2026-02-01'")
            .build()
        )
        sql = renderer.render(ast)
        assert "created_at" in sql
