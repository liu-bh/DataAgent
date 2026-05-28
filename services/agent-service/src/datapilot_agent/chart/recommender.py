"""LLM 智能图表推荐器。

基于数据列特征和用户问题，自动推荐最适合的图表类型。
采用规则优先 + LLM 优化的两阶段策略：
1. 规则推断（无 LLM 依赖，快速响应）
2. 有 LLM 时，结合用户意图优化推荐结果
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

from datapilot_agent.chart.prompts import CHART_RECOMMEND_PROMPT

if TYPE_CHECKING:
    from datapilot_chart.models import ChartSpec, ChartType
    from datapilot_chart.type_infer import ChartTypeInferrer

logger = structlog.get_logger(__name__)

# 用户问题中的图表关键词映射
_QUESTION_CHART_HINTS: dict[str, list[str]] = {
    "line": ["趋势", "变化", "走势", "增长", "下降", "波动", "随时间", "趋势线"],
    "bar": ["对比", "比较", "排名", "排行", "各", "不同", "分别", "分组", "Top"],
    "pie": ["占比", "比例", "构成", "组成", "分布", "百分比", "份额", "占比"],
    "scatter": ["相关", "关系", "关联", "分布", "散点", "相关性"],
    "table": ["明细", "详细", "列表", "记录", "清单", "所有"],
    "area": ["累计", "面积", "总量", "堆叠"],
}

# 时间列名常见模式
_TIME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)^(date|time|datetime|timestamp|year|month|day|week|quarter)$"),
    re.compile(r"(?i)_(date|time|at|on)$"),
    re.compile(r"(?i)^(created|updated|modified|start|end)"),
]


@dataclass
class ChartRecommendation:
    """图表推荐结果。

    Attributes:
        chart_types: 推荐的图表类型列表，按置信度降序排列。
            每个元素为 (类型名称, 置信度) 元组。
        title: 推荐的图表标题。
        description: 图表的自然语言描述。
        x_field: 推荐的 X 轴字段名。
        y_fields: 推荐的 Y 轴字段名列表。
        suggested_config: 可选的图表配置建议。
    """

    chart_types: list[tuple[str, float]]
    title: str
    description: str
    x_field: str
    y_fields: list[str]
    suggested_config: dict | None = None


class ChartRecommender:
    """智能图表推荐器。

    通过分析数据列特征（类型、名称）和用户问题，
    自动推荐最适合的图表类型和轴字段映射。

    策略:
    1. 规则推断（无 LLM 依赖）
    2. 有 LLM 时，结合用户意图优化
    3. 自动选择 x/y 轴字段

    Args:
        llm_router: LLM 路由器实例，可选。传入时启用 LLM 优化推荐。
    """

    def __init__(self, llm_router: Any = None) -> None:
        self._llm_router = llm_router
        self._inferrer: Any | None = None

    async def recommend(
        self,
        columns: list[dict],
        rows: list[dict],
        user_question: str = "",
    ) -> ChartRecommendation:
        """推荐图表类型。

        策略:
        1. 规则推断（无 LLM）
        2. 有 LLM 时，结合用户意图优化
        3. 自动选择 x/y 轴字段

        Args:
            columns: 列信息列表，每个元素为包含 name 和 type 的字典。
            rows: 数据行列表，每个元素为列名到值的映射。
            user_question: 用户自然语言问题，可选。

        Returns:
            ChartRecommendation 推荐结果。
        """
        # 阶段 1：基于规则的图表推断
        rule_results = self._infer_by_rules(columns, rows, user_question)

        # 阶段 2：LLM 优化（可选）
        if self._llm_router is not None:
            try:
                llm_results = await self._infer_by_llm(columns, rows, user_question)
                if llm_results:
                    rule_results = self._merge_results(rule_results, llm_results)
            except Exception:
                logger.warning(
                    "llm_chart_recommend_failed",
                    error="LLM 推荐失败，降级为纯规则推荐",
                )

        # 自动检测字段映射
        x_field, y_fields = self._detect_fields(columns, rows)

        # 生成默认标题和描述
        top_chart = rule_results[0][0] if rule_results else "table"
        title = f"{x_field} 与 {'/'.join(y_fields)} 的{self._chart_type_label(top_chart)}"
        description = self._default_description(top_chart, x_field, y_fields, rows)

        return ChartRecommendation(
            chart_types=rule_results,
            title=title,
            description=description,
            x_field=x_field,
            y_fields=y_fields,
        )

    def _infer_by_rules(
        self,
        columns: list[dict],
        rows: list[dict],
        question: str,
    ) -> list[tuple[str, float]]:
        """基于规则的图表推断。

        分析列的数据类型和名称特征，推断适合的图表类型。
        同时考虑用户问题中的关键词来提升推荐准确性。

        Args:
            columns: 列信息列表。
            rows: 数据行列表。
            question: 用户问题。

        Returns:
            按置信度降序排列的 [(图表类型, 置信度)] 列表。
        """
        scores: dict[str, float] = {
            "line": 0.0,
            "bar": 0.0,
            "pie": 0.0,
            "scatter": 0.0,
            "table": 0.0,
            "area": 0.0,
            "heatmap": 0.0,
        }

        # 分类列和数值列
        text_cols: list[str] = []
        numeric_cols: list[str] = []
        time_cols: list[str] = []
        has_time = False
        unique_counts: dict[str, int] = {}

        for col in columns:
            col_name = col.get("name", "")
            col_type = col.get("type", "").lower()

            # 检测时间列
            if self._is_time_column(col_name, col_type):
                time_cols.append(col_name)
                has_time = True
            elif "int" in col_type or "float" in col_type or "number" in col_type or "decimal" in col_type:
                numeric_cols.append(col_name)
            elif "bool" in col_type:
                # 布尔列归为文本分类
                text_cols.append(col_name)
            else:
                text_cols.append(col_name)

            # 计算唯一值数量
            if rows:
                values = set(row.get(col_name) for row in rows if row.get(col_name) is not None)
                unique_counts[col_name] = len(values)

        # --- 规则评分 ---

        # 时间列 + 数值列 -> 折线图 / 面积图
        if has_time and numeric_cols:
            scores["line"] += 0.8
            scores["area"] += 0.4

        # 分类列 + 数值列 -> 柱状图
        if text_cols and numeric_cols:
            scores["bar"] += 0.7

        # 少量分类（<=6） + 数值列 -> 饼图
        category_col = text_cols[0] if text_cols else None
        if category_col and unique_counts.get(category_col, 0) <= 6 and numeric_cols:
            scores["pie"] += 0.6

        # 两个以上数值列 -> 散点图
        if len(numeric_cols) >= 2:
            scores["scatter"] += 0.5

        # 行数少或列数多 -> 表格
        if len(rows) <= 10 or len(columns) > 6:
            scores["table"] += 0.3

        # 只有文本列 -> 表格
        if text_cols and not numeric_cols:
            scores["table"] += 0.8

        # --- 用户问题关键词加成 ---
        question_lower = question.lower() if question else ""
        for chart_type, keywords in _QUESTION_CHART_HINTS.items():
            for keyword in keywords:
                if keyword.lower() in question_lower:
                    scores[chart_type] += 0.3

        # 排序并归一化
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # 过滤掉零分项
        filtered = [(t, s) for t, s in sorted_results if s > 0]

        # 如果全部为零分，默认推荐表格
        if not filtered:
            filtered = [("table", 1.0)]

        # 归一化置信度
        total = sum(s for _, s in filtered)
        if total > 0:
            filtered = [(t, round(s / total, 2)) for t, s in filtered]

        return filtered

    def _detect_fields(
        self,
        columns: list[dict],
        rows: list[dict],
    ) -> tuple[str, list[str]]:
        """自动检测 x/y 轴字段。

        根据列的数据类型和名称特征，自动选择合适的 X 轴和 Y 轴字段。

        策略:
        - X 轴: 优先选择时间列，其次选择分类列（唯一值少的文本列）
        - Y 轴: 选择数值列

        Args:
            columns: 列信息列表。
            rows: 数据行列表。

        Returns:
            (x_field, y_fields) 元组。
        """
        time_cols: list[str] = []
        text_cols: list[str] = []
        numeric_cols: list[str] = []

        for col in columns:
            col_name = col.get("name", "")
            col_type = col.get("type", "").lower()

            if self._is_time_column(col_name, col_type):
                time_cols.append(col_name)
            elif "int" in col_type or "float" in col_type or "number" in col_type or "decimal" in col_type:
                numeric_cols.append(col_name)
            else:
                text_cols.append(col_name)

        # X 轴：优先时间列，其次分类列（按唯一值数量排序，少的优先）
        x_field = ""
        if time_cols:
            x_field = time_cols[0]
        elif text_cols:
            # 选择唯一值最少的文本列作为分类轴
            if rows:
                col_unique: dict[str, int] = {}
                for col_name in text_cols:
                    values = set(row.get(col_name) for row in rows if row.get(col_name) is not None)
                    col_unique[col_name] = len(values)
                x_field = min(text_cols, key=lambda c: col_unique.get(c, 0))
            else:
                x_field = text_cols[0]
        elif numeric_cols:
            x_field = numeric_cols[0]

        # Y 轴：选择数值列（排除 X 轴已使用的）
        y_fields = [c for c in numeric_cols if c != x_field]

        return x_field, y_fields

    async def _infer_by_llm(
        self,
        columns: list[dict],
        rows: list[dict],
        question: str,
    ) -> list[tuple[str, float]]:
        """通过 LLM 推荐图表类型。

        将数据摘要和用户问题发送给 LLM，获取图表推荐。

        Args:
            columns: 列信息列表。
            rows: 数据行列表。
            question: 用户问题。

        Returns:
            [(图表类型, 置信度)] 列表，失败时返回空列表。
        """
        from datapilot_llm.router import Scene

        # 构建数据摘要
        columns_desc = json.dumps(columns, ensure_ascii=False)
        row_count = len(rows)

        prompt = CHART_RECOMMEND_PROMPT.format(
            columns=columns_desc,
            row_count=row_count,
            question=question or "无",
        )

        response = await self._llm_router.generate(
            Scene.EXPLANATION,
            prompt,
            temperature=0.3,
            max_tokens=512,
            json_mode=True,
        )

        return self._parse_llm_response(response.content)

    def _parse_llm_response(self, content: str) -> list[tuple[str, float]]:
        """解析 LLM 返回的图表推荐结果。

        Args:
            content: LLM 返回的 JSON 字符串。

        Returns:
            [(图表类型, 置信度)] 列表。
        """
        try:
            # 尝试直接解析
            results = json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取 JSON 数组
            match = re.search(r"\[.*\]", content, re.DOTALL)
            if match:
                try:
                    results = json.loads(match.group())
                except json.JSONDecodeError:
                    logger.warning("llm_chart_response_parse_failed", content=content[:200])
                    return []
            else:
                logger.warning("llm_chart_response_no_json", content=content[:200])
                return []

        if not isinstance(results, list):
            return []

        parsed: list[tuple[str, float]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            chart_type = item.get("type", "")
            confidence = item.get("confidence", 0.0)
            if isinstance(confidence, (int, float)) and chart_type:
                parsed.append((str(chart_type), float(confidence)))

        # 按置信度降序
        parsed.sort(key=lambda x: x[1], reverse=True)
        return parsed

    def _merge_results(
        self,
        rule_results: list[tuple[str, float]],
        llm_results: list[tuple[str, float]],
    ) -> list[tuple[str, float]]:
        """合并规则推断和 LLM 推荐结果。

        对 LLM 结果中的图表类型进行加权提升（+0.2），保留规则推断的基础分数。

        Args:
            rule_results: 规则推断结果。
            llm_results: LLM 推荐结果。

        Returns:
            合并后的推荐结果。
        """
        merged: dict[str, float] = {}

        # 以规则结果为基础
        for chart_type, score in rule_results:
            merged[chart_type] = score

        # LLM 结果加权合并
        for chart_type, score in llm_results:
            if chart_type in merged:
                merged[chart_type] = merged[chart_type] * 0.7 + score * 0.3
            else:
                # 新增 LLM 发现的图表类型
                merged[chart_type] = score * 0.5

        # 排序并归一化
        sorted_results = sorted(merged.items(), key=lambda x: x[1], reverse=True)
        total = sum(s for _, s in sorted_results)
        if total > 0:
            sorted_results = [(t, round(s / total, 2)) for t, s in sorted_results]

        return sorted_results

    @staticmethod
    def _is_time_column(col_name: str, col_type: str) -> bool:
        """判断列是否为时间类型。

        Args:
            col_name: 列名。
            col_type: 列类型。

        Returns:
            是否为时间类型列。
        """
        # 类型名判断
        time_types = {"date", "datetime", "timestamp", "time"}
        if col_type.lower() in time_types:
            return True

        # 列名模式判断
        for pattern in _TIME_PATTERNS:
            if pattern.match(col_name):
                return True

        return False

    @staticmethod
    def _chart_type_label(chart_type: str) -> str:
        """获取图表类型的中文标签。

        Args:
            chart_type: 图表类型标识。

        Returns:
            中文标签。
        """
        labels = {
            "line": "趋势图",
            "bar": "对比图",
            "pie": "占比图",
            "scatter": "散点图",
            "table": "数据表格",
            "area": "面积图",
            "heatmap": "热力图",
        }
        return labels.get(chart_type, chart_type)

    def _default_description(
        self,
        chart_type: str,
        x_field: str,
        y_fields: list[str],
        rows: list[dict],
    ) -> str:
        """生成默认的图表描述。

        Args:
            chart_type: 图表类型。
            x_field: X 轴字段。
            y_fields: Y 轴字段列表。
            rows: 数据行列表。

        Returns:
            描述文本。
        """
        row_count = len(rows)
        fields_str = "、".join(y_fields) if y_fields else "数据"

        if chart_type == "line":
            return f"展示 {fields_str} 随 {x_field} 的变化趋势，共 {row_count} 条记录。"
        elif chart_type == "bar":
            return f"对比各 {x_field} 的 {fields_str} 差异，共 {row_count} 条记录。"
        elif chart_type == "pie":
            return f"展示各 {x_field} 在 {fields_str} 中的占比分布，共 {row_count} 条记录。"
        elif chart_type == "scatter":
            if len(y_fields) >= 2:
                return f"展示 {y_fields[0]} 与 {y_fields[1]} 之间的相关性分布，共 {row_count} 条记录。"
            return f"展示数据的分布情况，共 {row_count} 条记录。"
        elif chart_type == "table":
            return f"包含 {row_count} 条明细记录，展示 {x_field} 与 {fields_str} 的详细数据。"
        elif chart_type == "area":
            return f"展示 {fields_str} 随 {x_field} 的累计趋势，共 {row_count} 条记录。"
        elif chart_type == "heatmap":
            return f"以热力图形式展示多维数据交叉分析，共 {row_count} 条记录。"
        else:
            return f"共 {row_count} 条数据记录。"

    async def generate_description(
        self,
        spec_data: dict,
        data_summary: dict,
    ) -> str:
        """生成图表的自然语言描述。

        Args:
            spec_data: 图表规范数据，包含 chart_type, x_field, y_fields 等。
            data_summary: 数据摘要，包含 row_count, statistics 等。

        Returns:
            自然语言描述。
        """
        chart_type = spec_data.get("chart_type", "table")
        x_field = spec_data.get("x_field", "")
        y_fields = spec_data.get("y_fields", [])

        # 如果有 LLM，使用 LLM 生成
        if self._llm_router is not None:
            try:
                from datapilot_agent.chart.description import ChartDescriptionGenerator

                generator = ChartDescriptionGenerator(self._llm_router)
                return await generator.generate_description(
                    chart_type=chart_type,
                    x_field=x_field,
                    y_fields=y_fields,
                    data_summary=data_summary,
                    result_stats=data_summary.get("statistics", {}),
                )
            except Exception:
                logger.warning("llm_description_failed", error="降级为规则描述")

        # 降级为规则生成
        result_stats = data_summary.get("statistics", {})
        from datapilot_agent.chart.description import ChartDescriptionGenerator

        generator = ChartDescriptionGenerator()
        return generator._generate_rule_based_description(
            chart_type, x_field, y_fields, result_stats
        )
