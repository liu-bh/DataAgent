"""datapilot_sql.validator 单元测试。

覆盖 SQLValidator 的表/列校验、方言兼容性检查。
"""

from __future__ import annotations

import sqlglot

from datapilot_sql.builder import SQLBuilder
from datapilot_sql.dialect import Dialect
from datapilot_sql.validator import SQLValidator, ValidationResult


# 测试用 schema
TEST_SCHEMA = {
    "orders": {
        "id": "int",
        "amount": "decimal",
        "user_id": "int",
        "status": "varchar",
        "created_at": "timestamp",
    },
    "users": {
        "id": "int",
        "name": "varchar",
        "email": "varchar",
        "age": "int",
    },
    "products": {
        "id": "int",
        "product_name": "varchar",
        "price": "decimal",
    },
}


class TestValidationResult:
    """ValidationResult 数据类测试。"""

    def test_default_valid(self) -> None:
        """默认结果为 valid=True。"""
        result = ValidationResult()
        assert result.valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_add_error(self) -> None:
        """添加错误后 valid 变为 False。"""
        result = ValidationResult()
        result.add_error("表不存在")
        assert result.valid is False
        assert len(result.errors) == 1
        assert "表不存在" in result.errors[0]

    def test_add_warning(self) -> None:
        """添加警告不影响 valid。"""
        result = ValidationResult()
        result.add_warning("可能性能不佳")
        assert result.valid is True
        assert len(result.warnings) == 1

    def test_multiple_errors(self) -> None:
        """多个错误累积。"""
        result = ValidationResult()
        result.add_error("错误1")
        result.add_error("错误2")
        assert len(result.errors) == 2
        assert result.valid is False


class TestSQLValidatorTableCheck:
    """表存在性校验测试。"""

    def test_existing_table_passes(self) -> None:
        """引用已存在的表，验证通过。"""
        validator = SQLValidator(TEST_SCHEMA)
        ast = sqlglot.parse_one("SELECT id FROM orders")
        result = validator.validate(ast)
        assert result.valid is True

    def test_missing_table_fails(self) -> None:
        """引用不存在的表，验证失败。"""
        validator = SQLValidator(TEST_SCHEMA)
        ast = sqlglot.parse_one("SELECT id FROM nonexistent_table")
        result = validator.validate(ast)
        assert result.valid is False
        assert any("nonexistent_table" in e for e in result.errors)

    def test_empty_schema_all_fail(self) -> None:
        """空 schema 下所有表都不存在。"""
        validator = SQLValidator({})
        ast = sqlglot.parse_one("SELECT id FROM orders")
        result = validator.validate(ast)
        assert result.valid is False


class TestSQLValidatorColumnCheck:
    """列存在性校验测试。"""

    def test_existing_column_passes(self) -> None:
        """引用已存在的列，验证通过。"""
        validator = SQLValidator(TEST_SCHEMA)
        ast = sqlglot.parse_one("SELECT id, amount FROM orders")
        result = validator.validate(ast)
        assert result.valid is True

    def test_missing_column_with_table_qualifier(self) -> None:
        """引用不存在的列（带表限定），验证失败。"""
        validator = SQLValidator(TEST_SCHEMA)
        ast = sqlglot.parse_one("SELECT orders.nonexistent_col FROM orders")
        result = validator.validate(ast)
        assert result.valid is False
        assert any("nonexistent_col" in e for e in result.errors)

    def test_missing_column_without_qualifier_warning(self) -> None:
        """引用不存在的列（无表限定），产生警告。"""
        validator = SQLValidator(TEST_SCHEMA)
        ast = sqlglot.parse_one("SELECT nonexistent_col FROM orders")
        result = validator.validate(ast)
        assert any("nonexistent_col" in w for w in result.warnings)

    def test_star_column_passes(self) -> None:
        """SELECT * 不需要列校验。"""
        validator = SQLValidator(TEST_SCHEMA)
        ast = sqlglot.parse_one("SELECT * FROM orders")
        result = validator.validate(ast)
        assert result.valid is True

    def test_where_column_check(self) -> None:
        """WHERE 子句中的列也被检查。"""
        validator = SQLValidator(TEST_SCHEMA)
        ast = sqlglot.parse_one("SELECT * FROM orders WHERE nonexistent_col = 1")
        result = validator.validate(ast)
        # 无表限定的列在 WHERE 中会产生警告
        assert any("nonexistent_col" in w for w in result.warnings)


class TestSQLValidatorDialectCompatibility:
    """方言兼容性校验测试。"""

    def test_clickhouse_incompatibility(self) -> None:
        """ClickHouse 方言兼容性检查。"""
        validator = SQLValidator(TEST_SCHEMA)
        # 使用 WITH RECURSIVE 的 SQL
        ast = sqlglot.parse_one(
            "WITH RECURSIVE cte AS (SELECT 1 AS n UNION ALL SELECT n+1 FROM cte WHERE n < 5) "
            "SELECT * FROM cte"
        )
        result = validator.validate(ast, target_dialect=Dialect.CLICKHOUSE)
        assert result.valid is False
        assert any("WITH RECURSIVE" in e for e in result.errors)

    def test_postgresql_compatibility(self) -> None:
        """PostgreSQL 对标准 SQL 兼容性好。"""
        validator = SQLValidator(TEST_SCHEMA)
        ast = (
            SQLBuilder()
            .select(["id", "name"])
            .from_table("users")
            .where("age > 18")
            .build()
        )
        result = validator.validate(ast, target_dialect=Dialect.POSTGRESQL)
        assert result.valid is True


class TestSQLValidatorSchema:
    """Schema 更新测试。"""

    def test_update_schema(self) -> None:
        """动态更新 schema 后验证通过。"""
        validator = SQLValidator({"orders": {"id": "int"}})
        ast = sqlglot.parse_one("SELECT id, name FROM orders")
        result = validator.validate(ast)
        # name 列在初始 schema 中不存在 → 警告
        assert any("name" in w for w in result.warnings)

        # 更新 schema
        validator.update_schema({"orders": {"id": "int", "name": "varchar"}})
        result = validator.validate(ast)
        assert result.valid is True


class TestSQLValidatorWithBuilder:
    """使用 SQLBuilder 构建的 AST 进行验证。"""

    def test_builder_ast_validation(self) -> None:
        """验证 SQLBuilder 构建的 AST。"""
        validator = SQLValidator(TEST_SCHEMA)
        ast = (
            SQLBuilder()
            .select(["o.id", "u.name", "p.product_name"])
            .from_table("orders", alias="o")
            .join("users", "o.user_id = u.id", join_type="left", alias="u")
            .join("products", "o.product_id = p.id", join_type="left", alias="p")
            .where("o.status = 'completed'")
            .build()
        )
        result = validator.validate(ast)
        # 所有表都存在，验证应通过
        assert result.valid is True

    def test_builder_with_nonexistent_table(self) -> None:
        """验证 SQLBuilder 引用不存在表的 AST。"""
        validator = SQLValidator(TEST_SCHEMA)
        ast = (
            SQLBuilder()
            .select(["x.id"])
            .from_table("nonexistent", alias="x")
            .build()
        )
        result = validator.validate(ast)
        assert result.valid is False
