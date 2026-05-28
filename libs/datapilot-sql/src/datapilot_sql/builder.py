"""SQL AST 构建器模块。

提供链式 API 构建 SQL AST，所有 SQL 操作通过 sqlglot AST 完成，不拼接字符串。

用法::

    from datapilot_sql.builder import SQLBuilder, Aggregate

    ast = (
        SQLBuilder()
        .select(["id", "name", Aggregate.sum("amount").as_("total")])
        .from_table("orders", alias="o")
        .join("users", "o.user_id = u.id", join_type="left")
        .where("o.created_at >= '2026-01-01'")
        .group_by("o.user_id", "u.name")
        .having(Aggregate.sum("amount") > 1000)
        .order_by("total", desc=True)
        .limit(100)
        .build()
    )
"""

from __future__ import annotations

from typing import Any

import sqlglot
from sqlglot import expressions as exp


class Aggregate:
    """聚合表达式工厂。

    提供静态方法创建聚合表达式（SUM, AVG, COUNT, MIN, MAX 等）。
    """

    def __init__(self, expression: exp.Expression) -> None:
        self._expression = expression

    @property
    def expression(self) -> exp.Expression:
        """获取底层 sqlglot 表达式。"""
        return self._expression

    def as_(self, alias: str) -> exp.Alias:
        """为聚合表达式设置别名。

        Args:
            alias: 别名。

        Returns:
            带别名的 Alias 表达式。
        """
        return exp.Alias(this=self._expression, alias=exp.to_identifier(alias))

    @classmethod
    def count(cls, column: str = "*") -> Aggregate:
        """创建 COUNT 聚合。

        Args:
            column: 列名，默认 '*' 表示 COUNT(*)。

        Returns:
            Aggregate 实例。
        """
        expr = exp.Count(this=exp.Star()) if column == "*" else exp.Count(this=exp.column(column))
        return cls(expr)

    @classmethod
    def sum(cls, column: str) -> Aggregate:
        """创建 SUM 聚合。

        Args:
            column: 列名。

        Returns:
            Aggregate 实例。
        """
        return cls(exp.Sum(this=exp.column(column)))

    @classmethod
    def avg(cls, column: str) -> Aggregate:
        """创建 AVG 聚合。

        Args:
            column: 列名。

        Returns:
            Aggregate 实例。
        """
        return cls(exp.Avg(this=exp.column(column)))

    @classmethod
    def min(cls, column: str) -> Aggregate:
        """创建 MIN 聚合。

        Args:
            column: 列名。

        Returns:
            Aggregate 实例。
        """
        return cls(exp.Min(this=exp.column(column)))

    @classmethod
    def max(cls, column: str) -> Aggregate:
        """创建 MAX 聚合。

        Args:
            column: 列名。

        Returns:
            Aggregate 实例。
        """
        return cls(exp.Max(this=exp.column(column)))

    def __gt__(self, other: Any) -> exp.GT:  # type: ignore[override]
        """支持 > 比较运算符，返回 sqlglot GT 表达式。"""
        return exp.GT(this=self._expression, expression=exp.Literal.number(other))

    def __lt__(self, other: Any) -> exp.LT:  # type: ignore[override]
        """支持 < 比较运算符，返回 sqlglot LT 表达式。"""
        return exp.LT(this=self._expression, expression=exp.Literal.number(other))

    def __ge__(self, other: Any) -> exp.GTE:  # type: ignore[override]
        """支持 >= 比较运算符，返回 sqlglot GTE 表达式。"""
        return exp.GTE(this=self._expression, expression=exp.Literal.number(other))

    def __le__(self, other: Any) -> exp.LTE:  # type: ignore[override]
        """支持 <= 比较运算符，返回 sqlglot LTE 表达式。"""
        return exp.LTE(this=self._expression, expression=exp.Literal.number(other))

    def __eq__(self, other: Any) -> bool:  # type: ignore[override]
        # 保持 object 的 __eq__ 语义，避免与 sqlglot EQ 混淆
        return super().__eq__(other)

    def eq(self, other: Any) -> exp.EQ:
        """创建等于比较。

        Args:
            other: 比较值。

        Returns:
            sqlglot EQ 表达式。
        """
        return exp.EQ(this=self._expression, expression=exp.Literal.number(other))


class _ConditionBuilder:
    """条件表达式辅助构建器。

    用于方便地构建 AND/OR 组合条件。
    """

    def __init__(self, expression: exp.Expression) -> None:
        self._expression = expression

    @property
    def expression(self) -> exp.Expression:
        """获取底层 sqlglot 条件表达式。"""
        return self._expression

    def and_(self, other: str | exp.Expression | _ConditionBuilder) -> _ConditionBuilder:
        """AND 组合条件。

        Args:
            other: 另一个条件，可以是 SQL 字符串、sqlglot 表达式或 _ConditionBuilder。

        Returns:
            新的 _ConditionBuilder 实例。
        """
        other_expr = self._to_expression(other)
        combined = exp.And(this=self._expression, expression=other_expr)
        return _ConditionBuilder(combined)

    def or_(self, other: str | exp.Expression | _ConditionBuilder) -> _ConditionBuilder:
        """OR 组合条件。

        Args:
            other: 另一个条件。

        Returns:
            新的 _ConditionBuilder 实例。
        """
        other_expr = self._to_expression(other)
        combined = exp.Or(this=self._expression, expression=other_expr)
        return _ConditionBuilder(combined)

    @classmethod
    def _to_expression(cls, value: str | exp.Expression | _ConditionBuilder) -> exp.Expression:
        """将各种输入转为 sqlglot 表达式。"""
        if isinstance(value, _ConditionBuilder):
            return value.expression
        if isinstance(value, exp.Expression):
            return value
        # 字符串视为 SQL 片段，通过 sqlglot 解析
        return sqlglot.parse_one(value, into=exp.Condition)


def cond(condition: str) -> _ConditionBuilder:
    """从 SQL 条件字符串创建条件构建器。

    Args:
        condition: SQL WHERE 条件片段，如 "age > 18"。

    Returns:
        _ConditionBuilder 实例。
    """
    expr = sqlglot.parse_one(condition, into=exp.Condition)
    return _ConditionBuilder(expr)


# 列定义类型：支持字符串列名、带别名的元组、sqlglot 表达式、Alias 或 Aggregate
ColumnSpec = str | tuple[str, str] | exp.Expression | exp.Alias | Aggregate


class SQLBuilder:
    """SQL AST 链式构建器。

    通过链式 API 构建 sqlglot AST，最终调用 build() 获取 AST 表达式。

    示例::

        ast = (
            SQLBuilder()
            .select(["id", ("name", "user_name"), Aggregate.sum("amount").as_("total")])
            .from_table("orders")
            .where("status = 'active'")
            .group_by("id")
            .limit(100)
            .build()
        )
    """

    def __init__(self) -> None:
        """初始化构建器，所有内部状态为空。"""
        self._distinct: bool = False
        self._columns: list[exp.Expression] = []
        self._from_table: exp.Expression | None = None
        self._joins: list[exp.Join] = []
        self._where: exp.Expression | None = None
        self._group_by: list[exp.Expression] = []
        self._having: exp.Expression | None = None
        self._order_by: list[exp.Ordered] = []
        self._limit: exp.Limit | None = None

    def select(self, columns: list[ColumnSpec], distinct: bool = False) -> SQLBuilder:
        """指定查询列。

        Args:
            columns: 列定义列表，支持以下格式：
                - 字符串: "column_name"
                - 元组: ("column_name", "alias")
                - sqlglot 表达式: exp.Column 等
                - Aggregate: 聚合表达式
            distinct: 是否去重。

        Returns:
            self（支持链式调用）。
        """
        self._distinct = distinct
        for col in columns:
            self._columns.append(self._resolve_column(col))
        return self

    def from_table(self, table_name: str, alias: str | None = None) -> SQLBuilder:
        """指定来源表。

        Args:
            table_name: 表名。
            alias: 表别名。

        Returns:
            self（支持链式调用）。
        """
        if alias:
            table_expr = exp.Table(
                this=exp.to_identifier(table_name),
                alias=exp.TableAlias(this=exp.to_identifier(alias)),
            )
        else:
            table_expr = exp.Table(this=exp.to_identifier(table_name))
        self._from_table = table_expr
        return self

    def join(
        self,
        table_name: str,
        on_condition: str | exp.Expression,
        join_type: str = "inner",
        alias: str | None = None,
    ) -> SQLBuilder:
        """添加 JOIN 子句。

        Args:
            table_name: 要连接的表名。
            on_condition: JOIN 条件，支持 SQL 字符串或 sqlglot 表达式。
            join_type: JOIN 类型，支持 "inner"/"left"/"right"/"full"/"cross"。
            alias: 表别名。

        Returns:
            self（支持链式调用）。
        """
        # 构建目标表
        if alias:
            table_expr = exp.Table(
                this=exp.to_identifier(table_name),
                alias=exp.TableAlias(this=exp.to_identifier(alias)),
            )
        else:
            table_expr = exp.Table(this=exp.to_identifier(table_name))

        # 解析 ON 条件
        if isinstance(on_condition, str):
            on_expr = sqlglot.parse_one(on_condition, into=exp.Condition)
        else:
            on_expr = on_condition

        # 构建 JOIN 类型
        kind_map = {
            "inner": "",
            "left": "LEFT",
            "right": "RIGHT",
            "full": "FULL",
            "cross": "CROSS",
            "left_outer": "LEFT OUTER",
            "right_outer": "RIGHT OUTER",
        }
        side = kind_map.get(join_type.lower(), "")
        kind = exp.Join(kind=side) if side else exp.Join()

        join_node = exp.Join(
            this=table_expr,
            on=on_expr,
            kind=kind.args.get("kind") if side else None,
            side=side,
        )
        self._joins.append(join_node)
        return self

    def where(self, condition: str | exp.Expression | _ConditionBuilder) -> SQLBuilder:
        """添加 WHERE 条件。

        多次调用 where() 会以 AND 方式组合所有条件。

        Args:
            condition: 条件表达式，支持 SQL 字符串、sqlglot 表达式或 _ConditionBuilder。

        Returns:
            self（支持链式调用）。
        """
        expr = self._to_expression(condition)
        if self._where is None:
            self._where = expr
        else:
            self._where = exp.And(this=self._where, expression=expr)
        return self

    def group_by(self, *columns: str) -> SQLBuilder:
        """添加 GROUP BY 子句。

        Args:
            columns: 分组列名。

        Returns:
            self（支持链式调用）。
        """
        for col in columns:
            self._group_by.append(exp.column(col))
        return self

    def having(self, condition: str | exp.Expression) -> SQLBuilder:
        """添加 HAVING 条件。

        Args:
            condition: HAVING 条件表达式。

        Returns:
            self（支持链式调用）。
        """
        expr = self._to_expression(condition)
        self._having = expr
        return self

    def order_by(self, *columns: str, desc: bool = False) -> SQLBuilder:
        """添加 ORDER BY 子句。

        Args:
            columns: 排序列名。
            desc: 是否降序。

        Returns:
            self（支持链式调用）。
        """
        for col in columns:
            ordered = exp.Ordered(
                this=exp.column(col),
                desc=desc,
            )
            self._order_by.append(ordered)
        return self

    def limit(self, count: int, offset: int | None = None) -> SQLBuilder:
        """添加 LIMIT 子句。

        Args:
            count: 限制行数。
            offset: 偏移量。

        Returns:
            self（支持链式调用）。
        """
        self._limit = exp.Limit(expression=exp.Literal.number(count))
        if offset is not None:
            self._limit.set("offset", exp.Offset(expression=exp.Literal.number(offset)))
        return self

    def build(self) -> exp.Select:
        """构建最终的 sqlglot AST。

        Returns:
            sqlglot Select 表达式。

        Raises:
            ValueError: 未指定查询列时抛出。
        """
        if not self._columns:
            raise ValueError("必须指定至少一个查询列，使用 select() 方法")

        if self._from_table is None:
            raise ValueError("必须指定来源表，使用 from_table() 方法")

        # 构建 SELECT 表达式
        select_kwargs: dict[str, Any] = {
            "expressions": self._columns,
        }
        if self._distinct:
            select_kwargs["distinct"] = exp.Distinct()
        select_node = exp.Select(**select_kwargs)

        # 设置 FROM
        select_node.set("from_", exp.From(this=self._from_table))

        # 设置 JOIN
        if self._joins:
            select_node.set("joins", self._joins)

        # 设置 WHERE
        if self._where is not None:
            select_node.set("where", exp.Where(this=self._where))

        # 设置 GROUP BY
        if self._group_by:
            select_node.set("group", exp.Group(expressions=self._group_by))

        # 设置 HAVING
        if self._having is not None:
            select_node.set("having", exp.Having(this=self._having))

        # 设置 ORDER BY
        if self._order_by:
            select_node.set("order", exp.Order(expressions=self._order_by))

        # 设置 LIMIT
        if self._limit is not None:
            select_node.set("limit", self._limit)

        return select_node

    @staticmethod
    def _resolve_column(col: ColumnSpec) -> exp.Expression:
        """将各种列定义格式解析为 sqlglot 表达式。

        Args:
            col: 列定义。

        Returns:
            sqlglot 表达式。
        """
        if isinstance(col, str):
            return exp.column(col)
        if isinstance(col, tuple):
            col_name, alias = col
            return exp.Alias(this=exp.column(col_name), alias=exp.to_identifier(alias))
        if isinstance(col, Aggregate):
            return col.expression
        if isinstance(col, exp.Expression):
            return col
        raise TypeError(f"不支持的列定义类型: {type(col)}")

    @staticmethod
    def _to_expression(value: str | exp.Expression | _ConditionBuilder) -> exp.Expression:
        """将各种输入转为 sqlglot 表达式。"""
        if isinstance(value, _ConditionBuilder):
            return value.expression
        if isinstance(value, exp.Expression):
            return value
        # 字符串通过 sqlglot 解析
        return sqlglot.parse_one(value)
