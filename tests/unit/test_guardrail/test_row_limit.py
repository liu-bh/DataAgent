"""datapilot_guardrail.row_limit 单元测试。

覆盖 RowLimitEnforcer 的行数限制检查逻辑。
"""

from __future__ import annotations

import pytest

from datapilot_guardrail.row_limit import RowLimitEnforcer


class TestRowLimitEnforcerInit:
    """RowLimitEnforcer 初始化测试。"""

    def test_default_limit(self) -> None:
        """默认限制为 10000。"""
        enforcer = RowLimitEnforcer()
        assert enforcer.default_limit == 10000

    def test_custom_limit(self) -> None:
        """自定义限制值。"""
        enforcer = RowLimitEnforcer(default_limit=5000)
        assert enforcer.default_limit == 5000


class TestCheckWithLimit:
    """SQL 已包含 LIMIT 的场景。"""

    @pytest.fixture()
    def enforcer(self) -> RowLimitEnforcer:
        """创建限制器实例，默认 10000。"""
        return RowLimitEnforcer(default_limit=10000)

    def test_limit_within_range(self, enforcer: RowLimitEnforcer) -> None:
        """LIMIT 在允许范围内，不需要施加限制。"""
        needs_limit, actual = enforcer.check("SELECT id FROM users LIMIT 100")
        assert needs_limit is False
        assert actual == 100

    def test_limit_equals_max(self, enforcer: RowLimitEnforcer) -> None:
        """LIMIT 等于最大值，不需要施加限制。"""
        needs_limit, actual = enforcer.check("SELECT id FROM users LIMIT 10000")
        assert needs_limit is False
        assert actual == 10000

    def test_limit_exceeds_max(self, enforcer: RowLimitEnforcer) -> None:
        """LIMIT 超过最大值，需要截断。"""
        needs_limit, actual = enforcer.check("SELECT id FROM users LIMIT 50000")
        assert needs_limit is True
        assert actual == 10000

    def test_custom_max_rows(self, enforcer: RowLimitEnforcer) -> None:
        """自定义 max_rows 参数。"""
        needs_limit, actual = enforcer.check(
            "SELECT id FROM users LIMIT 5000", max_rows=1000
        )
        assert needs_limit is True
        assert actual == 1000


class TestCheckWithoutLimit:
    """SQL 未包含 LIMIT 的场景。"""

    @pytest.fixture()
    def enforcer(self) -> RowLimitEnforcer:
        """创建限制器实例。"""
        return RowLimitEnforcer(default_limit=10000)

    def test_no_limit(self, enforcer: RowLimitEnforcer) -> None:
        """SQL 没有 LIMIT，需要施加默认限制。"""
        needs_limit, actual = enforcer.check("SELECT id FROM users")
        assert needs_limit is True
        assert actual == 10000

    def test_no_limit_custom_max(self, enforcer: RowLimitEnforcer) -> None:
        """没有 LIMIT + 自定义 max_rows。"""
        needs_limit, actual = enforcer.check(
            "SELECT id FROM users", max_rows=500
        )
        assert needs_limit is True
        assert actual == 500


class TestCheckWithComplexSQL:
    """复杂 SQL 的行数限制检查。"""

    @pytest.fixture()
    def enforcer(self) -> RowLimitEnforcer:
        """创建限制器实例。"""
        return RowLimitEnforcer(default_limit=1000)

    def test_join_with_limit(self, enforcer: RowLimitEnforcer) -> None:
        """JOIN 查询带有合理的 LIMIT。"""
        sql = (
            "SELECT u.id, u.name FROM users u "
            "JOIN orders o ON u.id = o.user_id LIMIT 50"
        )
        needs_limit, actual = enforcer.check(sql)
        assert needs_limit is False
        assert actual == 50

    def test_subquery_with_limit(self, enforcer: RowLimitEnforcer) -> None:
        """子查询的 LIMIT 提取。"""
        sql = (
            "SELECT * FROM (SELECT id FROM users LIMIT 200) t"
        )
        needs_limit, actual = enforcer.check(sql)
        # 内层子查询有 LIMIT 200，外层无 LIMIT
        # 限制器提取第一个找到的 LIMIT
        assert actual == 200

    def test_group_by_no_limit(self, enforcer: RowLimitEnforcer) -> None:
        """GROUP BY 查询没有 LIMIT。"""
        sql = (
            "SELECT status, COUNT(*) FROM users GROUP BY status"
        )
        needs_limit, actual = enforcer.check(sql)
        assert needs_limit is True
        assert actual == 1000


class TestInvalidSQL:
    """无效 SQL 测试。"""

    @pytest.fixture()
    def enforcer(self) -> RowLimitEnforcer:
        """创建限制器实例。"""
        return RowLimitEnforcer(default_limit=10000)

    def test_gibberish_sql(self, enforcer: RowLimitEnforcer) -> None:
        """无法解析的 SQL 使用默认限制。"""
        needs_limit, actual = enforcer.check("NOT SQL")
        assert needs_limit is True
        assert actual == 10000

    def test_empty_sql(self, enforcer: RowLimitEnforcer) -> None:
        """空 SQL 使用默认限制。"""
        needs_limit, actual = enforcer.check("")
        assert needs_limit is True
        assert actual == 10000
