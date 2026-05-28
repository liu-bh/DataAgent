"""意图路由模块。

对用户输入进行快速意图分类，分流到不同的处理通道。
优先使用规则匹配（关键词），规则不确定时调用 LLM 进行结构化分类。
支持常见意图分类结果的内存缓存。
"""

from __future__ import annotations

import json
import re

import structlog

from datapilot_sqlgen.intent.types import IntentResult, IntentType

logger = structlog.get_logger(__name__)

# ============================================================
# 关键词规则定义
# ============================================================

# 数据查询关键词——命中则判定为 SQL_QUERY
_SQL_QUERY_KEYWORDS: list[str] = [
    "多少",
    "统计",
    "排名",
    "趋势",
    "对比",
    "环比",
    "同比",
    "总计",
    "合计",
    "汇总",
    "平均",
    "最大",
    "最小",
    "最高",
    "最低",
    "前几",
    "top",
    "排序",
    "占比",
    "分布",
    "增长率",
    "增速",
    "累计",
    "数量",
    "金额",
    "销售额",
    "GMV",
    "客单价",
    "转化率",
    "订单量",
    "用户数",
    "明细",
    "列表",
    "查询",
    "查一下",
    "看看",
    "哪些",
    "哪个",
    "什么时候",
    "哪天",
    "哪个季度",
]

# 闲聊关键词——命中则判定为 CHITCHAT
_CHITCHAT_KEYWORDS: list[str] = [
    "你好",
    "您好",
    "嗨",
    "早上好",
    "下午好",
    "晚上好",
    "谢谢",
    "感谢",
    "再见",
    "拜拜",
    "好的",
    "嗯嗯",
    "收到",
]

# 超出范围关键词——命中则判定为 OUT_OF_SCOPE
_OUT_OF_SCOPE_KEYWORDS: list[str] = [
    "天气",
    "新闻",
    "股票",
    "基金",
    "汇率",
    "彩票",
    "游戏",
    "电影",
    "音乐",
    "菜谱",
    "翻译",
    "算数",
    "计算",
    "写代码",
    "编程",
]

# 转人工关键词——命中则判定为 ESCALATE_TO_HUMAN
_ESCALATE_KEYWORDS: list[str] = [
    "转人工",
    "人工客服",
    "找人工",
    "找客服",
    "投诉",
    "举报",
    "紧急",
]


# ============================================================
# 意图识别 Prompt 模板（JSON mode）
# ============================================================

_INTENT_CLASSIFY_PROMPT: str = """你是一个意图识别助手。判断用户的查询意图，只返回 JSON。

## 意图类型
- sql_query: 用户要查询数据，可以转换为 SQL
- chitchat: 闲聊、打招呼
- out_of_scope: 超出系统范围的问题
- escalate_to_human: 无法处理，需要人工介入

## 判断规则
1. 包含数据查询关键词（"多少"、"统计"、"排名"、"趋势"）→ sql_query
2. 问候语、无关话题 → chitchat
3. 涉及系统外知识（如"天气怎样"）→ out_of_scope
4. 用户明确要求人工服务 → escalate_to_human

## 用户问题
{question}

请返回 JSON: {{"intent": "sql_query", "confidence": 0.95, "reason": "包含数据查询关键词", "entities": []}}"""


class IntentRouter:
    """意图路由器。

    对用户输入进行意图分类，优先使用规则快速匹配，
    规则无法确定时回退到 LLM 分类。

    Usage::

        router = IntentRouter()
        result = router.classify("上个月销售额是多少？")
        # result.intent_type == IntentType.SQL_QUERY
    """

    def __init__(self, *, enable_llm: bool = True, enable_cache: bool = True) -> None:
        """初始化意图路由器。

        Args:
            enable_llm: 是否启用 LLM 回退分类。默认 True。
            enable_cache: 是否启用分类结果缓存。默认 True。
        """
        self._enable_llm = enable_llm
        self._enable_cache = enable_cache
        logger.info("意图路由器初始化", enable_llm=enable_llm, enable_cache=enable_cache)

    # ---- 公开接口 ----

    def classify(self, question: str) -> IntentResult:
        """对用户问题进行意图分类。

        执行顺序：
        1. 检查缓存
        2. 规则快速匹配（关键词）
        3. LLM 分类（仅当规则不确定时）

        Args:
            question: 用户自然语言问题。

        Returns:
            IntentResult 分类结果。
        """
        if not question or not question.strip():
            return IntentResult(
                intent_type=IntentType.CHITCHAT,
                confidence=1.0,
                reason="空输入，默认闲聊",
            )

        normalized = question.strip()

        # 1. 检查缓存
        if self._enable_cache:
            cached = self._get_cached(normalized)
            if cached is not None:
                logger.debug("意图分类命中缓存", question=normalized[:50])
                return cached

        # 2. 规则快速匹配
        rule_result = self._classify_by_rules(normalized)
        if rule_result is not None:
            logger.info(
                "规则匹配意图",
                intent=rule_result.intent_type.value,
                confidence=rule_result.confidence,
            )
            return rule_result

        # 3. LLM 分类回退
        if self._enable_llm:
            llm_result = self._classify_by_llm(normalized)
            if llm_result is not None:
                logger.info(
                    "LLM 分类意图",
                    intent=llm_result.intent_type.value,
                    confidence=llm_result.confidence,
                )
                return llm_result

        # 最终兜底：默认数据查询
        logger.warning("意图分类兜底为 SQL_QUERY", question=normalized[:100])
        fallback = IntentResult(
            intent_type=IntentType.SQL_QUERY,
            confidence=0.3,
            reason="规则和 LLM 均无法确定，默认数据查询",
        )
        return fallback

    # ---- 规则匹配 ----

    def _classify_by_rules(self, question: str) -> IntentResult | None:
        """使用关键词规则进行意图分类。

        Returns:
            如果规则能确定意图则返回 IntentResult，否则返回 None。
        """
        lower_q = question.lower()

        # 优先级 1：转人工
        for kw in _ESCALATE_KEYWORDS:
            if kw in lower_q:
                return IntentResult(
                    intent_type=IntentType.ESCALATE_TO_HUMAN,
                    confidence=0.95,
                    reason=f"命中转人工关键词: {kw}",
                )

        # 优先级 2：闲聊（但需排除混合查询）
        chitchat_hits = sum(1 for kw in _CHITCHAT_KEYWORDS if kw in lower_q)
        if chitchat_hits > 0 and len(question) <= 10:
            return IntentResult(
                intent_type=IntentType.CHITCHAT,
                confidence=0.9,
                reason="命中闲聊关键词且输入较短",
            )

        # 优先级 3：超出范围
        for kw in _OUT_OF_SCOPE_KEYWORDS:
            if kw in lower_q and not self._has_query_keyword(lower_q):
                # 排除可能是数据查询的场景（如"销售额增长趋势"中的"增长"）
                return IntentResult(
                    intent_type=IntentType.OUT_OF_SCOPE,
                    confidence=0.8,
                    reason=f"命中超出范围关键词: {kw}",
                )

        # 优先级 4：数据查询
        sql_hits = [kw for kw in _SQL_QUERY_KEYWORDS if kw in lower_q]
        if sql_hits:
            return IntentResult(
                intent_type=IntentType.SQL_QUERY,
                confidence=min(0.7 + 0.03 * len(sql_hits), 0.95),
                reason=f"命中数据查询关键词: {', '.join(sql_hits[:3])}",
            )

        # 规则无法确定
        return None

    def _has_query_keyword(self, question: str) -> bool:
        """检查问题中是否包含数据查询关键词。"""
        lower_q = question.lower()
        return any(kw in lower_q for kw in _SQL_QUERY_KEYWORDS)

    # ---- LLM 分类 ----

    def _classify_by_llm(self, question: str) -> IntentResult | None:
        """调用 LLM 进行意图分类。

        使用 JSON mode 确保结构化输出。

        Returns:
            LLM 分类结果，失败时返回 None。
        """
        try:
            # 占位导入，Track A 负责实现 LLMRouter
            from datapilot_llm import LLMRouter  # noqa: F401

            _ = _INTENT_CLASSIFY_PROMPT.format(question=question)

            # TODO: 通过 LLMRouter 调用 LLM（JSON mode）
            # response = LLMRouter.call(
            #     prompt=prompt,
            #     scene="intent",
            #     response_format="json",
            # )
            # parsed = json.loads(response)
            # return IntentResult(
            #     intent_type=IntentType(parsed["intent"]),
            #     confidence=parsed.get("confidence", 0.5),
            #     reason=parsed.get("reason", ""),
            #     extracted_entities=parsed.get("entities", []),
            # )

            logger.warning("LLM 意图分类尚未实现，回退到规则", question=question[:50])
            return None

        except ImportError:
            logger.debug("datapilot_llm 未安装，跳过 LLM 意图分类")
            return None
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("LLM 意图分类解析失败", error=str(e))
            return None

    # ---- 缓存 ----

    @staticmethod
    def _get_cached(question: str) -> IntentResult | None:
        """从缓存获取分类结果。

        使用 LRU 缓存常见意图分类。
        """
        # 通过 lru_cache 装饰的函数实现
        return _cached_classify(question)

    @staticmethod
    def _build_cache_key(question: str) -> str:
        """构建缓存键（标准化后的问句）。"""
        return re.sub(r"\s+", " ", question.strip().lower())


# ============================================================
# 缓存实现：预置常见问句
# ============================================================

# 常见意图分类的缓存表
_COMMON_INTENTS: dict[str, IntentResult] = {
    "你好": IntentResult(
        intent_type=IntentType.CHITCHAT, confidence=1.0, reason="常见问候语"
    ),
    "谢谢": IntentResult(
        intent_type=IntentType.CHITCHAT, confidence=1.0, reason="常见致谢语"
    ),
}


def _cached_classify(question: str) -> IntentResult | None:
    """从预置缓存表中查找意图分类结果。"""
    normalized = re.sub(r"\s+", " ", question.strip().lower())
    return _COMMON_INTENTS.get(normalized)
