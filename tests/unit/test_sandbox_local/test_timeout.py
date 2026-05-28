"""进程超时控制器单元测试。"""

from __future__ import annotations

import sys

import pytest

from datapilot_sandbox.local.timeout import ProcessTimeout


class TestProcessTimeoutInit:
    """ProcessTimeout 初始化测试。"""

    def test_init_default(self) -> None:
        """测试默认超时时间为 30 秒。"""
        pt = ProcessTimeout()
        assert pt.timeout_seconds == 30.0

    def test_init_custom_timeout(self) -> None:
        """测试自定义超时时间。"""
        pt = ProcessTimeout(timeout_seconds=10.0)
        assert pt.timeout_seconds == 10.0

    def test_init_zero_timeout_raises(self) -> None:
        """测试 timeout_seconds=0 抛出 ValueError。"""
        with pytest.raises(ValueError, match="timeout_seconds 必须为正数"):
            ProcessTimeout(timeout_seconds=0)

    def test_init_negative_timeout_raises(self) -> None:
        """测试 timeout_seconds 为负数抛出 ValueError。"""
        with pytest.raises(ValueError, match="timeout_seconds 必须为正数"):
            ProcessTimeout(timeout_seconds=-5.0)

    def test_init_fractional_timeout(self) -> None:
        """测试小数超时时间。"""
        pt = ProcessTimeout(timeout_seconds=0.5)
        assert pt.timeout_seconds == 0.5


class TestProcessTimeoutRun:
    """ProcessTimeout.run() 执行测试。"""

    @pytest.fixture
    def pt(self) -> ProcessTimeout:
        """创建超时控制器，使用 5 秒超时。"""
        return ProcessTimeout(timeout_seconds=5.0)

    @pytest.mark.asyncio
    async def test_run_simple_code_success(self, pt: ProcessTimeout) -> None:
        """测试正常执行代码返回 returncode=0。"""
        returncode, stdout, stderr, elapsed_ms = await pt.run("print('hello')")
        assert returncode == 0
        assert b"hello" in stdout
        assert elapsed_ms > 0

    @pytest.mark.asyncio
    async def test_run_return_type_is_tuple_of_four(
        self, pt: ProcessTimeout
    ) -> None:
        """测试返回值格式为 (int, bytes, bytes, float)。"""
        result = await pt.run("x = 1 + 1")
        assert isinstance(result, tuple)
        assert len(result) == 4
        assert isinstance(result[0], int)
        assert isinstance(result[1], bytes)
        assert isinstance(result[2], bytes)
        assert isinstance(result[3], float)

    @pytest.mark.asyncio
    async def test_run_stderr_captured(self, pt: ProcessTimeout) -> None:
        """测试 stderr 被正确捕获。"""
        returncode, stdout, stderr, _ = await pt.run(
            "import sys; sys.stderr.write('error output')"
        )
        assert b"error output" in stderr

    @pytest.mark.asyncio
    async def test_run_code_with_error_nonzero_returncode(
        self, pt: ProcessTimeout
    ) -> None:
        """测试执行出错的代码返回非零 returncode。"""
        returncode, _, stderr, _ = await pt.run("1 / 0")
        assert returncode != 0
        assert b"ZeroDivisionError" in stderr

    @pytest.mark.asyncio
    async def test_run_syntax_error_nonzero_returncode(
        self, pt: ProcessTimeout
    ) -> None:
        """测试语法错误代码返回非零 returncode。"""
        returncode, _, stderr, _ = await pt.run("this is not valid !!!")
        assert returncode != 0

    @pytest.mark.asyncio
    async def test_run_empty_code_success(self, pt: ProcessTimeout) -> None:
        """测试空代码正常执行。"""
        returncode, stdout, stderr, elapsed_ms = await pt.run("")
        assert returncode == 0
        assert isinstance(stdout, bytes)
        assert isinstance(stderr, bytes)
        assert elapsed_ms >= 0

    @pytest.mark.asyncio
    async def test_run_invalid_python_path_returns_error(self) -> None:
        """测试无效 python_path 返回错误。"""
        pt = ProcessTimeout(timeout_seconds=5.0)
        returncode, stdout, stderr, elapsed_ms = await pt.run(
            "print('hello')",
            python_path="/nonexistent/python/path/bin/python",
        )
        assert returncode == -1
        assert b"Python" in stderr  # 错误消息包含 "Python 解释器不存在"

    @pytest.mark.asyncio
    async def test_run_timeout_returns_minus_one(self) -> None:
        """测试超时后返回 returncode=-1。"""
        pt = ProcessTimeout(timeout_seconds=0.5)
        returncode, stdout, stderr, elapsed_ms = await pt.run(
            "import time; time.sleep(10)"
        )
        assert returncode == -1
        assert elapsed_ms > 0

    @pytest.mark.asyncio
    async def test_run_timeout_empty_output(self) -> None:
        """测试超时后 stdout 和 stderr 为空。"""
        pt = ProcessTimeout(timeout_seconds=0.5)
        returncode, stdout, stderr, elapsed_ms = await pt.run(
            "import time; time.sleep(10)"
        )
        assert returncode == -1
        # 超时返回 b"", b""
        assert stdout == b""
        assert stderr == b""

    @pytest.mark.asyncio
    async def test_run_extra_env_passed(self, pt: ProcessTimeout) -> None:
        """测试额外环境变量传递到子进程。"""
        returncode, stdout, stderr, _ = await pt.run(
            "import os; print(os.environ.get('MY_TEST_VAR', 'not_set'))",
            extra_env={"MY_TEST_VAR": "test_value"},
        )
        assert returncode == 0
        assert b"test_value" in stdout

    @pytest.mark.asyncio
    async def test_run_pythonpath_cleared(self, pt: ProcessTimeout) -> None:
        """测试 PYTHONPATH 被清空以隔离执行环境。"""
        returncode, stdout, stderr, _ = await pt.run(
            "import os; print(repr(os.environ.get('PYTHONPATH')))",
        )
        assert returncode == 0
        # PYTHONPATH 应被设置为空字符串
        assert b"''" in stdout

    @pytest.mark.asyncio
    async def test_run_elapsed_time_reasonable(self, pt: ProcessTimeout) -> None:
        """测试执行时间在合理范围内。"""
        returncode, _, _, elapsed_ms = await pt.run("x = 1")
        # 简单代码执行时间不应超过 2 秒
        assert elapsed_ms < 2000

    @pytest.mark.asyncio
    async def test_run_uses_specified_python(self) -> None:
        """测试使用指定的 Python 解释器。"""
        pt = ProcessTimeout(timeout_seconds=5.0)
        returncode, stdout, _, _ = await pt.run(
            "import sys; print(sys.executable)",
            python_path=sys.executable,
        )
        assert returncode == 0
