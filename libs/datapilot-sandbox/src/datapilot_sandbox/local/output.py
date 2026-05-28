"""输出截断器。

限制子进程 stdout/stderr 输出大小，防止内存耗尽。
"""

from __future__ import annotations

TRUNCATION_MARKER = b"\n... [output truncated] ..."


class OutputTruncator:
    """输出截断器，限制 stdout/stderr 大小。

    当子进程产生过多输出时，截断到指定大小并附加截断标记，
    防止大量输出占用内存。

    Attributes:
        max_bytes: 允许的最大输出字节数。
    """

    def __init__(self, max_bytes: int = 1048576) -> None:
        """初始化截断器。

        Args:
            max_bytes: 最大输出字节数，默认 1MB。
        """
        if max_bytes <= 0:
            raise ValueError(f"max_bytes 必须为正数，当前值: {max_bytes}")
        self.max_bytes = max_bytes

    def truncate(self, data: bytes) -> tuple[bytes, bool]:
        """截断输出。

        如果数据大小超过 max_bytes，保留前 max_bytes 字节并附加截断标记。

        Args:
            data: 原始输出数据。

        Returns:
            元组 (截断后数据, 是否被截断)。
        """
        if len(data) <= self.max_bytes:
            return data, False

        truncated = self.max_bytes + len(TRUNCATION_MARKER)
        if len(data) <= truncated:
            # 数据加上截断标记不会超出太多，直接截断
            return data[: self.max_bytes] + TRUNCATION_MARKER, True

        # 数据非常大，截断后加标记
        return data[: self.max_bytes] + TRUNCATION_MARKER, True

    @staticmethod
    def format_truncated(data: bytes, max_chars: int = 500) -> str:
        """格式化截断输出用于展示（UTF-8 解码 + 截断标记）。

        将字节数据解码为 UTF-8 字符串，处理可能存在的解码错误，
        并限制展示长度。

        Args:
            data: 输出数据（可能已被截断）。
            max_chars: 最大展示字符数，默认 500。

        Returns:
            格式化后的展示字符串。
        """
        # 使用 errors="replace" 处理非法 UTF-8 字节
        text = data.decode("utf-8", errors="replace")

        if len(text) <= max_chars:
            return text

        return text[:max_chars] + "\n... [display truncated] ..."
