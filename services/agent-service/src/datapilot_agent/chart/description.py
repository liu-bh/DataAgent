"""图表自然语言描述生成器。

提供图表标题和描述的生成能力，支持 LLM 增强和规则降级两种模式。
"""

from __future__ import annotations

from typing import Any

import structlog

from datapilot_agent.chart.prompts import (
    CHART_DESCRIPTION_PROMPT,
    CHART_TITLE_PROMPT,
)

logger = structlog.get_logger(__name__)

# 图表类型中文标签
_CHART_TYPE_LABELS: dict[str, str] = {
    "line": "折线图",
    "bar": "柱状图",
    "pie": "饼图",
    "scatter": "散点图",
    "table": "数据表格",
    "area": "面积图",
    "heatmap": "热力图",
}


class ChartDescriptionGenerator:
    """图表自然语言描述生成器。

    生成图表标题和描述，优先使用 LLM 生成更自然的表达，
    无 LLM 时自动降级为规则化生成。

    Args:
        llm_router: LLM 路由器实例，可选。
    """

    def __init__(self, llm_router: Any = None) -> None:
        self._llm_router = llm_router

    async def generate_title(
        self,
        chart_type: str,
        x_field: str,
        y_fields: list[str],
        data_summary: dict,
    ) -> str:
        """生成图表标题。

        Args:
            chart_type: 图表类型标识。
            x_field: X 轴字段名。
            y_fields: Y 轴字段名列表。
            data_summary: 数据摘要信息。

        Returns:
            图表标题文本。
        """
        if self._llm_router is not None:
            try:
                return await self._generate_llm_title(chart_type, x_field, y_fields, data_summary)
            except Exception:
                logger.warning(
                    "llm_title_generation_failed",
                    chart_type=chart_type,
                    error="降级为规则标题",
                )

        return self._generate_rule_based_title(chart_type, x_field, y_fields)

    async def generate_description(
        self,
        chart_type: str,
        x_field: str,
        y_fields: list[str],
        data_summary: dict,
        result_stats: dict,
    ) -> str:
        """生成图表描述。

        Args:
            chart_type: 图表类型标识。
            x_field: X 轴字段名。
            y_fields: Y 轴字段名列表。
            data_summary: 数据摘要信息。
            result_stats: 数据统计信息（如 max, min, avg 等）。

        Returns:
            图表描述文本。
        """
        if self._llm_router is not None:
            try:
                return await self._generate_llm_description(
                    chart_type, x_field, y_fields, data_summary, result_stats
                )
            except Exception:
                logger.warning(
                    "llm_description_generation_failed",
                    chart_type=chart_type,
                    error="降级为规则描述",
                )

        return self._generate_rule_based_description(chart_type, x_field, y_fields, result_stats)

    def _generate_rule_based_title(
        self,
        chart_type: str,
        x_field: str,
        y_fields: list[str],
    ) -> str:
        """无 LLM 时的规则化标题生成。

        根据图表类型和字段信息，生成简洁的中文标题。

        Args:
            chart_type: 图表类型标识。
            x_field: X 轴字段名。
            y_fields: Y 轴字段名列表。

        Returns:
            规则生成的标题文本。
        """
        type_label = _CHART_TYPE_LABELS.get(chart_type, chart_type)
        fields_str = "与".join(y_fields) if y_fields else "数据"

        if chart_type == "line":
            return f"{fields_str}随{x_field}变化趋势"
        elif chart_type == "bar":
            return f"各{x_field}的{fields_str}对比"
        elif chart_type == "pie":
            return f"{fields_str}按{x_field}占比分布"
        elif chart_type == "scatter":
            if len(y_fields) >= 2:
                return f"{y_fields[0]}与{y_fields[1]}相关性分析"
            return f"{x_field}与{fields_str}的分布"
        elif chart_type == "table":
            return f"{x_field}{fields_str}明细表"
        elif chart_type == "area":
            return f"{fields_str}随{x_field}的累计趋势"
        elif chart_type == "heatmap":
            return f"{x_field}多维交叉热力图"
        else:
            return f"{type_label}：{x_field}与{fields_str}"

    def _generate_rule_based_description(
        self,
        chart_type: str,
        x_field: str,
        y_fields: list[str],
        result_stats: dict,
    ) -> str:
        """无 LLM 时的规则化描述生成。

        根据图表类型、字段信息和统计数据，生成描述文本。

        Args:
            chart_type: 图表类型标识。
            x_field: X 轴字段名。
            y_fields: Y 轴字段名列表。
            result_stats: 数据统计信息。

        Returns:
            规则生成的描述文本。
        """
        fields_str = "、".join(y_fields) if y_fields else "数据"
        row_count = result_stats.get("count", 0)

        # 构建统计摘要片段
        stats_parts = self._build_stats_summary(y_fields, result_stats)

        if chart_type == "line":
            desc = f"展示{fields_str}随{x_field}的变化趋势"
        elif chart_type == "bar":
            desc = f"对比各{x_field}的{fields_str}差异"
        elif chart_type == "pie":
            desc = f"展示{fields_str}按{x_field}的占比分布"
        elif chart_type == "scatter":
            if len(y_fields) >= 2:
                desc = f"展示{y_fields[0]}与{y_fields[1]}的相关性"
            else:
                desc = f"展示{x_field}与{fields_str}的分布情况"
        elif chart_type == "table":
            desc = f"包含{fields_str}的明细数据"
        elif chart_type == "area":
            desc = f"展示{fields_str}随{x_field}的累计变化"
        elif chart_type == "heatmap":
            desc = "以热力图展示多维数据交叉分布"
        else:
            desc = f"展示{x_field}与{fields_str}的关系"

        # 附加统计信息
        if stats_parts:
            desc += f"，{stats_parts}"

        if row_count:
            desc += f"，共{row_count}条记录。"
        else:
            desc += "。"

        return desc

    def _build_stats_summary(
        self,
        y_fields: list[str],
        result_stats: dict,
    ) -> str:
        """构建统计摘要文本。

        从统计数据中提取关键信息，生成自然的摘要文本。

        Args:
            y_fields: Y 轴字段列表。
            result_stats: 统计信息字典。

        Returns:
            统计摘要文本。
        """
        if not y_fields or not result_stats:
            return ""

        parts: list[str] = []
        field_stats = result_stats.get("fields", {})

        for field_name in y_fields:
            stats = field_stats.get(field_name, {})
            if not stats:
                continue

            # 提取关键统计值
            max_val = stats.get("max")
            min_val = stats.get("min")
            avg_val = stats.get("avg")

            if max_val is not None and min_val is not None:
                if avg_val is not None:
                    part = f"{field_name}范围为{min_val}~{max_val}，平均{avg_val}"
                else:
                    part = f"{field_name}范围为{min_val}~{max_val}"
                parts.append(part)
            elif avg_val is not None:
                parts.append(f"{field_name}平均值为{avg_val}")

        return "；".join(parts)

    async def _generate_llm_title(
        self,
        chart_type: str,
        x_field: str,
        y_fields: list[str],
        data_summary: dict,
    ) -> str:
        """通过 LLM 生成图表标题。

        Args:
            chart_type: 图表类型。
            x_field: X 轴字段。
            y_fields: Y 轴字段列表。
            data_summary: 数据摘要。

        Returns:
            LLM 生成的标题。
        """
        from datapilot_llm.router import Scene

        prompt = CHART_TITLE_PROMPT.format(
            chart_type=_CHART_TYPE_LABELS.get(chart_type, chart_type),
            x_field=x_field,
            y_fields=", ".join(y_fields),
            data_summary=str(data_summary),
        )

        response = await self._llm_router.generate(
            Scene.EXPLANATION,
            prompt,
            temperature=0.5,
            max_tokens=256,
        )

        title = response.content.strip().strip('"').strip("'").strip()
        # 限制标题长度
        if len(title) > 30:
            title = title[:30] + "..."
        return title or self._generate_rule_based_title(chart_type, x_field, y_fields)

    async def _generate_llm_description(
        self,
        chart_type: str,
        x_field: str,
        y_fields: list[str],
        data_summary: dict,
        result_stats: dict,
    ) -> str:
        """通过 LLM 生成图表描述。

        Args:
            chart_type: 图表类型。
            x_field: X 轴字段。
            y_fields: Y 轴字段列表。
            data_summary: 数据摘要。
            result_stats: 统计信息。

        Returns:
            LLM 生成的描述。
        """
        from datapilot_llm.router import Scene

        prompt = CHART_DESCRIPTION_PROMPT.format(
            chart_type=_CHART_TYPE_LABELS.get(chart_type, chart_type),
            x_field=x_field,
            y_fields=", ".join(y_fields),
            data_summary=str(data_summary),
            result_stats=str(result_stats),
        )

        response = await self._llm_router.generate(
            Scene.EXPLANATION,
            prompt,
            temperature=0.5,
            max_tokens=512,
        )

        desc = response.content.strip().strip('"').strip("'").strip()
        # 限制描述长度
        if len(desc) > 200:
            desc = desc[:200] + "..."
        return desc or self._generate_rule_based_description(
            chart_type, x_field, y_fields, result_stats
        )
