"""SQL 验证模块。

提供 SQL Dry-run 预执行、成本预估和综合验证编排能力。

用法::

    from datapilot_sqlgen.validation import SQLValidationOrchestrator

    orchestrator = SQLValidationOrchestrator()
    result = await orchestrator.validate("SELECT COUNT(*) FROM orders")
    if not result.is_valid:
        for error in result.errors:
            print(error)
"""

from datapilot_sqlgen.validation.cost_estimator import SQLCostEstimator
from datapilot_sqlgen.validation.dryrun import SQLDryRunner
from datapilot_sqlgen.validation.models import CostEstimate, DryRunResult, ValidationResult
from datapilot_sqlgen.validation.validator import SQLValidationOrchestrator

__all__ = [
    "CostEstimate",
    "DryRunResult",
    "SQLCostEstimator",
    "SQLDryRunner",
    "SQLValidationOrchestrator",
    "ValidationResult",
]
