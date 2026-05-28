"""SQL 验证编排器模块。

协调 AST 语法验证、Dry-run 预执行和成本预估三个步骤，
汇总所有错误和警告，输出综合 ValidationResult。

各步骤独立执行，单步失败不阻塞后续步骤。
"""

from __future__ import annotations

import structlog

from datapilot_sqlgen.validation.cost_estimator import SQLCostEstimator
from datapilot_sqlgen.validation.dryrun import SQLDryRunner
from datapilot_sqlgen.validation.models import CostEstimate, DryRunResult, ValidationResult

logger = structlog.get_logger(__name__)

# 支持的 SQL 方言
SUPPORTED_DIALECTS = frozenset({"mysql", "postgresql", "doris", "starrocks", "clickhouse"})

# 方言名映射：DataPilot 标准名 -> sqlglot 方言名
_DIALECT_MAP: dict[str, str] = {
    "postgresql": "postgres",
    "mysql": "mysql",
    "doris": "mysql",
    "starrocks": "mysql",
    "clickhouse": "clickhouse",
}


class SQLValidationOrchestrator:
    """SQL 验证编排器。

    编排三个验证步骤的执行：
    1. AST 语法验证 — 使用 sqlglot 解析 SQL，检查语法正确性
    2. Dry-run 预执行 — 检查表/列存在性
    3. 成本预估 — 估算查询执行成本

    所有步骤均独立执行，即使某步失败也会继续后续步骤。

    Args:
        connection_url: 可选的数据库连接串，为 None 时各步骤降级为 AST 检查。
        default_limit: 默认的 LIMIT 上限，用于成本估算参考。
    """

    def __init__(
        self,
        connection_url: str | None = None,
        default_limit: int = 10000,
    ) -> None:
        self._connection_url = connection_url
        self._default_limit = default_limit
        self._dry_runner = SQLDryRunner(connection_url=connection_url)
        self._cost_estimator = SQLCostEstimator(connection_url=connection_url)

    async def validate(self, sql: str, dialect: str = "mysql") -> ValidationResult:
        """对 SQL 执行综合验证。

        依次执行 AST 验证、Dry-run 预执行和成本预估，汇总结果。

        Args:
            sql: 待验证的 SQL 字符串。
            dialect: SQL 方言。

        Returns:
            ValidationResult 综合验证结果。
        """
        errors: list[str] = []
        warnings: list[str] = []
        ast_valid = True
        dryrun_passed = True
        cost_estimate: CostEstimate | None = None

        # 方言校验
        if dialect.lower() not in SUPPORTED_DIALECTS:
            warnings.append(f"方言 '{dialect}' 不在已知支持列表中，解析可能不准确")

        # ---- 步骤 1: AST 语法验证 ----
        ast_result = self._validate_ast(sql, dialect)
        ast_valid = bool(ast_result["valid"])
        errors.extend(ast_result["errors"])
        warnings.extend(ast_result["warnings"])

        # ---- 步骤 2: Dry-run 预执行 ----
        dryrun_result: DryRunResult = await self._dry_runner.check(sql, dialect)
        dryrun_passed = dryrun_result.success
        if dryrun_result.error:
            errors.append(f"[Dry-run] {dryrun_result.error}")
        warnings.extend(dryrun_result.warnings)

        # ---- 步骤 3: 成本预估 ----
        cost_estimate = await self._cost_estimator.estimate(sql, dialect)
        if cost_estimate.cost_level == "high":
            warnings.append(
                f"[成本预估] 查询成本较高（预估 {cost_estimate.estimated_rows} 行，"
                f"约 {cost_estimate.estimated_time_ms} ms），建议添加筛选条件或 LIMIT"
            )

        # ---- 汇总结果 ----
        is_valid = ast_valid and dryrun_passed

        result = ValidationResult(
            is_valid=is_valid,
            ast_valid=ast_valid,
            dryrun_passed=dryrun_passed,
            cost_estimate=cost_estimate,
            errors=errors,
            warnings=warnings,
        )

        logger.info(
            "SQL 验证完成",
            is_valid=is_valid,
            ast_valid=ast_valid,
            dryrun_passed=dryrun_passed,
            cost_level=cost_estimate.cost_level if cost_estimate else "unknown",
            error_count=len(errors),
            warning_count=len(warnings),
        )

        return result

    # ------------------------------------------------------------------
    # AST 语法验证
    # ------------------------------------------------------------------

    def _validate_ast(self, sql: str, dialect: str) -> dict[str, object]:
        """使用 sqlglot 对 SQL 进行 AST 语法验证。

        Args:
            sql: SQL 字符串。
            dialect: SQL 方言。

        Returns:
            包含 valid, errors, warnings 的字典。
        """
        errors: list[str] = []
        warnings: list[str] = []

        if not sql or not sql.strip():
            return {"valid": False, "errors": ["SQL 为空"], "warnings": warnings}

        try:
            import sqlglot
            from sqlglot import expressions as exp

            # 将 DataPilot 方言名转换为 sqlglot 方言名
            sqlglot_dialect = _DIALECT_MAP.get(dialect, dialect)
            ast = sqlglot.parse_one(sql, read=sqlglot_dialect)

            # sqlglot 会将无法识别的 SQL 解析为表达式（如 Mul），
            # 需要判断根节点是否为 SELECT / INSERT / UPDATE / DELETE 等合法语句
            valid_root_types = (exp.Select, exp.Insert, exp.Update, exp.Delete, exp.Create)
            if not isinstance(ast, valid_root_types):
                return {
                    "valid": False,
                    "errors": [f"SQL 语法不正确，解析结果为 {type(ast).__name__} 而非合法 SQL 语句"],
                    "warnings": warnings,
                }

            # 检查是否为只读操作（SELECT）
            if not isinstance(ast, exp.Select):
                warnings.append("SQL 不是 SELECT 语句，Dry-run 和成本预估可能不准确")

            # 检查是否有 LIMIT
            has_limit = False
            if isinstance(ast, exp.Select):
                has_limit = ast.args.get("limit") is not None
            if not has_limit:
                warnings.append(
                    f"SQL 未包含 LIMIT，建议添加 LIMIT {self._default_limit} 以控制返回行数"
                )

            return {"valid": True, "errors": errors, "warnings": warnings}

        except Exception as exc:  # noqa: BLE001
            return {
                "valid": False,
                "errors": [f"SQL 语法解析失败: {exc}"],
                "warnings": warnings,
            }
