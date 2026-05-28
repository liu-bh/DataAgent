"""RCA 根因分析 API。

提供 RCA 分析的 REST 接口，支持发起分析、查询结果和历史记录。
"""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from datapilot_agent.rca.models import AnomalyResult, AttributionResult, RCAReport
from datapilot_agent.rca.store import RCAStore

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/rca", tags=["rca"])

# 全局 RCA 分析记录存储（单例）
_store = RCAStore()


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class RCAAnalyzeRequest(BaseModel):
    """RCA 分析请求。"""

    model_config = ConfigDict(from_attributes=True)

    question: str = Field(..., min_length=1, max_length=2000, description="分析问题")
    metric_name: str = Field(..., min_length=1, description="指标名称")
    current_data: dict = Field(..., description="当前数据")
    baseline_data: dict = Field(..., description="基线数据")
    dimensions: list[dict] | None = Field(default=None, description="分析维度列表")


class RCAAnalyzeResponse(BaseModel):
    """RCA 分析响应。"""

    model_config = ConfigDict(from_attributes=True)

    analysis_id: str = Field(..., description="分析 ID")
    report: dict = Field(..., description="RCA 分析报告")
    execution_time_ms: float = Field(..., description="执行耗时（毫秒）")


class RCAHistoryItem(BaseModel):
    """RCA 历史记录条目。"""

    model_config = ConfigDict(from_attributes=True)

    analysis_id: str = Field(..., description="分析 ID")
    question: str = Field(..., description="分析问题")
    metric_name: str = Field(..., description="指标名称")
    anomaly_detected: bool = Field(..., description="是否检测到异常")
    change_percent: float = Field(..., description="变化百分比")
    created_at: str = Field(default="", description="创建时间")


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _build_stub_report(
    analysis_id: str,
    question: str,
    metric_name: str,
    current_data: dict,
    baseline_data: dict,
    dimensions: list[dict] | None,
) -> RCAReport:
    """构建 Phase1 stub 的 RCA 报告。

    TODO: 生产环境替换为 RCAOrchestrator.analyze() 调用。
    """
    from datapilot_agent.rca.models import DimensionValue, DrillDownResult

    current_value = float(current_data.get("value", 0))
    baseline_value = float(baseline_data.get("value", 1))
    change_percent = round(
        ((current_value - baseline_value) / baseline_value * 100) if baseline_value != 0 else 0.0,
        2,
    )

    anomaly = AnomalyResult(
        metric_name=metric_name,
        current_value=current_value,
        baseline_value=baseline_value,
        change_percent=change_percent,
        is_anomaly=abs(change_percent) > 5.0,
        anomaly_type="drop" if change_percent < 0 else "spike",
        confidence=0.85,
        direction="down" if change_percent < 0 else "up",
    )

    # 构建维度下钻结果
    drill_downs: list[DrillDownResult] = []
    if dimensions:
        for dim in dimensions[:5]:
            dim_name = dim.get("name", "未知维度")
            dv = DimensionValue(
                value="示例值",
                current=current_value * 0.3,
                baseline=baseline_value * 0.3,
                change=current_value * 0.3 - baseline_value * 0.3,
                change_percent=change_percent,
                contribution=current_value - baseline_value,
                contribution_percent=round(change_percent * 0.3, 2),
            )
            drill_downs.append(
                DrillDownResult(
                    dimension_name=dim_name,
                    values=[dv],
                    top_contributors=[dv],
                )
            )

    attribution = AttributionResult(
        total_change=current_value - baseline_value,
        total_change_percent=change_percent,
        dimensions=[
            {
                "dimension": dim.get("name", "未知维度") if dimensions else "总体",
                "contribution": round((current_value - baseline_value) * 0.5, 2),
                "contribution_percent": 50.0,
            }
            for dim in (dimensions or [{}])[:3]
        ],
        key_drivers=["[Stub] 示例驱动因素"],
    )

    summary = (
        f"[Stub] 分析问题：{question}。"
        f"指标 {metric_name} 相对基线变化 {change_percent}%。"
        f"生产环境应调用 RCAOrchestrator 生成详细分析。"
    )

    return RCAReport(
        analysis_id=analysis_id,
        question=question,
        anomaly=anomaly,
        drill_downs=drill_downs,
        attribution=attribution,
        summary=summary,
        confidence=0.85,
        execution_time_ms=0.0,
    )


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------


@router.post("/analyze", response_model=RCAAnalyzeResponse)
async def analyze_rca(request: RCAAnalyzeRequest) -> RCAAnalyzeResponse:
    """执行 RCA 根因分析。

    分析指定指标的变化，检测异常并进行维度下钻和归因分析。

    Args:
        request: RCA 分析请求。

    Returns:
        分析结果和报告。
    """
    start_time = time.time()
    analysis_id = f"rca-{uuid.uuid4().hex[:12]}"

    try:
        report = _build_stub_report(
            analysis_id=analysis_id,
            question=request.question,
            metric_name=request.metric_name,
            current_data=request.current_data,
            baseline_data=request.baseline_data,
            dimensions=request.dimensions,
        )
    except Exception as exc:
        logger.error("RCA 分析失败", analysis_id=analysis_id, error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail=f"RCA 分析失败: {exc}") from exc

    # 保存分析记录
    _store.save(report)

    execution_time_ms = round((time.time() - start_time) * 1000, 2)

    logger.info(
        "RCA 分析完成",
        analysis_id=analysis_id,
        metric_name=request.metric_name,
        change_percent=report.anomaly.change_percent,
        is_anomaly=report.anomaly.is_anomaly,
        execution_time_ms=execution_time_ms,
    )

    return RCAAnalyzeResponse(
        analysis_id=analysis_id,
        report=report.to_dict(),
        execution_time_ms=execution_time_ms,
    )


@router.get("/{analysis_id}/result")
async def get_rca_result(analysis_id: str) -> dict:
    """获取 RCA 分析结果。

    Args:
        analysis_id: 分析 ID。

    Returns:
        RCA 分析报告详情。

    Raises:
        HTTPException: 分析记录不存在时返回 404。
    """
    report = _store.get(analysis_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"RCA 分析记录不存在: {analysis_id}")

    return report.to_dict()


@router.get("/history", response_model=list[RCAHistoryItem])
async def get_rca_history(limit: int = 50) -> list[RCAHistoryItem]:
    """获取 RCA 分析历史记录。

    Args:
        limit: 最大返回数量，默认 50。

    Returns:
        分析历史记录列表。
    """
    records = _store.list_all(limit=limit)

    items: list[RCAHistoryItem] = []
    for report in records:
        items.append(
            RCAHistoryItem(
                analysis_id=report.analysis_id,
                question=report.question,
                metric_name=report.anomaly.metric_name,
                anomaly_detected=report.anomaly.is_anomaly,
                change_percent=report.anomaly.change_percent,
            )
        )

    return items
