"""操作权限守卫单元测试。

覆盖 OperationGuard 的各种 SQL 操作类型检测：
- SELECT → READ
- INSERT/UPDATE/DELETE → WRITE
- CREATE/ALTER/DROP/TRUNCATE → DDL
"""

from __future__ import annotations

import pytest

from datapilot_queryexec.rbac.models import OperationType
from datapilot_queryexec.rbac.operation_guard import OperationGuard


class TestSelectOperations:
    """SELECT 操作 → READ 类型测试。"""

    @pytest.fixture()
    def guard(self) -> OperationGuard:
        """创建操作守卫实例。"""
        return OperationGuard()

    def test_simple_select_read_allowed(self, guard: OperationGuard) -> None:
        """简单 SELECT 被 READ 权限允许。"""
        allowed, reason = guard.check(
            "SELECT id, name FROM users", [OperationType.READ]
        )
        assert allowed is True
        assert reason == ""

    def test_select_with_where(self, guard: OperationGuard) -> None:
        """带 WHERE 的 SELECT。"""
        allowed, _ = guard.check(
            "SELECT id FROM users WHERE age > 18", [OperationType.READ]
        )
        assert allowed is True

    def test_select_with_join(self, guard: OperationGuard) -> None:
        """带 JOIN 的 SELECT。"""
        allowed, _ = guard.check(
            "SELECT u.id FROM users u JOIN orders o ON u.id = o.user_id",
            [OperationType.READ],
        )
        assert allowed is True

    def test_select_blocked_for_write_only(self, guard: OperationGuard) -> None:
        """SELECT 被 WRITE-only 权限拒绝。"""
        allowed, reason = guard.check(
            "SELECT id FROM users", [OperationType.WRITE]
        )
        assert allowed is False
        assert "read" in reason.lower()


class TestWriteOperations:
    """INSERT/UPDATE/DELETE → WRITE 类型测试。"""

    @pytest.fixture()
    def guard(self) -> OperationGuard:
        """创建操作守卫实例。"""
        return OperationGuard()

    def test_insert_write_allowed(self, guard: OperationGuard) -> None:
        """INSERT 被 WRITE 权限允许。"""
        allowed, _ = guard.check(
            "INSERT INTO users (name) VALUES ('test')", [OperationType.WRITE]
        )
        assert allowed is True

    def test_insert_blocked_for_read_only(self, guard: OperationGuard) -> None:
        """INSERT 被 READ-only 权限拒绝。"""
        allowed, reason = guard.check(
            "INSERT INTO users (name) VALUES ('test')", [OperationType.READ]
        )
        assert allowed is False
        assert "write" in reason.lower()

    def test_update_write_allowed(self, guard: OperationGuard) -> None:
        """UPDATE 被 WRITE 权限允许。"""
        allowed, _ = guard.check(
            "UPDATE users SET name = 'new' WHERE id = 1", [OperationType.WRITE]
        )
        assert allowed is True

    def test_update_blocked_for_read_only(self, guard: OperationGuard) -> None:
        """UPDATE 被 READ-only 权限拒绝。"""
        allowed, _ = guard.check(
            "UPDATE users SET name = 'new' WHERE id = 1", [OperationType.READ]
        )
        assert allowed is False

    def test_delete_write_allowed(self, guard: OperationGuard) -> None:
        """DELETE 被 WRITE 权限允许。"""
        allowed, _ = guard.check(
            "DELETE FROM users WHERE id = 1", [OperationType.WRITE]
        )
        assert allowed is True

    def test_delete_blocked_for_read_only(self, guard: OperationGuard) -> None:
        """DELETE 被 READ-only 权限拒绝。"""
        allowed, _ = guard.check(
            "DELETE FROM users WHERE id = 1", [OperationType.READ]
        )
        assert allowed is False


class TestDDLOperations:
    """DDL 操作类型测试。"""

    @pytest.fixture()
    def guard(self) -> OperationGuard:
        """创建操作守卫实例。"""
        return OperationGuard()

    def test_create_table_ddl(self, guard: OperationGuard) -> None:
        """CREATE TABLE → DDL。"""
        allowed, reason = guard.check(
            "CREATE TABLE test (id INT)", [OperationType.READ]
        )
        assert allowed is False
        assert "ddl" in reason.lower()

    def test_create_table_ddl_allowed(self, guard: OperationGuard) -> None:
        """CREATE TABLE 被 DDL 权限允许。"""
        allowed, _ = guard.check(
            "CREATE TABLE test (id INT)", [OperationType.DDL]
        )
        assert allowed is True

    def test_alter_table_ddl(self, guard: OperationGuard) -> None:
        """ALTER TABLE → DDL。"""
        allowed, _ = guard.check(
            "ALTER TABLE users ADD COLUMN phone VARCHAR(20)", [OperationType.READ]
        )
        assert allowed is False

    def test_drop_table_ddl(self, guard: OperationGuard) -> None:
        """DROP TABLE → DDL。"""
        allowed, _ = guard.check("DROP TABLE users", [OperationType.READ])
        assert allowed is False

    def test_truncate_table_ddl(self, guard: OperationGuard) -> None:
        """TRUNCATE TABLE → DDL。"""
        allowed, _ = guard.check("TRUNCATE TABLE users", [OperationType.READ])
        assert allowed is False


class TestMultipleOperations:
    """多操作权限组合测试。"""

    @pytest.fixture()
    def guard(self) -> OperationGuard:
        """创建操作守卫实例。"""
        return OperationGuard()

    def test_read_and_write(self, guard: OperationGuard) -> None:
        """同时允许 READ 和 WRITE。"""
        allowed, _ = guard.check(
            "SELECT id FROM users", [OperationType.READ, OperationType.WRITE]
        )
        assert allowed is True

        allowed, _ = guard.check(
            "INSERT INTO users (name) VALUES ('test')",
            [OperationType.READ, OperationType.WRITE],
        )
        assert allowed is True

    def test_all_operations(self, guard: OperationGuard) -> None:
        """允许所有操作类型。"""
        all_ops = [OperationType.READ, OperationType.WRITE, OperationType.DDL, OperationType.EXPORT]
        allowed, _ = guard.check("SELECT id FROM users", all_ops)
        assert allowed is True

        allowed, _ = guard.check("DROP TABLE users", all_ops)
        assert allowed is True

    def test_empty_allowed_operations(self, guard: OperationGuard) -> None:
        """空操作列表拒绝所有操作。"""
        allowed, reason = guard.check("SELECT id FROM users", [])
        assert allowed is False
        assert reason != ""


class TestEdgeCases:
    """边界情况测试。"""

    @pytest.fixture()
    def guard(self) -> OperationGuard:
        """创建操作守卫实例。"""
        return OperationGuard()

    def test_invalid_sql_default_allowed(self, guard: OperationGuard) -> None:
        """无法识别的 SQL 操作默认允许（sqlglot 可能解析为 Alias 等表达式）。"""
        allowed, reason = guard.check("THIS IS NOT SQL", [OperationType.READ])
        # sqlglot 将任意文本解析为某种表达式，无法识别操作类型时默认允许
        assert allowed is True

    def test_empty_sql_blocked(self, guard: OperationGuard) -> None:
        """空 SQL 被拒绝。"""
        allowed, reason = guard.check("", [OperationType.READ])
        assert allowed is False
