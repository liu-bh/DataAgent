"""工具选择器。

根据用户意图，通过关键词匹配和评分机制选择合适的工具列表，
减少不必要的工具传递给 LLM，提高 Function Calling 的准确性和效率。
"""

from __future__ import annotations

import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# 中英文常见停用词，不参与匹配
_STOP_WORDS: set[str] = {
    "的",
    "了",
    "在",
    "是",
    "我",
    "有",
    "和",
    "就",
    "不",
    "人",
    "都",
    "一",
    "一个",
    "上",
    "也",
    "很",
    "到",
    "说",
    "要",
    "去",
    "你",
    "会",
    "着",
    "没有",
    "看",
    "好",
    "自己",
    "这",
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "shall",
    "can",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "at",
    "by",
    "from",
    "that",
    "this",
    "it",
    "and",
    "or",
    "not",
    "but",
}


class ToolSelector:
    """工具选择器。

    基于关键词匹配和评分机制，从已注册的工具中选择与用户消息
    最相关的候选工具列表。

    Args:
        registry: 工具注册表实例，提供已注册工具的元信息。
        min_score: 最低匹配分数阈值，低于此分数的工具不会被选中。
        max_tools: 最多返回的工具数量。
    """

    def __init__(
        self,
        registry: Any,
        *,
        min_score: float = 0.1,
        max_tools: int = 10,
    ) -> None:
        self._registry = registry
        self._min_score = min_score
        self._max_tools = max_tools

    async def select(self, user_message: str) -> list[str]:
        """基于关键词匹配选择候选工具列表。

        Args:
            user_message: 用户自然语言输入。

        Returns:
            匹配的工具名称列表，按分数降序排列。
        """
        tools = self._registry.list_tools()
        scored: list[tuple[str, float]] = []

        for tool in tools:
            score = self._score_tool(tool, user_message)
            if score >= self._min_score:
                # 提取工具名称：支持字符串或对象
                tool_name = getattr(tool, "name", str(tool))
                scored.append((tool_name, score))

        # 按分数降序排列，取前 max_tools 个
        scored.sort(key=lambda x: x[1], reverse=True)
        selected = [name for name, _ in scored[: self._max_tools]]

        logger.debug(
            "tool_selection_completed",
            user_message=user_message[:50],
            candidates=len(scored),
            selected=selected,
        )

        return selected

    def _score_tool(self, tool: Any, message: str) -> float:
        """计算工具与消息的匹配得分。

        综合考虑以下因素：
        1. 工具名称与消息关键词的匹配度
        2. 工具描述与消息的语义相关性
        3. 工具参数名称与消息中提及的匹配

        Args:
            tool: 工具对象，需具备 name、description、parameters 属性。
            message: 用户消息。

        Returns:
            匹配得分，范围 [0.0, 1.0]。
        """
        message_lower = message.lower()
        message_tokens = set(self._tokenize(message_lower))

        score = 0.0

        # 1. 工具名称匹配（权重 0.4）
        tool_name = getattr(tool, "name", str(tool))
        name_tokens = set(self._tokenize(tool_name.lower()))
        if name_tokens:
            name_matches = name_tokens & message_tokens
            score += 0.4 * (len(name_matches) / len(name_tokens))

        # 2. 工具描述匹配（权重 0.35）
        description = getattr(tool, "description", "")
        desc_tokens = set(self._tokenize(description.lower()))
        if desc_tokens:
            desc_matches = desc_tokens & message_tokens
            score += 0.35 * (len(desc_matches) / len(desc_tokens))

        # 3. 参数名称匹配（权重 0.25）
        parameters = getattr(tool, "parameters", {})
        if isinstance(parameters, dict):
            param_names = set()
            props = parameters.get("properties", {})
            for param_name in props:
                param_name_tokens = set(self._tokenize(param_name.lower()))
                param_names |= param_name_tokens
            if param_names:
                param_matches = param_names & message_tokens
                score += 0.25 * (len(param_matches) / len(param_names))

        return min(score, 1.0)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """简单的文本分词，提取非停用词的 token。

        对中文使用单字粒度（去掉停用词），对英文使用空格分词。

        Args:
            text: 输入文本。

        Returns:
            token 列表。
        """
        # 移除标点符号
        text = re.sub(r"[^\w\u4e00-\u9fff]", " ", text)
        text = text.strip()

        tokens: list[str] = []
        for word in text.split():
            # 将混合词拆分为中文片段和英文片段
            # 例如 "用Python执行" -> ["用", "Python", "执行"]
            segments = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9]+", word)
            for segment in segments:
                has_chinese = bool(re.search(r"[\u4e00-\u9fff]", segment))
                if has_chinese:
                    # 中文按单字切分
                    for char in segment:
                        if char not in _STOP_WORDS and len(char.strip()) > 0:
                            tokens.append(char)
                else:
                    # 英文/数字直接作为 token
                    lower_word = segment.lower()
                    if lower_word not in _STOP_WORDS:
                        tokens.append(lower_word)

        return tokens
