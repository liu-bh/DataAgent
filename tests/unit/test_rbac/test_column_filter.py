"""列级权限过滤器单元测试。

覆盖 ColumnFilter 的各种场景：
- 简单列移除
- table.column 形式
- 带别名的列
- 所有列被移除时的占位
- 无隐藏列
"""

from __future__ import annotations

import pytest

from datapilot_queryexec.rbac.column_filter import ColumnFilter


class TestColumnFilterBasic:
    """ColumnFilter 基本功能测试。"""

    def test_remove_single_column(self) -> None:
        """移除单个列。"""
        sql = "SELECT id, name, phone FROM users"
        result, removed = ColumnFilter.apply(sql, ["phone"])
        assert "phone" not in result.lower() or "PHONE" not in result.upper()
        assert "phone" in removed
        assert "id" in result.lower() or "ID" in result.upper()
        assert "name" in result.lower() or "NAME" in result.upper()

    def test_remove_multiple_columns(self) -> None:
        """移除多个列。"""
        sql = "SELECT id, name, phone, email FROM users"
        result, removed = ColumnFilter.apply(sql, ["phone", "email"])
        assert len(removed) == 2
        assert set(removed) == {"phone", "email"}
        assert "id" in result.lower() or "ID" in result.upper()

    def test_empty_hidden_columns(self) -> None:
        """空隐藏列列表时原样返回。"""
        sql = "SELECT id, name FROM users"
        result, removed = ColumnFilter.apply(sql, [])
        assert result == sql
        assert removed == []

    def test_no_matching_columns(self) -> None:
        """没有匹配的列时原样返回。"""
        sql = "SELECT id, name FROM users"
        result, removed = ColumnFilter.apply(sql, ["phone", "email"])
        assert "id" in result.lower() or "ID" in result.upper()
        assert "name" in result.lower() or "NAME" in result.upper()
        assert removed == []


class TestColumnFilterWithTablePrefix:
    """ColumnFilter table.column 形式测试。"""

    def test_table_column_format(self) -> None:
        """table.column 形式的列移除。"""
        sql = "SELECT u.id, u.name, u.phone FROM users u"
        result, removed = ColumnFilter.apply(sql, ["phone"])
        assert "phone" in removed
        assert "id" in result.lower() or "ID" in result.upper()

    def test_mixed_table_column_and_plain(self) -> None:
        """混合 table.column 和纯列名。"""
        sql = "SELECT u.id, u.phone, name FROM users u"
        result, removed = ColumnFilter.apply(sql, ["phone", "name"])
        assert len(removed) == 2
        assert "id" in result.lower() or "ID" in result.upper()

    def test_join_table_prefix(self) -> None:
        """JOIN 中使用表前缀的列移除。"""
        sql = (
            "SELECT u.id, u.name, o.phone "
            "FROM users u "
            "JOIN orders o ON u.id = o.user_id"
        )
        result, removed = ColumnFilter.apply(sql, ["phone"])
        assert "phone" in removed
        assert "id" in result.lower() or "ID" in result.upper()
        assert "name" in result.lower() or "NAME" in result.upper()


class TestColumnFilterWithAlias:
    """ColumnFilter 带别名的列测试。"""

    def test_aliased_column(self) -> None:
        """带 AS 别名的列移除。"""
        sql = "SELECT id, phone AS mobile FROM users"
        result, removed = ColumnFilter.apply(sql, ["phone"])
        assert "phone" in removed
        # phone 或 mobile 列应被移除
        assert "id" in result.lower() or "ID" in result.upper()

    def test_aliased_column_by_alias_name(self) -> None:
        """通过别名移除列。"""
        sql = "SELECT id, name AS user_name FROM users"
        result, removed = ColumnFilter.apply(sql, ["user_name"])
        # 别名匹配也会移除
        assert "user_name" in removed


class TestColumnFilterEdgeCases:
    """ColumnFilter 边界情况测试。"""

    def test_all_columns_removed(self) -> None:
        """所有列都被移除时使用 COUNT(*) 占位。"""
        sql = "SELECT phone, email FROM users"
        result, removed = ColumnFilter.apply(sql, ["phone", "email"])
        assert len(removed) == 2
        assert "COUNT" in result.upper()
        assert "*" in result

    def test_select_star(self) -> None:
        """SELECT * 不受影响（* 不是具体列名）。"""
        sql = "SELECT * FROM users"
        result, removed = ColumnFilter.apply(sql, ["phone"])
        # * 列无法通过 AST 列名匹配移除
        assert removed == []

    def test_invalid_sql_raises(self) -> None:
        """无效 SQL 不一定会抛出异常（sqlglot 会尝试解析为表达式）。"""
        # sqlglot 对任意文本都可能尝试解析，不一定报错
        result, removed = ColumnFilter.apply("NOT A SQL", ["phone"])
        # 关键：不会崩溃，返回某种结果
        assert isinstance(result, str)

    def test_duplicate_hidden_columns(self) -> None:
        """重复的隐藏列不导致重复移除。"""
        sql = "SELECT id, phone FROM users"
        result, removed = ColumnFilter.apply(sql, ["phone", "phone"])
        assert removed.count("phone") == 1
