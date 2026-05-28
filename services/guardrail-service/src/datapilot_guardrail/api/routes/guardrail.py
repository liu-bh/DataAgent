"""Guardrail API 路由。

提供 SQL 预检和配额查询接口。
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

from datapilot_guardrail.checker import GuardrailChecker
from datapilot_guardrail.models import GuardrailResult

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Guardrail"])

# 全局检查器实例（启动时初始化，后续可替换为依赖注入）
_checker: GuardrailChecker | None = None


def get_checker() -> GuardrailChecker:
    """获取 GuardrailChecker 实例。

    Returns:
        GuardrailChecker 实例。
    """
    global _checker
    if _checker is None:
        _checker = GuardrailChecker()
    return _checker


def set_checker(checker: GuardrailChecker) -> None:
    """设置 GuardrailChecker 实例（用于测试或自定义配置）。

    Args:
        checker: GuardrailChecker 实例。
    """
    global _checker
    _checker = checker


# ---------------------------------------------------------------------------
# 请求/响应模型
# ---------------------------------------------------------------------------


class SQLCheckRequest(BaseModel):
    """SQL 预检请求体。

    Attributes:
        sql: 待检查的 SQL 语句。
        dialect: SQL 方言，默认 "mysql"。
        tenant_id: 租户 ID。
    """

    sql: str = Field(..., description="待检查的 SQL 语句", min_length=1)
    dialect: str = Field(default="mysql", description="SQL 方言")
    tenant_id: str = Field(..., description="租户 ID", min_length=1)


class QuotaResponse(BaseModel):
    """配额查询响应。

    Attributes:
        tenant_id: 租户 ID。
        passed: 是否通过配额检查。
        quota_remaining: 剩余配额。
    """

    tenant_id: str
    passed: bool
    quota_remaining: int


# ---------------------------------------------------------------------------
# POST /api/v1/guardrail/check-sql — SQL 预检
# ---------------------------------------------------------------------------


@router.post("/guardrail/check-sql", response_model=GuardrailResult)
async def check_sql(body: SQLCheckRequest) -> GuardrailResult:
    """SQL 预检接口。

    对 SQL 语句执行风险检测、行数限制和配额检查。

    Args:
        body: SQL 预检请求体。

    Returns:
        GuardrailResult 检查结果。
    """
    logger.info("收到 SQL 预检请求", tenant_id=body.tenant_id, dialect=body.dialect)
    checker = get_checker()
    result = await checker.check(
        sql=body.sql,
        tenant_id=body.tenant_id,
        dialect=body.dialect,
    )
    return result


# ---------------------------------------------------------------------------
# GET /api/v1/guardrail/quota/{tenant_id} — 查询配额
# ---------------------------------------------------------------------------


@router.get("/guardrail/quota/{tenant_id}", response_model=QuotaResponse)
async def get_quota(
    tenant_id: str,
) -> QuotaResponse:
    """查询租户的剩余配额。

    Args:
        tenant_id: 租户 ID。

    Returns:
        QuotaResponse 配额信息。
    """
    logger.info("查询租户配额", tenant_id=tenant_id)
    checker = get_checker()
    passed, remaining = await checker.quota_manager.check_quota(tenant_id=tenant_id)
    return QuotaResponse(
        tenant_id=tenant_id,
        passed=passed,
        quota_remaining=remaining,
    )
