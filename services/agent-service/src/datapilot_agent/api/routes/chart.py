"""图表推荐和渲染 API。

提供基于数据特征的图表类型推荐和 ECharts 配置渲染。
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/chart", tags=["chart"])


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class ChartRecommendRequest(BaseModel):
    """图表推荐请求。"""

    model_config = ConfigDict(from_attributes=True)

    columns: list[dict[str, Any]] = Field(..., description="列元数据列表，每项包含 name, type 等")
    rows: list[dict[str, Any]] = Field(..., description="数据行列表")
    user_question: str = Field(default="", description="用户原始问题，用于辅助推荐")


class ChartRecommendResponse(BaseModel):
    """图表推荐响应。"""

    model_config = ConfigDict(from_attributes=True)

    recommended_types: list[dict[str, Any]] = Field(
        default_factory=list,
        description="推荐图表类型列表，每项包含 type, confidence, title, description",
    )
    x_field: str = Field(default="", description="推荐 X 轴字段")
    y_fields: list[str] = Field(default_factory=list, description="推荐 Y 轴字段列表")


class ChartRenderRequest(BaseModel):
    """图表渲染请求。"""

    model_config = ConfigDict(from_attributes=True)

    chart_type: str = Field(..., description="图表类型，如 bar, line, pie, scatter 等")
    columns: list[dict[str, Any]] = Field(..., description="列元数据列表")
    rows: list[dict[str, Any]] = Field(..., description="数据行列表")
    x_field: str = Field(default="", description="X 轴字段名")
    y_fields: list[str] = Field(default_factory=list, description="Y 轴字段名列表")
    title: str = Field(default="", description="图表标题")


class ChartRenderResponse(BaseModel):
    """图表渲染响应。"""

    model_config = ConfigDict(from_attributes=True)

    chart_type: str = Field(..., description="图表类型")
    title: str = Field(default="", description="图表标题")
    echarts_option: dict[str, Any] = Field(default_factory=dict, description="ECharts 配置")


# ---------------------------------------------------------------------------
# 规则推断器（Phase1 基于 heuristic）
# ---------------------------------------------------------------------------


def _infer_chart_type(
    columns: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    user_question: str = "",
) -> ChartRecommendResponse:
    """基于数据特征推断推荐图表类型。

    Phase1 使用规则推断器，后续可替换为 LLM 推荐引擎。

    Args:
        columns: 列元数据列表。
        rows: 数据行列表。
        user_question: 用户原始问题。

    Returns:
        图表推荐结果。
    """
    if not columns or not rows:
        return ChartRecommendResponse(
            recommended_types=[],
            x_field="",
            y_fields=[],
        )

    # 分类字段和数值字段
    categorical_fields: list[str] = []
    numeric_fields: list[str] = []
    time_fields: list[str] = []

    for col in columns:
        col_name = col.get("name", "")
        col_type = col.get("type", "").lower()
        if col_type in ("date", "datetime", "timestamp", "time"):
            time_fields.append(col_name)
        elif col_type in ("integer", "int", "float", "double", "decimal", "number", "numeric"):
            numeric_fields.append(col_name)
        else:
            categorical_fields.append(col_name)

    # 确定推荐
    recommendations: list[dict[str, Any]] = []
    x_field = ""
    y_fields: list[str] = []

    # 优先使用时间字段作为 X 轴
    if time_fields:
        x_field = time_fields[0]
        y_fields = numeric_fields[:3]
        recommendations.append({
            "type": "line",
            "confidence": 0.9,
            "title": "趋势图",
            "description": "时间维度的趋势变化",
        })
        if len(numeric_fields) > 1:
            recommendations.append({
                "type": "bar",
                "confidence": 0.75,
                "title": "对比柱状图",
                "description": "不同指标间的对比",
            })
    elif categorical_fields and numeric_fields:
        x_field = categorical_fields[0]
        y_fields = numeric_fields[:3]
        if len(rows) <= 6 and len(categorical_fields) == 1 and len(numeric_fields) == 1:
            recommendations.append({
                "type": "pie",
                "confidence": 0.85,
                "title": "占比饼图",
                "description": "分类占比分布",
            })
        recommendations.append({
            "type": "bar",
            "confidence": 0.8,
            "title": "柱状图",
            "description": "分类维度的数值对比",
        })
        if len(numeric_fields) >= 2:
            recommendations.append({
                "type": "scatter",
                "confidence": 0.7,
                "title": "散点图",
                "description": "多个数值字段间的关联",
            })
    elif numeric_fields and len(numeric_fields) >= 2:
        x_field = numeric_fields[0]
        y_fields = numeric_fields[1:3]
        recommendations.append({
            "type": "scatter",
            "confidence": 0.75,
            "title": "散点图",
            "description": "数值字段间的关联分布",
        })
        recommendations.append({
            "type": "bar",
            "confidence": 0.6,
            "title": "柱状图",
            "description": "数值对比",
        })
    else:
        # 默认推荐
        if columns:
            x_field = columns[0].get("name", "")
        if len(columns) > 1:
            y_fields = [columns[1].get("name", "")]
        recommendations.append({
            "type": "bar",
            "confidence": 0.5,
            "title": "柱状图",
            "description": "默认推荐柱状图",
        })

    # 根据用户问题微调
    if user_question:
        question_lower = user_question.lower()
        if "趋势" in question_lower or "趋势" in user_question:
            # 确保趋势图优先
            trend_exists = any(r["type"] == "line" for r in recommendations)
            if not trend_exists:
                recommendations.insert(0, {
                    "type": "line",
                    "confidence": 0.8,
                    "title": "趋势图",
                    "description": "根据用户问题推荐的趋势图",
                })
        if "占比" in question_lower or "比例" in user_question:
            pie_exists = any(r["type"] == "pie" for r in recommendations)
            if not pie_exists:
                recommendations.insert(0, {
                    "type": "pie",
                    "confidence": 0.8,
                    "title": "占比饼图",
                    "description": "根据用户问题推荐的占比图",
                })

    return ChartRecommendResponse(
        recommended_types=recommendations,
        x_field=x_field,
        y_fields=y_fields,
    )


def _build_echarts_option(
    chart_type: str,
    columns: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    x_field: str = "",
    y_fields: list[str] | None = None,
    title: str = "",
) -> dict[str, Any]:
    """构建 ECharts 配置。

    Args:
        chart_type: 图表类型。
        columns: 列元数据列表。
        rows: 数据行列表。
        x_field: X 轴字段名。
        y_fields: Y 轴字段名列表。
        title: 图表标题。

    Returns:
        ECharts option 配置字典。
    """
    y_fields = y_fields or []
    x_data = [str(row.get(x_field, "")) for row in rows]

    # 构建 series
    series: list[dict[str, Any]] = []
    colors = ["#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de"]

    for idx, y_field in enumerate(y_fields):
        series.append({
            "name": y_field,
            "type": chart_type,
            "data": [row.get(y_field, 0) for row in rows],
            "itemStyle": {"color": colors[idx % len(colors)]},
        })

    # 饼图特殊处理
    if chart_type == "pie":
        pie_data: list[dict[str, Any]] = []
        for row in rows:
            pie_data.append({
                "name": str(row.get(x_field, "")),
                "value": row.get(y_fields[0], 0) if y_fields else 0,
            })
        return {
            "title": {"text": title, "left": "center"},
            "tooltip": {"trigger": "item", "formatter": "{a} <br/>{b}: {c} ({d}%)"},
            "legend": {"orient": "vertical", "left": "left"},
            "series": [{
                "name": y_fields[0] if y_fields else "数值",
                "type": "pie",
                "radius": "50%",
                "data": pie_data,
            }],
        }

    option: dict[str, Any] = {
        "title": {"text": title},
        "tooltip": {"trigger": "axis"},
        "legend": {"data": y_fields},
        "xAxis": {"type": "category", "data": x_data},
        "yAxis": {"type": "value"},
        "series": series,
    }

    return option


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------


@router.post("/recommend", response_model=ChartRecommendResponse)
async def recommend_chart(request: ChartRecommendRequest) -> ChartRecommendResponse:
    """推荐图表类型。

    基于数据列特征和用户问题，推荐最适合的图表类型。

    Args:
        request: 图表推荐请求。

    Returns:
        图表推荐结果。
    """
    logger.info(
        "图表推荐请求",
        column_count=len(request.columns),
        row_count=len(request.rows),
        user_question=request.user_question[:50] if request.user_question else "",
    )

    result = _infer_chart_type(
        columns=request.columns,
        rows=request.rows,
        user_question=request.user_question,
    )

    logger.info(
        "图表推荐完成",
        recommended_count=len(result.recommended_types),
        top_type=result.recommended_types[0]["type"] if result.recommended_types else None,
    )
    return result


@router.post("/render", response_model=ChartRenderResponse)
async def render_chart(request: ChartRenderRequest) -> ChartRenderResponse:
    """渲染图表配置。

    根据图表类型和数据生成 ECharts 配置。

    Args:
        request: 图表渲染请求。

    Returns:
        ECharts 配置。
    """
    logger.info(
        "图表渲染请求",
        chart_type=request.chart_type,
        row_count=len(request.rows),
    )

    # 验证图表类型
    supported_types = {"bar", "line", "pie", "scatter", "area", "heatmap"}
    if request.chart_type not in supported_types:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图表类型: {request.chart_type}，支持: {', '.join(sorted(supported_types))}",
        )

    if not request.rows:
        raise HTTPException(status_code=400, detail="数据行不能为空")

    # 自动推断 x_field 和 y_fields（如果未提供）
    x_field = request.x_field
    y_fields = request.y_fields

    if not x_field and request.columns:
        x_field = request.columns[0].get("name", "")
    if not y_fields and len(request.columns) > 1:
        y_fields = [col.get("name", "") for col in request.columns[1:4]]

    # area 类型映射为 line + areaStyle
    actual_chart_type = request.chart_type
    if actual_chart_type == "area":
        actual_chart_type = "line"

    echarts_option = _build_echarts_option(
        chart_type=actual_chart_type,
        columns=request.columns,
        rows=request.rows,
        x_field=x_field,
        y_fields=y_fields,
        title=request.title,
    )

    # area 图表增加 areaStyle
    if request.chart_type == "area" and echarts_option.get("series"):
        for s in echarts_option["series"]:
            s["areaStyle"] = {}

    logger.info("图表渲染完成", chart_type=request.chart_type)
    return ChartRenderResponse(
        chart_type=request.chart_type,
        title=request.title,
        echarts_option=echarts_option,
    )
