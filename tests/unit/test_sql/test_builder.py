"""datapilot_sql.builder 单元测试。

覆盖 SQLBuilder 链式构建的各种 SQL 模式。
"""

from __future__ import annotations

import pytest

from datapilot_sql.builder import Aggregate, SQLBuilder, cond


# ---------- 基础 SELECT 测试 ----------


class TestSQLBuilderBasicSelect:
    """基础 SELECT 构建测试。"""

    def test_simple_select(self) -> None:
        """简单 SELECT * 构建。"""
        ast = (
            SQLBuilder()
            .select(["*"])
            .from_table("users")
            .build()
        )
        sql = ast.sql()
        assert "SELECT" in sql.upper()
        assert "FROM users" in sql

    def test_select_with_columns(self) -> None:
        """指定列名 SELECT。"""
        ast = (
            SQLBuilder()
            .select(["id", "name", "email"])
            .from_table("users")
            .build()
        )
        sql = ast.sql()
        assert "id" in sql
        assert "name" in sql
        assert "email" in sql

    def test_select_with_alias(self) -> None:
        """列别名构建。"""
        ast = (
            SQLBuilder()
            .select([("name", "user_name"), ("email", "user_email")])
            .from_table("users")
            .build()
        )
        sql = ast.sql()
        assert "user_name" in sql
        assert "user_email" in sql

    def test_select_distinct(self) -> None:
        """DISTINCT 构建。"""
        ast = (
            SQLBuilder()
            .select(["name"], distinct=True)
            .from_table("users")
            .build()
        )
        sql = ast.sql()
        assert "DISTINCT" in sql.upper()

    def test_from_with_alias(self) -> None:
        """表别名构建。"""
        ast = (
            SQLBuilder()
            .select(["o.id", "o.amount"])
            .from_table("orders", alias="o")
            .build()
        )
        sql = ast.sql()
        assert "orders" in sql


# ---------- JOIN 测试 ----------


class TestSQLBuilderJoin:
    """JOIN 构建测试。"""

    def test_inner_join(self) -> None:
        """INNER JOIN 构建。"""
        ast = (
            SQLBuilder()
            .select(["o.id", "u.name"])
            .from_table("orders", alias="o")
            .join("users", "o.user_id = u.id", join_type="inner", alias="u")
            .build()
        )
        sql = ast.sql()
        assert "JOIN" in sql.upper()
        assert "users" in sql

    def test_left_join(self) -> None:
        """LEFT JOIN 构建。"""
        ast = (
            SQLBuilder()
            .select(["o.id", "u.name"])
            .from_table("orders", alias="o")
            .join("users", "o.user_id = u.id", join_type="left", alias="u")
            .build()
        )
        sql = ast.sql()
        assert "LEFT" in sql.upper()

    def test_multiple_joins(self) -> None:
        """多表 JOIN 构建。"""
        ast = (
            SQLBuilder()
            .select(["o.id", "u.name", "p.product_name"])
            .from_table("orders", alias="o")
            .join("users", "o.user_id = u.id", join_type="left", alias="u")
            .join("products", "o.product_id = p.id", join_type="left", alias="p")
            .build()
        )
        sql = ast.sql()
        assert "users" in sql
        assert "products" in sql


# ---------- WHERE 测试 ----------


class TestSQLBuilderWhere:
    """WHERE 条件构建测试。"""

    def test_single_where(self) -> None:
        """单一 WHERE 条件。"""
        ast = (
            SQLBuilder()
            .select(["*"])
            .from_table("users")
            .where("age > 18")
            .build()
        )
        sql = ast.sql()
        assert "WHERE" in sql.upper()
        assert "age" in sql

    def test_multiple_where_and(self) -> None:
        """多个 WHERE 条件自动 AND 组合。"""
        ast = (
            SQLBuilder()
            .select(["*"])
            .from_table("users")
            .where("age > 18")
            .where("status = 'active'")
            .build()
        )
        sql = ast.sql()
        assert "WHERE" in sql.upper()
        assert "AND" in sql.upper()

    def test_where_with_condition_builder(self) -> None:
        """使用 _ConditionBuilder 构建复杂条件。"""
        condition = cond("age > 18").and_(cond("status = 'active'")).or_(cond("is_vip = true"))
        ast = (
            SQLBuilder()
            .select(["*"])
            .from_table("users")
            .where(condition)
            .build()
        )
        sql = ast.sql()
        assert "WHERE" in sql.upper()


# ---------- GROUP BY + HAVING 测试 ----------


class TestSQLBuilderGroupBy:
    """GROUP BY 和 HAVING 构建测试。"""

    def test_group_by(self) -> None:
        """GROUP BY 构建。"""
        ast = (
            SQLBuilder()
            .select([("user_id", ""), Aggregate.sum("amount").as_("total")])
            .from_table("orders")
            .group_by("user_id")
            .build()
        )
        sql = ast.sql()
        assert "GROUP BY" in sql.upper()

    def test_group_by_having(self) -> None:
        """GROUP BY + HAVING 构建。"""
        having_cond = Aggregate.sum("amount") > 1000
        ast = (
            SQLBuilder()
            .select([("user_id", ""), Aggregate.sum("amount").as_("total")])
            .from_table("orders")
            .group_by("user_id")
            .having(having_cond)
            .build()
        )
        sql = ast.sql()
        assert "GROUP BY" in sql.upper()
        assert "HAVING" in sql.upper()

    def test_multiple_group_by(self) -> None:
        """多列 GROUP BY。"""
        ast = (
            SQLBuilder()
            .select(["category", "region", Aggregate.count()])
            .from_table("sales")
            .group_by("category", "region")
            .build()
        )
        sql = ast.sql()
        assert "GROUP BY" in sql.upper()


# ---------- ORDER BY + LIMIT 测试 ----------


class TestSQLBuilderOrderByLimit:
    """ORDER BY 和 LIMIT 构建测试。"""

    def test_order_by_asc(self) -> None:
        """升序 ORDER BY。"""
        ast = (
            SQLBuilder()
            .select(["*"])
            .from_table("users")
            .order_by("name")
            .build()
        )
        sql = ast.sql()
        assert "ORDER BY" in sql.upper()

    def test_order_by_desc(self) -> None:
        """降序 ORDER BY。"""
        ast = (
            SQLBuilder()
            .select(["*"])
            .from_table("users")
            .order_by("created_at", desc=True)
            .build()
        )
        sql = ast.sql()
        assert "ORDER BY" in sql.upper()
        assert "DESC" in sql.upper()

    def test_limit(self) -> None:
        """LIMIT 构建。"""
        ast = (
            SQLBuilder()
            .select(["*"])
            .from_table("users")
            .limit(100)
            .build()
        )
        sql = ast.sql()
        assert "LIMIT" in sql.upper()

    def test_limit_with_offset(self) -> None:
        """LIMIT + OFFSET 构建。"""
        ast = (
            SQLBuilder()
            .select(["*"])
            .from_table("users")
            .limit(100, offset=50)
            .build()
        )
        sql = ast.sql()
        assert "LIMIT" in sql.upper()
        assert "OFFSET" in sql.upper() or "50" in sql


# ---------- 聚合函数测试 ----------


class TestAggregate:
    """聚合表达式工厂测试。"""

    def test_count_star(self) -> None:
        """COUNT(*) 聚合。"""
        agg = Aggregate.count()
        sql = agg.expression.sql()
        assert "COUNT" in sql.upper()

    def test_count_column(self) -> None:
        """COUNT(column) 聚合。"""
        agg = Aggregate.count("id")
        sql = agg.expression.sql()
        assert "COUNT" in sql.upper()
        assert "id" in sql

    def test_sum(self) -> None:
        """SUM 聚合。"""
        agg = Aggregate.sum("amount")
        sql = agg.expression.sql()
        assert "SUM" in sql.upper()
        assert "amount" in sql

    def test_avg(self) -> None:
        """AVG 聚合。"""
        agg = Aggregate.avg("price")
        sql = agg.expression.sql()
        assert "AVG" in sql.upper()

    def test_min(self) -> None:
        """MIN 聚合。"""
        agg = Aggregate.min("price")
        sql = agg.expression.sql()
        assert "MIN" in sql.upper()

    def test_max(self) -> None:
        """MAX 聚合。"""
        agg = Aggregate.max("price")
        sql = agg.expression.sql()
        assert "MAX" in sql.upper()

    def test_aggregate_with_alias(self) -> None:
        """聚合带别名。"""
        agg = Aggregate.sum("amount").as_("total_amount")
        sql = agg.sql()
        assert "total_amount" in sql
        assert "SUM" in sql.upper()

    def test_aggregate_comparison(self) -> None:
        """聚合比较运算。"""
        gt = Aggregate.sum("amount") > 1000
        sql = gt.sql()
        assert "SUM" in sql.upper()
        assert ">" in sql

    def test_aggregate_eq(self) -> None:
        """聚合等于比较。"""
        eq = Aggregate.avg("price").eq(100)
        sql = eq.sql()
        assert "AVG" in sql.upper()
        assert "=" in sql


# ---------- 完整 SQL 模式测试 ----------


class TestSQLBuilderComplexPatterns:
    """完整 SQL 模式测试。"""

    def test_aggregation_with_group_having(self) -> None:
        """聚合 + GROUP BY + HAVING 完整模式。"""
        ast = (
            SQLBuilder()
            .select([
                ("category", ""),
                Aggregate.sum("amount").as_("total"),
                Aggregate.count().as_("order_count"),
            ])
            .from_table("orders")
            .where("created_at >= '2026-01-01'")
            .group_by("category")
            .having(Aggregate.sum("amount") > 10000)
            .order_by("total", desc=True)
            .limit(100)
            .build()
        )
        sql = ast.sql()
        assert "SELECT" in sql.upper()
        assert "FROM orders" in sql
        assert "WHERE" in sql.upper()
        assert "GROUP BY" in sql.upper()
        assert "HAVING" in sql.upper()
        assert "ORDER BY" in sql.upper()
        assert "LIMIT" in sql.upper()

    def test_join_with_filter(self) -> None:
        """JOIN + 过滤条件。"""
        ast = (
            SQLBuilder()
            .select(["o.id", "u.name", Aggregate.sum("o.amount").as_("total")])
            .from_table("orders", alias="o")
            .join("users", "o.user_id = u.id", join_type="left", alias="u")
            .where("o.status = 'completed'")
            .where("o.created_at >= '2026-01-01'")
            .group_by("o.id", "u.name")
            .order_by("total", desc=True)
            .limit(50)
            .build()
        )
        sql = ast.sql()
        assert "JOIN" in sql.upper()
        assert "WHERE" in sql.upper()

    def test_time_range_filter(self) -> None:
        """时间范围过滤。"""
        ast = (
            SQLBuilder()
            .select(["*"])
            .from_table("orders")
            .where("created_at >= '2026-01-01'")
            .where("created_at < '2026-02-01'")
            .build()
        )
        sql = ast.sql()
        assert "WHERE" in sql.upper()

    def test_multiple_order_columns(self) -> None:
        """多列排序。"""
        ast = (
            SQLBuilder()
            .select(["*"])
            .from_table("users")
            .order_by("status", desc=True)
            .order_by("name")
            .build()
        )
        sql = ast.sql()
        assert "ORDER BY" in sql.upper()


# ---------- 错误处理测试 ----------


class TestSQLBuilderErrors:
    """构建器错误处理测试。"""

    def test_missing_select_raises(self) -> None:
        """未调用 select() 时 build() 抛出 ValueError。"""
        with pytest.raises(ValueError, match="必须指定至少一个查询列"):
            (
                SQLBuilder()
                .from_table("users")
                .build()
            )

    def test_missing_from_raises(self) -> None:
        """未调用 from_table() 时 build() 抛出 ValueError。"""
        with pytest.raises(ValueError, match="必须指定来源表"):
            (
                SQLBuilder()
                .select(["id"])
                .build()
            )

    def test_unsupported_column_type_raises(self) -> None:
        """不支持的列定义类型抛出 TypeError。"""
        with pytest.raises(TypeError, match="不支持的列定义类型"):
            (
                SQLBuilder()
                .select([123])  # type: ignore[list-item]
                .from_table("users")
                .build()
            )
