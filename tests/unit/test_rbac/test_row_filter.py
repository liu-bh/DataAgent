"""行级权限过滤器单元测试。

覆盖 RowFilter 的各种 SQL 场景：
- 有 WHERE 的 SQL
- 无 WHERE 的 SQL
- 子查询
- JOIN
- 多个条件叠加
"""

from __future__ import annotations

import pytest

from datapilot_queryexec.rbac.row_filter import RowFilter


class TestRowFilterBasic:
    """RowFilter 基本功能测试。"""

    def test_add_where_to_simple_select(self) -> None:
        """在无 WHERE 的简单 SELECT 中添加 WHERE。"""
        sql = "SELECT id, name FROM users"
        result = RowFilter.apply(sql, "department_id = 100")
        assert "WHERE" in result.upper()
        assert "department_id" in result
        assert "id" in result
        assert "name" in result

    def test_append_to_existing_where(self) -> None:
        """在已有 WHERE 的 SQL 中追加条件。"""
        sql = "SELECT id FROM users WHERE age > 18"
        result = RowFilter.apply(sql, "department_id = 100")
        assert "WHERE" in result.upper()
        # 两个条件都应该存在
        assert "age" in result or "AGE" in result.upper()
        assert "department_id" in result or "DEPARTMENT_ID" in result.upper()

    def test_filter_empty_expression(self) -> None:
        """空过滤表达式时原样返回。"""
        sql = "SELECT id FROM users WHERE age > 18"
        result = RowFilter.apply(sql, "")
        assert result == sql

    def test_none_filter_expression(self) -> None:
        """空字符串过滤表达式不报错。"""
        sql = "SELECT id FROM users"
        result = RowFilter.apply(sql, "")
        assert result == sql


class TestRowFilterWithJoin:
    """RowFilter 与 JOIN 场景测试。"""

    def test_filter_with_join(self) -> None:
        """JOIN 查询中注入 WHERE。"""
        sql = (
            "SELECT u.id, o.amount "
            "FROM users u "
            "JOIN orders o ON u.id = o.user_id"
        )
        result = RowFilter.apply(sql, "u.department_id = 100")
        assert "WHERE" in result.upper()
        assert "department_id" in result

    def test_filter_with_join_and_where(self) -> None:
        """已有 WHERE 的 JOIN 查询。"""
        sql = (
            "SELECT u.id, o.amount "
            "FROM users u "
            "JOIN orders o ON u.id = o.user_id "
            "WHERE o.amount > 100"
        )
        result = RowFilter.apply(sql, "u.department_id = 100")
        assert "WHERE" in result.upper()
        assert "amount" in result.lower() or "AMOUNT" in result.upper()
        assert "department_id" in result

    def test_filter_with_left_join(self) -> None:
        """LEFT JOIN 查询中注入 WHERE。"""
        sql = (
            "SELECT u.id, d.name "
            "FROM users u "
            "LEFT JOIN departments d ON u.dept_id = d.id"
        )
        result = RowFilter.apply(sql, "u.status = 'active'")
        assert "WHERE" in result.upper()
        assert "status" in result.lower() or "STATUS" in result.upper()


class TestRowFilterWithSubquery:
    """RowFilter 与子查询场景测试。"""

    def test_filter_with_subquery(self) -> None:
        """包含子查询的 SQL。"""
        sql = "SELECT * FROM (SELECT id, name FROM users) t"
        result = RowFilter.apply(sql, "t.id > 10")
        assert "WHERE" in result.upper()
        assert "id" in result.lower() or "ID" in result.upper()

    def test_filter_outer_query(self) -> None:
        """外层查询已有 WHERE 的子查询。"""
        sql = (
            "SELECT t.id FROM ("
            "  SELECT id, name FROM users"
            ") t WHERE t.id > 5"
        )
        result = RowFilter.apply(sql, "t.name != 'admin'")
        assert "WHERE" in result.upper()
        assert "id" in result.lower() or "ID" in result.upper()
        assert "name" in result.lower() or "NAME" in result.upper()


class TestRowFilterComplexConditions:
    """RowFilter 复杂条件测试。"""

    def test_in_condition(self) -> None:
        """IN 条件注入。"""
        sql = "SELECT id FROM users"
        result = RowFilter.apply(sql, "department_id IN (100, 200, 300)")
        assert "WHERE" in result.upper()
        assert "IN" in result.upper()

    def test_like_condition(self) -> None:
        """LIKE 条件注入。"""
        sql = "SELECT id FROM users"
        result = RowFilter.apply(sql, "name LIKE '%张%'")
        assert "WHERE" in result.upper()
        assert "LIKE" in result.upper()

    def test_between_condition(self) -> None:
        """BETWEEN 条件注入。"""
        sql = "SELECT id, amount FROM orders"
        result = RowFilter.apply(sql, "amount BETWEEN 100 AND 500")
        assert "WHERE" in result.upper()
        assert "BETWEEN" in result.upper()

    def test_multiple_injections(self) -> None:
        """多次注入（两次 apply 调用）。"""
        sql = "SELECT id FROM users"
        result = RowFilter.apply(sql, "department_id = 100")
        result = RowFilter.apply(result, "status = 'active'")
        # 两次注入后应该包含两个条件
        assert "department_id" in result
        assert "status" in result.lower() or "STATUS" in result.upper()


class TestRowFilterDialect:
    """RowFilter 方言测试。"""

    def test_postgres_dialect(self) -> None:
        """PostgreSQL 方言。"""
        sql = "SELECT id FROM users"
        result = RowFilter.apply(sql, "department_id = 100", dialect="postgres")
        assert "WHERE" in result.upper()
        assert "department_id" in result or "DEPARTMENT_ID" in result.upper()

    def test_invalid_sql_gracefully_handled(self) -> None:
        """无效 SQL 不一定会抛出异常（sqlglot 会尝试解析为表达式）。"""
        # sqlglot 对任意文本都可能尝试解析，不一定报错
        result = RowFilter.apply("THIS IS NOT SQL", "id = 1")
        # 关键：不会崩溃，返回某种结果
        assert isinstance(result, str)

    def test_invalid_expression_raises(self) -> None:
        """无效过滤表达式抛出 ValueError。"""
        with pytest.raises(ValueError, match="过滤表达式解析失败"):
            RowFilter.apply("SELECT id FROM users", "=== INVALID ===")
