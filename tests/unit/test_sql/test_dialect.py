"""datapilot_sql.dialect 单元测试。

覆盖方言枚举、方言工厂和兼容性检查。
"""

from __future__ import annotations

import pytest
import sqlglot
from sqlglot import expressions as exp

from datapilot_sql.dialect import (
    CompatibilityIssue,
    Dialect,
    check_compatibility,
    get_dialect,
)


class TestDialectEnum:
    """Dialect 枚举测试。"""

    def test_all_dialects_exist(self) -> None:
        """验证所有需要的方言都已定义。"""
        expected = {"MYSQL", "POSTGRESQL", "DORIS", "STARROCKS", "CLICKHOUSE"}
        actual = {d.name for d in Dialect}
        assert actual == expected

    def test_dialect_values(self) -> None:
        """验证方言枚举值。"""
        assert Dialect.MYSQL.value == "mysql"
        assert Dialect.POSTGRESQL.value == "postgres"
        assert Dialect.DORIS.value == "doris"
        assert Dialect.STARROCKS.value == "starrocks"
        assert Dialect.CLICKHOUSE.value == "clickhouse"


class TestGetDialect:
    """get_dialect 工厂方法测试。"""

    def test_get_postgresql_dialect(self) -> None:
        """获取 PostgreSQL 方言实例。"""
        d = get_dialect(Dialect.POSTGRESQL)
        assert d is not None

    def test_get_mysql_dialect(self) -> None:
        """获取 MySQL 方言实例。"""
        d = get_dialect(Dialect.MYSQL)
        assert d is not None

    def test_get_doris_dialect(self) -> None:
        """获取 Doris 方言实例。"""
        d = get_dialect(Dialect.DORIS)
        assert d is not None

    def test_get_starrocks_dialect(self) -> None:
        """获取 StarRocks 方言实例。"""
        d = get_dialect(Dialect.STARROCKS)
        assert d is not None

    def test_get_clickhouse_dialect(self) -> None:
        """获取 ClickHouse 方言实例。"""
        d = get_dialect(Dialect.CLICKHOUSE)
        assert d is not None


class TestCompatibilityCheck:
    """方言兼容性检查测试。"""

    def test_clickhouse_multi_table_join(self) -> None:
        """ClickHouse 不支持多表 JOIN。"""
        # 构建 FROM a, b 的 AST（隐式多表 JOIN）
        ast = sqlglot.parse_one("SELECT * FROM a, b WHERE a.id = b.id")
        issues = check_compatibility(ast, Dialect.CLICKHOUSE)
        assert any("multi_table_join" in issue.feature for issue in issues)

    def test_clickhouse_with_recursive(self) -> None:
        """ClickHouse 不支持 WITH RECURSIVE。"""
        ast = sqlglot.parse_one(
            "WITH RECURSIVE cte AS (SELECT 1 AS n UNION ALL SELECT n+1 FROM cte WHERE n < 5) "
            "SELECT * FROM cte"
        )
        issues = check_compatibility(ast, Dialect.CLICKHOUSE)
        assert any("with_recursive" in issue.feature for issue in issues)

    def test_postgresql_no_issues(self) -> None:
        """PostgreSQL 对大多数标准 SQL 无兼容性问题。"""
        ast = sqlglot.parse_one(
            "SELECT o.id, u.name FROM orders o LEFT JOIN users u ON o.user_id = u.id"
        )
        issues = check_compatibility(ast, Dialect.POSTGRESQL)
        assert len(issues) == 0

    def test_mysql_no_known_issues(self) -> None:
        """MySQL 当前无已知限制。"""
        ast = sqlglot.parse_one("SELECT * FROM users WHERE id = 1")
        issues = check_compatibility(ast, Dialect.MYSQL)
        assert len(issues) == 0

    def test_doris_with_recursive(self) -> None:
        """Doris 不支持 WITH RECURSIVE。"""
        ast = sqlglot.parse_one(
            "WITH RECURSIVE cte AS (SELECT 1 AS n) SELECT * FROM cte"
        )
        issues = check_compatibility(ast, Dialect.DORIS)
        assert any("with_recursive" in issue.feature for issue in issues)

    def test_full_outer_join_warning(self) -> None:
        """FULL OUTER JOIN 在 Doris 中产生警告。"""
        ast = sqlglot.parse_one(
            "SELECT * FROM a FULL OUTER JOIN b ON a.id = b.id"
        )
        issues = check_compatibility(ast, Dialect.DORIS)
        assert any("full_outer_join" in issue.feature for issue in issues)
        assert any(issue.severity == "warning" for issue in issues)


class TestCompatibilityIssue:
    """CompatibilityIssue 数据类测试。"""

    def test_creation(self) -> None:
        """创建兼容性问题实例。"""
        issue = CompatibilityIssue(
            feature="with_recursive",
            description="不支持 WITH RECURSIVE",
            severity="error",
        )
        assert issue.feature == "with_recursive"
        assert issue.description == "不支持 WITH RECURSIVE"
        assert issue.severity == "error"

    def test_repr(self) -> None:
        """验证 repr 输出。"""
        issue = CompatibilityIssue("test_feature", "test_desc", "warning")
        r = repr(issue)
        assert "test_feature" in r
        assert "test_desc" in r
        assert "warning" in r
