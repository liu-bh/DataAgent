"""对话摘要生成器。"""

from __future__ import annotations

from .models import ConversationTurn


class ConversationSummarizer:
    """对话摘要生成器。

    Phase1 使用规则摘要（提取关键信息），
    后续可接入 LLM 生成更自然的摘要。
    """

    def summarize(self, turns: list[ConversationTurn]) -> str:
        """生成对话摘要。

        规则策略：
        1. 提取用户问题列表
        2. 统计对话轮数
        3. 提取最后一条助手回复的前 100 字符
        """
        if not turns:
            return "暂无对话记录。"

        questions = self.extract_key_questions(turns)
        turn_count = len(turns)
        last_response_preview = ""

        # 从后向前查找最后一条助手回复
        for turn in reversed(turns):
            if turn.role == "assistant" and turn.content:
                last_response_preview = turn.content[:100]
                break

        return self._format_summary(questions, turn_count, last_response_preview)

    def extract_key_questions(self, turns: list[ConversationTurn]) -> list[str]:
        """提取用户提问。"""
        questions: list[str] = []
        for turn in turns:
            if turn.role == "user" and turn.content.strip():
                # 截断过长的问题
                content = turn.content.strip()
                if len(content) > 80:
                    content = content[:80] + "..."
                questions.append(content)
        return questions

    def _format_summary(
        self,
        questions: list[str],
        turn_count: int,
        last_response_preview: str,
    ) -> str:
        """格式化摘要文本。"""
        parts: list[str] = [f"本次对话共 {turn_count} 轮。"]

        if questions:
            parts.append(f"用户提出了 {len(questions)} 个问题：")
            for i, q in enumerate(questions, 1):
                parts.append(f"  {i}. {q}")
        else:
            parts.append("用户未提出问题。")

        if last_response_preview:
            parts.append(f"最近助手回复摘要：{last_response_preview}")

        return "\n".join(parts)
