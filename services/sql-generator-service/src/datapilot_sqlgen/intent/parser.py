"""Intent Parser 模块。

从用户自然语言中提取结构化查询信息（查询类型、指标、维度、时间范围、
过滤条件、排序、LIMIT），使用 LLM JSON mode 确保结构化输出。
解析失败时使用安全的默认值。
"""

from __future__ import annotations

import contextlib
import json
import re
from datetime import date
from typing import Any

import structlog

from datapilot_sqlgen.intent.types import (
    FilterCondition,
    ParsedIntent,
    QueryType,
    SortDirection,
    SortSpec,
    TimeRange,
)

logger = structlog.get_logger(__name__)

# ============================================================
# Intent Parser Prompt 模板
# ============================================================

_INTENT_PARSE_PROMPT: str = """你是一个 NL2SQL 意图解析助手。从用户问题中提取结构化查询信息，只返回 JSON。

## 提取要求

### query_type（查询类型）
- aggregation: 聚合查询（总计、平均、汇总）
- detail: 明细查询（逐行展示）
- ranking: 排名查询（Top N / Bottom N）
- comparison: 对比查询（同比、环比、分组对比）
- trend: 趋势查询（时序变化）

### target_metrics（目标指标）
从问题中提取用户关心的指标名称，如 GMV、销售额、订单量、客单价。

### target_dimensions（目标维度）
从问题中提取用户关心的维度，如 地区、时间、商品类目。

### time_range（时间范围）
- start: ISO 格式日期或 null（如 "2026-04-01"）
- end: ISO 格式日期或 null
- raw_text: 原始时间描述
- granularity: day/week/month/quarter/year

### filters（过滤条件）
提取业务过滤条件，每个条件包含 column, operator, value, raw_text。
operator 支持: =, !=, >, <, >=, <=, IN, LIKE, BETWEEN。

### sort_by（排序）
提取排序要求，每个包含 column, direction (ASC/DESC)。

### limit（行数限制）
用户显式指定的行数，如 "前10" 则 limit=10，未指定则 null。

## 用户问题
{question}

{context_section}

请返回 JSON（不要包含其他文字）:
{{
    "query_type": "aggregation",
    "target_metrics": [],
    "target_dimensions": [],
    "time_range": {{"start": null, "end": null, "raw_text": "", "granularity": "day"}},
    "filters": [],
    "sort_by": [],
    "limit": null
}}"""


class IntentParser:
    """意图解析器。

    从用户自然语言问题中提取结构化查询信息，
    使用 LLM JSON mode 确保输出格式正确。
    解析失败时返回安全的默认值。

    Usage::

        parser = IntentParser()
        result = parser.parse("上个月华东区销售额排名前10")
    """

    def __init__(self, *, enable_llm: bool = True) -> None:
        """初始化意图解析器。

        Args:
            enable_llm: 是否启用 LLM 解析。默认 True。
        """
        self._enable_llm = enable_llm
        logger.info("IntentParser 初始化", enable_llm=enable_llm)

    # ---- 公开接口 ----

    def parse(
        self,
        question: str,
        context: list[dict[str, Any]] | None = None,
    ) -> ParsedIntent:
        """解析用户自然语言问题为结构化意图。

        Args:
            question: 用户自然语言问题。
            context: 上下文消息列表（多轮对话历史），
                     每项为 {"role": "user"|"assistant", "content": "..."}。

        Returns:
            ParsedIntent 结构化意图解析结果。
        """
        if not question or not question.strip():
            return ParsedIntent(raw_question="")

        raw_question = question.strip()

        if not self._enable_llm:
            # LLM 未启用时使用规则解析
            return self._parse_by_rules(raw_question)

        # LLM 解析
        llm_result = self._parse_by_llm(raw_question, context)
        if llm_result is not None:
            logger.info(
                "LLM 意图解析成功",
                query_type=llm_result.query_type.value,
                metrics=llm_result.target_metrics,
                dimensions=llm_result.target_dimensions,
            )
            return llm_result

        # LLM 失败时回退到规则解析
        logger.warning("LLM 意图解析失败，回退到规则解析")
        return self._parse_by_rules(raw_question)

    # ---- LLM 解析 ----

    def _parse_by_llm(
        self,
        question: str,
        context: list[dict[str, Any]] | None = None,
    ) -> ParsedIntent | None:
        """调用 LLM 解析意图。

        Returns:
            解析结果，失败时返回 None。
        """
        try:
            # 占位导入，Track A 负责实现
            from datapilot_llm import LLMRouter  # noqa: F401

            # 构建上下文段落
            context_section = ""
            if context:
                recent = context[-3:]  # 最多取最近 3 轮
                ctx_lines = []
                for msg in recent:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    ctx_lines.append(f"- {role}: {content}")
                context_section = "## 对话上下文\n" + "\n".join(ctx_lines)

            _ = _INTENT_PARSE_PROMPT.format(
                question=question,
                context_section=context_section,
            )

            # TODO: 通过 LLMRouter 调用 LLM（JSON mode）
            # response = LLMRouter.call(
            #     prompt=prompt,
            #     scene="intent",
            #     response_format="json",
            # )
            # parsed = json.loads(response)
            # return self._build_parsed_intent(parsed, question)

            logger.warning("LLM 意图解析尚未实现", question=question[:50])
            return None

        except ImportError:
            logger.debug("datapilot_llm 未安装，跳过 LLM 意图解析")
            return None
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("LLM 意图解析响应解析失败", error=str(e))
            return None

    # ---- 规则解析（LLM 失败时的回退方案） ----

    def _parse_by_rules(self, question: str) -> ParsedIntent:
        """使用规则从问题中提取结构化信息。

        作为 LLM 解析失败时的轻量级回退方案。

        Args:
            question: 用户问题。

        Returns:
            ParsedIntent 基本解析结果。
        """
        # 解析查询类型
        query_type = self._detect_query_type(question)

        # 解析时间范围
        time_range = self._parse_time_range(question)

        # 解析 LIMIT
        limit = self._parse_limit(question)

        # 解析排序
        sort_by = self._parse_sort(question)

        # 解析过滤条件（规则模式仅做简单提取）
        filters = self._parse_filters(question)

        # 提取可能的指标关键词
        target_metrics = self._extract_metric_keywords(question)

        # 提取可能的维度关键词
        target_dimensions = self._extract_dimension_keywords(question)

        return ParsedIntent(
            query_type=query_type,
            target_metrics=target_metrics,
            target_dimensions=target_dimensions,
            time_range=time_range,
            filters=filters,
            sort_by=sort_by,
            limit=limit,
            raw_question=question,
        )

    def _detect_query_type(self, question: str) -> QueryType:
        """根据关键词检测查询类型。"""
        lower_q = question.lower()

        # 趋势关键词
        trend_kw = ["趋势", "变化", "走势", "增长", "下降"]
        if any(kw in lower_q for kw in trend_kw):
            return QueryType.TREND

        # 对比关键词
        comparison_kw = ["对比", "同比", "环比", "比较", "vs", "versus"]
        if any(kw in lower_q for kw in comparison_kw):
            return QueryType.COMPARISON

        # 排名关键词
        ranking_kw = ["排名", "排行", "top", "前", "最高", "最低", "best", "worst"]
        if any(kw in lower_q for kw in ranking_kw):
            return QueryType.RANKING

        # 聚合关键词
        agg_kw = ["总计", "合计", "汇总", "平均", "总量", "总共", "统计", "sum", "avg", "count"]
        if any(kw in lower_q for kw in agg_kw):
            return QueryType.AGGREGATION

        return QueryType.DETAIL

    def _parse_time_range(self, question: str) -> TimeRange:
        """从问题中解析时间范围。"""
        today = date.today()

        # 今天
        if "今天" in question or "今日" in question:
            return TimeRange(
                start=today, end=today, raw_text="今天", granularity="day"
            )

        # 昨天
        if "昨天" in question or "昨日" in question:
            yesterday = today.replace(day=today.day - 1) if today.day > 1 else today
            return TimeRange(
                start=yesterday, end=yesterday, raw_text="昨天", granularity="day"
            )

        # 本月
        if "本月" in question or "这个月" in question:
            return TimeRange(
                start=date(today.year, today.month, 1),
                end=today,
                raw_text="本月",
                granularity="day",
            )

        # 上月
        if "上月" in question or "上个月" in question:
            if today.month == 1:
                start = date(today.year - 1, 12, 1)
                end = date(today.year - 1, 12, 31)
            else:
                start = date(today.year, today.month - 1, 1)
                end = date(today.year, today.month, 1)  # 不含当月
            return TimeRange(
                start=start, end=end, raw_text="上月", granularity="month"
            )

        # 季度解析（需在"今年"/"去年"检查之前）
        q_match = re.search(r"(今年|本年|去年)?[Qq]([1-4])", question)
        if q_match:
            year_prefix = q_match.group(1) or "今年"
            q_num = int(q_match.group(2))
            year = today.year if "去年" not in year_prefix else today.year - 1
            q_start_month = (q_num - 1) * 3 + 1
            q_end_month = q_num * 3
            start = date(year, q_start_month, 1)
            # 计算季度末最后一天
            end = date(year, 12, 31) if q_end_month == 12 else date(year, q_end_month + 1, 1)
            raw = f"{year}Q{q_num}"
            return TimeRange(
                start=start, end=end, raw_text=raw, granularity="quarter"
            )

        # 今年
        if "今年" in question or "本年" in question:
            return TimeRange(
                start=date(today.year, 1, 1),
                end=today,
                raw_text="今年",
                granularity="month",
            )

        # 去年
        if "去年" in question:
            return TimeRange(
                start=date(today.year - 1, 1, 1),
                end=date(today.year - 1, 12, 31),
                raw_text="去年",
                granularity="month",
            )

        # 最近 N 天
        match = re.search(r"最近(\d+)天", question)
        if match:
            days = int(match.group(1))
            start = today.replace(day=today.day - days) if today.day > days else date(
                today.year, today.month - 1, today.day
            )
            return TimeRange(
                start=start, end=today, raw_text=f"最近{days}天", granularity="day"
            )

        return TimeRange()

    def _parse_limit(self, question: str) -> int:
        """从问题中解析 LIMIT 值。"""
        # "前 N" / "top N" / "N 条"
        patterns = [
            r"前\s*(\d+)",
            r"[Tt][Oo][Pp]\s*(\d+)",
            r"(\d+)\s*条",
        ]
        for pattern in patterns:
            match = re.search(pattern, question)
            if match:
                try:
                    return max(1, min(int(match.group(1)), 10000))
                except ValueError:
                    pass

        return 100  # 默认值

    def _parse_sort(self, question: str) -> list[SortSpec]:
        """从问题中解析排序需求。"""
        result: list[SortSpec] = []

        # 降序关键词
        desc_kw = ["从高到低", "从大到小", "降序", "最高", "最多"]
        for kw in desc_kw:
            if kw in question:
                result.append(SortSpec(column="", direction=SortDirection.DESC))
                break

        # 升序关键词
        asc_kw = ["从低到高", "从小到大", "升序", "最低", "最少"]
        for kw in asc_kw:
            if kw in question:
                result.append(SortSpec(column="", direction=SortDirection.ASC))
                break

        return result

    def _parse_filters(self, question: str) -> list[FilterCondition]:
        """从问题中提取简单过滤条件。"""
        filters: list[FilterCondition] = []

        # 地区类过滤
        region_kw = ["华东", "华南", "华北", "华中", "西南", "西北", "东北"]
        for region in region_kw:
            if region in question:
                filters.append(
                    FilterCondition(
                        column="region",
                        operator="=",
                        value=region,
                        raw_text=region,
                    )
                )
                break

        # 金额比较
        amount_match = re.search(r"金额(?:大于|[>＞])(\d+)", question)
        if amount_match:
            filters.append(
                FilterCondition(
                    column="amount",
                    operator=">",
                    value=float(amount_match.group(1)),
                    raw_text=amount_match.group(0),
                )
            )

        amount_match_lt = re.search(r"金额(?:小于|[<＜])(\d+)", question)
        if amount_match_lt:
            filters.append(
                FilterCondition(
                    column="amount",
                    operator="<",
                    value=float(amount_match_lt.group(1)),
                    raw_text=amount_match_lt.group(0),
                )
            )

        return filters

    def _extract_metric_keywords(self, question: str) -> list[str]:
        """从问题中提取可能的指标关键词。"""
        metrics: list[str] = []
        known_metrics = [
            "销售额", "GMV", "gmv", "订单量", "客单价", "转化率", "利润",
            "营收", "收入", "成本", "毛利", "净利", "退货率", "复购率",
            "活跃用户", "新增用户", "留存率", "DAU", "MAU",
        ]
        for m in known_metrics:
            if m.lower() in question.lower() and m not in metrics:
                metrics.append(m)
        return metrics

    def _extract_dimension_keywords(self, question: str) -> list[str]:
        """从问题中提取可能的维度关键词。"""
        dimensions: list[str] = []
        known_dims = [
            "地区", "区域", "省份", "城市", "时间", "日期", "月份", "季度", "年份",
            "商品", "类目", "品类", "品牌", "渠道", "用户", "性别", "年龄",
        ]
        for d in known_dims:
            if d in question and d not in dimensions:
                dimensions.append(d)

        # 额外提取 "X区" 模式为地区维度（如"华东区"、"华南区"）
        region_match = re.search(r"((?:华[东南北]|西[南北]|中[南西北]|[自海]?内[蒙古]?|[云贵川陕甘青]肃?)\s*区)", question)
        if region_match and "地区" not in dimensions:
            dimensions.append("地区")

        return dimensions

    # ---- LLM 结果构建 ----

    def _build_parsed_intent(
        self, raw: dict[str, Any], question: str
    ) -> ParsedIntent:
        """从 LLM JSON 响应构建 ParsedIntent。

        Args:
            raw: LLM 返回的 JSON 字典。
            question: 原始问题。

        Returns:
            ParsedIntent 结构化结果。
        """
        # 解析查询类型
        query_type = QueryType.DETAIL
        with contextlib.suppress(ValueError):
            query_type = QueryType(raw.get("query_type", "detail"))

        # 解析时间范围
        tr_raw = raw.get("time_range", {})
        time_range = TimeRange(
            start=self._parse_date_safe(tr_raw.get("start")),
            end=self._parse_date_safe(tr_raw.get("end")),
            raw_text=tr_raw.get("raw_text", ""),
            granularity=tr_raw.get("granularity", "day"),
        )

        # 解析过滤条件
        filters: list[FilterCondition] = []
        for f in raw.get("filters", []):
            filters.append(
                FilterCondition(
                    column=f.get("column", ""),
                    operator=f.get("operator", "="),
                    value=f.get("value"),
                    raw_text=f.get("raw_text", ""),
                )
            )

        # 解析排序
        sort_by: list[SortSpec] = []
        for s in raw.get("sort_by", []):
            direction = SortDirection.ASC
            with contextlib.suppress(ValueError):
                direction = SortDirection(s.get("direction", "ASC"))
            sort_by.append(SortSpec(column=s.get("column", ""), direction=direction))

        # 解析 LIMIT
        limit = 100
        raw_limit = raw.get("limit")
        if raw_limit is not None:
            with contextlib.suppress(ValueError, TypeError):
                limit = max(1, min(int(raw_limit), 10000))

        return ParsedIntent(
            query_type=query_type,
            target_metrics=raw.get("target_metrics", []),
            target_dimensions=raw.get("target_dimensions", []),
            time_range=time_range,
            filters=filters,
            sort_by=sort_by,
            limit=limit,
            raw_question=question,
        )

    @staticmethod
    def _parse_date_safe(value: Any) -> date | None:
        """安全解析日期字符串。"""
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except (ValueError, TypeError):
                pass
        return None
