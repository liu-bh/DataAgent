"""SQL AST 验证器模块。

对 SQL AST 进行语义级别的验证，包括表/列是否存在、语法正确性和方言兼容性。

用法::

    from datapilot_sql.validator import SQLValidator, ValidationResult

    schema = {
        "orders": {"id": "int", "amount": "decimal", "user_id": "int", "status": "varchar"},
        "users": {"id": "int", "name": "varchar"},
    }

    validator = SQLValidator(schema)
    result = validator.validate(ast, target_dialect=Dialect.POSTGRESQL)
    if not result.valid:
        for error in result.errors:
            print(error)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlglot.expressions import Column, Expression, Subquery, Table

from datapilot_sql.dialect import Dialect, check_compatibility


@dataclass
class ValidationResult:
    """SQL 验证结果。

    Attributes:
        valid: 是否验证通过。
        errors: 错误列表，每项为错误描述字符串。
        warnings: 警告列表，每项为警告描述字符串。
    """

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """添加错误信息。"""
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str) -> None:
        """添加警告信息。"""
        self.warnings.append(message)


class SQLValidator:
    """SQL AST 验证器。

    对 SQL AST 进行多维度验证：
    1. 语法正确性（由 sqlglot 解析保证）
    2. 表是否存在于 schema
    3. 列是否存在于对应表
    4. 方言兼容性

    Args:
        schema: 数据库 schema 定义，格式为 {表名: {列名: 类型}}。
    """

    def __init__(self, schema: dict[str, dict[str, str]] | None = None) -> None:
        """初始化验证器。

        Args:
            schema: 数据库 schema，格式为 {"table_name": {"column_name": "column_type"}}。
        """
        self._schema = schema or {}

    @property
    def schema(self) -> dict[str, dict[str, str]]:
        """获取当前 schema。"""
        return self._schema

    def update_schema(self, schema: dict[str, dict[str, str]]) -> None:
        """更新 schema。

        Args:
            schema: 新的 schema 定义，会合并到现有 schema 中。
        """
        self._schema.update(schema)

    def validate(
        self,
        ast: Expression,
        target_dialect: Dialect | None = None,
    ) -> ValidationResult:
        """验证 SQL AST。

        Args:
            ast: sqlglot AST 表达式。
            target_dialect: 目标方言，为 None 时不检查方言兼容性。

        Returns:
            ValidationResult 验证结果。
        """
        result = ValidationResult()

        # 1. 提取引用的表和列
        tables = self._extract_tables(ast)
        columns = self._extract_columns(ast)

        # 2. 检查表是否存在
        for table_info in tables:
            table_name = table_info["name"]
            if table_name not in self._schema:
                result.add_error(f"表 '{table_name}' 不存在于 schema 中")

        # 3. 检查列是否存在于对应表
        valid_tables = {t["name"] for t in tables if t["name"] in self._schema}
        for col_info in columns:
            col_name = col_info["name"]
            col_table = col_info["table"]
            if col_table:
                if col_table in valid_tables and col_name != "*":
                    table_columns = self._schema.get(col_table, {})
                    if col_name not in table_columns:
                        result.add_error(f"列 '{col_table}.{col_name}' 不存在于表 '{col_table}' 中")
            # 没有表限定的列：检查所有引用的表
            elif valid_tables:
                found = False
                for t_name in valid_tables:
                    if col_name == "*":
                        found = True
                        break
                    if col_name in self._schema.get(t_name, {}):
                        found = True
                        break
                if not found and col_name != "*":
                    result.add_warning(f"列 '{col_name}' 未在引用的表 {valid_tables} 中找到")

        # 4. 方言兼容性检查
        if target_dialect is not None:
            issues = check_compatibility(ast, target_dialect)
            for issue in issues:
                if issue.severity == "error":
                    result.add_error(f"[方言兼容性] {issue.description}")
                else:
                    result.add_warning(f"[方言兼容性] {issue.description}")

        return result

    def _extract_tables(self, ast: Expression) -> list[dict[str, str]]:
        """从 AST 中提取引用的表。

        Args:
            ast: sqlglot AST 表达式。

        Returns:
            表信息列表，每项包含 "name" 和可选的 "alias"。
        """
        tables: list[dict[str, str]] = []

        for node in ast.walk():
            if isinstance(node, Table):
                table_name = node.name
                alias = None
                # 检查外层是否有别名（通过 Subquery 包裹的别名表）
                parent = node.parent
                if parent and isinstance(parent, Subquery):
                    alias_node = parent.args.get("alias")
                    if alias_node:
                        alias = alias_node.alias if hasattr(alias_node, "alias") else None

                # 避免重复
                if not any(t["name"] == table_name for t in tables):
                    entry: dict[str, str] = {"name": table_name}
                    if alias:
                        entry["alias"] = alias
                    tables.append(entry)

        return tables

    def _extract_columns(self, ast: Expression) -> list[dict[str, str | None]]:
        """从 AST 中提取引用的列。

        Args:
            ast: sqlglot AST 表达式。

        Returns:
            列信息列表，每项包含 "name" 和 "table"。
        """
        columns: list[dict[str, str | None]] = []

        for node in ast.walk():
            if isinstance(node, Column):
                col_name = node.name
                col_table = node.table

                # 避免重复
                if not any(c["name"] == col_name and c["table"] == col_table for c in columns):
                    columns.append({"name": col_name, "table": col_table})

        return columns
