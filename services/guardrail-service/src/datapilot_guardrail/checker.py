"""Guardrail 综合检查器。

编排 SQL 风险检测、行数限制和查询配额三项检查，返回统一的检查结果。
"""

from __future__ import annotations

import structlog

from datapilot_guardrail.models import GuardrailResult, QuotaConfig, RiskLevel
from datapilot_guardrail.quota import QueryQuotaManager
from datapilot_guardrail.row_limit import RowLimitEnforcer
from datapilot_guardrail.sql_risk import SQLRiskDetector

logger = structlog.get_logger(__name__)


class GuardrailChecker:
    """Guardrail 综合检查器。

    依次执行以下检查流程：
    1. SQL 风险检测 — 如果 BLOCKED，直接返回 passed=False
    2. 行数限制检查
    3. 查询配额检查
    4. 汇总结果返回 GuardrailResult
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        """初始化综合检查器。

        Args:
            redis_url: Redis 连接 URL，用于配额管理。
        """
        self.sql_risk_detector = SQLRiskDetector()
        self.row_limit_enforcer = RowLimitEnforcer()
        self.quota_manager = QueryQuotaManager(redis_url=redis_url)

    async def check(
        self,
        sql: str,
        tenant_id: str,
        dialect: str = "mysql",
        quota_config: QuotaConfig | None = None,
    ) -> GuardrailResult:
        """执行综合 Guardrail 检查。

        Args:
            sql: 待检查的 SQL 语句。
            tenant_id: 租户 ID。
            dialect: SQL 方言，默认 "mysql"。
            quota_config: 配额配置，None 时使用默认值。

        Returns:
            GuardrailResult 检查结果。
        """
        warnings: list[str] = []

        # 1. SQL 风险检测
        logger.info("开始 SQL 风险检测", tenant_id=tenant_id)
        risk_level, risk_reason = self.sql_risk_detector.check(sql, dialect=dialect)

        if risk_level == RiskLevel.BLOCKED:
            logger.warning(
                "SQL 风险检测未通过，已拦截",
                tenant_id=tenant_id,
                risk_level=risk_level,
                reason=risk_reason,
            )
            return GuardrailResult(
                passed=False,
                risk_level=risk_level,
                blocked_reason=risk_reason,
                warnings=warnings,
            )

        if risk_level in (RiskLevel.HIGH, RiskLevel.MEDIUM):
            warnings.append(risk_reason)
            logger.info(
                "SQL 存在风险提示",
                tenant_id=tenant_id,
                risk_level=risk_level,
                reason=risk_reason,
            )

        # 2. 行数限制检查
        logger.info("开始行数限制检查", tenant_id=tenant_id)
        effective_max_rows = (
            quota_config.max_rows_per_query if quota_config else QuotaConfig().max_rows_per_query
        )
        needs_limit, actual_limit = self.row_limit_enforcer.check(sql, max_rows=effective_max_rows)

        if needs_limit:
            warnings.append(f"SQL 未指定 LIMIT 或超过限制，将截断为 {actual_limit} 行")

        # 3. 查询配额检查
        logger.info("开始查询配额检查", tenant_id=tenant_id)
        quota_passed, quota_remaining = await self.quota_manager.check_quota(
            tenant_id=tenant_id,
            config=quota_config,
        )

        if not quota_passed:
            logger.warning(
                "租户配额已耗尽，请求被拒绝",
                tenant_id=tenant_id,
                quota_remaining=quota_remaining,
            )
            return GuardrailResult(
                passed=False,
                risk_level=risk_level,
                blocked_reason="查询配额已耗尽，请稍后再试",
                max_rows=actual_limit,
                quota_remaining=quota_remaining,
                warnings=warnings,
            )

        # 4. 所有检查通过
        passed = risk_level not in (RiskLevel.BLOCKED,)
        logger.info(
            "Guardrail 检查完成",
            tenant_id=tenant_id,
            passed=passed,
            risk_level=risk_level,
            max_rows=actual_limit,
            quota_remaining=quota_remaining,
        )

        return GuardrailResult(
            passed=passed,
            risk_level=risk_level,
            max_rows=actual_limit,
            quota_remaining=quota_remaining,
            warnings=warnings,
        )
