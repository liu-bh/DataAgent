"""输出截断器单元测试。"""

from __future__ import annotations

import importlib

import pytest

# 直接导入模块，避免触发 datapilot_sandbox.__init__ 中的 k8s 导入
_output_module = importlib.import_module("datapilot_sandbox.local.output")
OutputTruncator = _output_module.OutputTruncator


class TestOutputTruncator:
    """OutputTruncator 测试。"""

    def test_init_default(self) -> None:
        """测试默认初始化。"""
        truncator = OutputTruncator()
        assert truncator.max_bytes == 1048576  # 1MB

    def test_init_custom(self) -> None:
        """测试自定义最大字节数。"""
        truncator = OutputTruncator(max_bytes=100)
        assert truncator.max_bytes == 100

    def test_init_invalid_max_bytes(self) -> None:
        """测试无效的 max_bytes 值。"""
        with pytest.raises(ValueError, match="max_bytes 必须为正数"):
            OutputTruncator(max_bytes=0)
        with pytest.raises(ValueError, match="max_bytes 必须为正数"):
            OutputTruncator(max_bytes=-1)

    def test_truncate_no_truncation(self) -> None:
        """测试数据未超过限制时不截断。"""
        truncator = OutputTruncator(max_bytes=100)
        data = b"hello world"
        result, is_truncated = truncator.truncate(data)
        assert result == data
        assert is_truncated is False

    def test_truncate_exact_size(self) -> None:
        """测试数据刚好等于限制时不截断。"""
        truncator = OutputTruncator(max_bytes=11)
        data = b"hello world"
        result, is_truncated = truncator.truncate(data)
        assert result == data
        assert is_truncated is False

    def test_truncate_over_size(self) -> None:
        """测试数据超过限制时截断。"""
        truncator = OutputTruncator(max_bytes=10)
        data = b"hello world, this is a longer output"
        result, is_truncated = truncator.truncate(data)
        assert is_truncated is True
        assert len(result) > 10  # 加上截断标记
        assert result.startswith(b"hello worl")

    def test_truncate_empty_data(self) -> None:
        """测试空数据不截断。"""
        truncator = OutputTruncator(max_bytes=100)
        result, is_truncated = truncator.truncate(b"")
        assert result == b""
        assert is_truncated is False

    def test_truncate_with_marker(self) -> None:
        """测试截断标记存在。"""
        truncator = OutputTruncator(max_bytes=5)
        data = b"hello world"
        result, is_truncated = truncator.truncate(data)
        assert is_truncated is True
        assert b"[output truncated]" in result

    def test_format_truncated_short(self) -> None:
        """测试格式化短数据。"""
        data = b"hello"
        result = OutputTruncator.format_truncated(data)
        assert result == "hello"

    def test_format_truncated_long(self) -> None:
        """测试格式化长数据（截断展示）。"""
        data = b"a" * 1000
        result = OutputTruncator.format_truncated(data, max_chars=100)
        assert len(result) <= 150  # 100 字符 + 截断标记
        assert "[display truncated]" in result

    def test_format_truncated_default_max_chars(self) -> None:
        """测试默认 max_chars=500。"""
        data = b"a" * 1000
        result = OutputTruncator.format_truncated(data)
        assert "[display truncated]" in result

    def test_format_truncated_utf8(self) -> None:
        """测试 UTF-8 解码。"""
        data = "你好世界".encode("utf-8")
        result = OutputTruncator.format_truncated(data)
        assert result == "你好世界"

    def test_format_truncated_invalid_utf8(self) -> None:
        """测试非法 UTF-8 字节使用 replace 处理。"""
        data = b"\xff\xfe\xfd"
        result = OutputTruncator.format_truncated(data)
        # 不应该抛出异常
        assert isinstance(result, str)

    def test_format_truncated_exact_chars(self) -> None:
        """测试数据刚好等于 max_chars 时不截断展示。"""
        data = b"a" * 500
        result = OutputTruncator.format_truncated(data, max_chars=500)
        assert result == "a" * 500
        assert "[display truncated]" not in result

    def test_init_max_bytes_one(self) -> None:
        """测试 max_bytes=1 最小正值初始化。"""
        truncator = OutputTruncator(max_bytes=1)
        assert truncator.max_bytes == 1

    def test_truncate_one_byte_over(self) -> None:
        """测试数据刚好超过 1 字节时截断。"""
        truncator = OutputTruncator(max_bytes=1)
        data = b"ab"
        result, is_truncated = truncator.truncate(data)
        assert is_truncated is True
        assert result.startswith(b"a")
        assert b"[output truncated]" in result

    def test_truncate_very_large_data(self) -> None:
        """测试非常大的数据被截断。"""
        truncator = OutputTruncator(max_bytes=100)
        data = b"x" * 10_000_000  # 10MB
        result, is_truncated = truncator.truncate(data)
        assert is_truncated is True
        # 截断后数据长度 = max_bytes + 截断标记长度
        assert len(result) == 100 + len(b"\n... [output truncated] ...")

    def test_format_truncated_empty(self) -> None:
        """测试格式化空数据返回空字符串。"""
        result = OutputTruncator.format_truncated(b"")
        assert result == ""

    def test_format_truncated_max_chars_one(self) -> None:
        """测试 max_chars=1 时截断展示。"""
        data = b"hello"
        result = OutputTruncator.format_truncated(data, max_chars=1)
        assert result == "h\n... [display truncated] ..."
