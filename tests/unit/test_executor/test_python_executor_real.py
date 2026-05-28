"""Python 任务执行器真实实现单元测试。

测试 PythonTaskExecutor 的核心功能：
- 正常 Python 代码执行
- 危险代码拒绝
- 超时处理
- 输出截断
- 无沙箱时的降级行为
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datapilot_dag.executor.python_executor import PythonTaskExecutor


class TestPythonTaskExecutorInit:
    """PythonTaskExecutor 初始化测试。"""

    def test_init_without_sandbox(self) -> None:
        """不传入沙箱时 sandbox_executor 为 None。"""
        executor = PythonTaskExecutor()
        assert executor._sandbox_executor is None

    def test_init_with_sandbox(self) -> None:
        """传入沙箱时正确保存。"""
        mock_sandbox = MagicMock()
        executor = PythonTaskExecutor(sandbox_executor=mock_sandbox)
        assert executor._sandbox_executor is mock_sandbox


class TestPythonTaskExecutorExecute:
    """PythonTaskExecutor 执行测试。"""

    @pytest.mark.asyncio
    async def test_simple_code_execution(self) -> None:
        """测试正常 Python 代码执行。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-1",
            config={"code": "result = 1 + 1\nprint(result)"},
            context={},
        )

        assert result["success"] is True
        assert "2" in result["stdout"]
        assert result["stderr"] == ""
        assert result["sandbox_available"] is False
        assert result["execution_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_multiline_code_execution(self) -> None:
        """测试多行 Python 代码执行。"""
        executor = PythonTaskExecutor()

        code = """
data = [1, 2, 3, 4, 5]
total = sum(data)
average = total / len(data)
print(f"总和: {total}, 平均值: {average}")
"""
        result = await executor.execute(
            node_id="py-2",
            config={"code": code},
            context={},
        )

        assert result["success"] is True
        assert "15" in result["stdout"]
        assert "3.0" in result["stdout"]

    @pytest.mark.asyncio
    async def test_code_with_context(self) -> None:
        """测试代码可以访问上下文变量。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-3",
            config={"code": "print(context['value'])"},
            context={"value": "hello_from_upstream"},
        )

        assert result["success"] is True
        assert "hello_from_upstream" in result["stdout"]

    @pytest.mark.asyncio
    async def test_code_with_syntax_error(self) -> None:
        """测试代码语法错误的处理。

        语法错误代码会被 AST 安全检查器拦截，报告为"代码语法错误"。
        """
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-4",
            config={"code": "def broken("},
            context={},
        )

        assert result["success"] is False
        assert result["stderr"] != ""
        # 语法错误被 AST 检查器拦截
        assert "语法错误" in result["stderr"] or "SyntaxError" in result["stderr"]

    @pytest.mark.asyncio
    async def test_code_with_runtime_error(self) -> None:
        """测试代码运行时错误的处理。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-5",
            config={"code": "x = 1 / 0"},
            context={},
        )

        assert result["success"] is False
        assert result["stderr"] != ""
        assert "ZeroDivisionError" in result["stderr"]

    @pytest.mark.asyncio
    async def test_missing_code_raises(self) -> None:
        """测试缺少 code 参数时抛出 ValueError。"""
        executor = PythonTaskExecutor()

        with pytest.raises(ValueError, match="code"):
            await executor.execute(
                node_id="py-6",
                config={},
                context={},
            )


class TestPythonTaskExecutorSecurity:
    """PythonTaskExecutor 安全检查测试。"""

    @pytest.mark.asyncio
    async def test_dangerous_import_os_rejected(self) -> None:
        """测试禁止导入 os 模块。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-sec-1",
            config={"code": "import os; os.system('ls')"},
            context={},
        )

        assert result["success"] is False
        assert "os" in result["stderr"]

    @pytest.mark.asyncio
    async def test_dangerous_import_subprocess_rejected(self) -> None:
        """测试禁止导入 subprocess 模块。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-sec-2",
            config={"code": "import subprocess; subprocess.run(['ls'])"},
            context={},
        )

        assert result["success"] is False
        assert "subprocess" in result["stderr"]

    @pytest.mark.asyncio
    async def test_dangerous_import_sys_rejected(self) -> None:
        """测试禁止导入 sys 模块。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-sec-3",
            config={"code": "import sys; print(sys.path)"},
            context={},
        )

        assert result["success"] is False
        assert "sys" in result["stderr"]

    @pytest.mark.asyncio
    async def test_dangerous_from_import_rejected(self) -> None:
        """测试禁止 from ... import 形式的危险导入。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-sec-4",
            config={"code": "from os import system; system('ls')"},
            context={},
        )

        assert result["success"] is False
        assert "os" in result["stderr"]

    @pytest.mark.asyncio
    async def test_dangerous_import_socket_rejected(self) -> None:
        """测试禁止导入 socket 模块。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-sec-5",
            config={"code": "import socket"},
            context={},
        )

        assert result["success"] is False
        assert "socket" in result["stderr"]

    @pytest.mark.asyncio
    async def test_dangerous_import_ctypes_rejected(self) -> None:
        """测试禁止导入 ctypes 模块。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-sec-6",
            config={"code": "import ctypes"},
            context={},
        )

        assert result["success"] is False
        assert "ctypes" in result["stderr"]

    @pytest.mark.asyncio
    async def test_safe_import_allowed(self) -> None:
        """测试非危险模块导入被允许（如 math）。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-sec-7",
            config={"code": "import math\nprint(math.sqrt(16))"},
            context={},
        )

        assert result["success"] is True
        assert "4" in result["stdout"]

    @pytest.mark.asyncio
    async def test_sandbox_safety_check_failure(self) -> None:
        """测试沙箱安全检查失败时的处理。"""
        mock_sandbox = MagicMock()
        safety_result = MagicMock()
        safety_result.is_safe = False
        safety_result.violations = ["检测到危险操作: 文件写入"]
        mock_sandbox.check_safety = MagicMock(return_value=safety_result)

        executor = PythonTaskExecutor(sandbox_executor=mock_sandbox)

        result = await executor.execute(
            node_id="py-sec-8",
            config={"code": "open('test.txt', 'w')"},
            context={},
        )

        assert result["success"] is False
        assert "文件写入" in result["stderr"]
        assert result["sandbox_available"] is True


class TestPythonTaskExecutorTimeout:
    """PythonTaskExecutor 超时处理测试。"""

    @pytest.mark.asyncio
    async def test_timeout_with_infinite_loop(self) -> None:
        """测试无限循环代码的超时处理。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-timeout-1",
            config={
                "code": "while True:\n    pass",
                "timeout": 0.5,  # 0.5 秒超时
            },
            context={},
        )

        assert result["success"] is False
        assert "超时" in result["stderr"]

    @pytest.mark.asyncio
    async def test_default_timeout(self) -> None:
        """测试使用默认超时参数。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-timeout-2",
            config={
                "code": "print('done')",
                # 不传 timeout，使用默认值 30 秒
            },
            context={},
        )

        assert result["success"] is True
        assert "done" in result["stdout"]

    @pytest.mark.asyncio
    async def test_short_timeout_with_valid_code(self) -> None:
        """测试短超时但代码快速完成的情况。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-timeout-3",
            config={
                "code": "print('fast')",
                "timeout": 5.0,
            },
            context={},
        )

        assert result["success"] is True
        assert "fast" in result["stdout"]


class TestPythonTaskExecutorOutputTruncation:
    """PythonTaskExecutor 输出截断测试。"""

    @pytest.mark.asyncio
    async def test_output_truncation(self) -> None:
        """测试输出超过大小限制时被截断。"""
        executor = PythonTaskExecutor()

        # 生成超过 100 字节的输出
        code = "for i in range(1000):\n    print(f'line_{i:04d}_padding_data')"
        result = await executor.execute(
            node_id="py-truncate-1",
            config={
                "code": code,
                "max_output_bytes": 100,
            },
            context={},
        )

        assert result["success"] is True
        assert "已截断" in result["stdout"]
        # 验证截断后的输出不超过限制太多（截断提示本身会增加一些长度）
        output_bytes = len(result["stdout"].encode("utf-8"))
        assert output_bytes < 200  # 允许截断提示的额外长度

    @pytest.mark.asyncio
    async def test_output_within_limit(self) -> None:
        """测试输出在限制内时不被截断。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-truncate-2",
            config={
                "code": "print('short output')",
                "max_output_bytes": 1024,
            },
            context={},
        )

        assert result["success"] is True
        assert "已截断" not in result["stdout"]
        assert "short output" in result["stdout"]

    @pytest.mark.asyncio
    async def test_default_max_output_bytes(self) -> None:
        """测试默认输出限制（64KB）不被截断。"""
        executor = PythonTaskExecutor()

        # 生成较小输出
        code = "print('x' * 100)"
        result = await executor.execute(
            node_id="py-truncate-3",
            config={"code": code},
            context={},
        )

        assert result["success"] is True
        assert "已截断" not in result["stdout"]


class TestPythonTaskExecutorFallback:
    """PythonTaskExecutor 无沙箱降级测试。"""

    @pytest.mark.asyncio
    async def test_fallback_without_sandbox(self) -> None:
        """测试无沙箱时使用内置执行，sandbox_available 为 False。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-fallback-1",
            config={"code": "print(2 + 2)"},
            context={},
        )

        assert result["success"] is True
        assert result["sandbox_available"] is False
        assert "4" in result["stdout"]

    @pytest.mark.asyncio
    async def test_fallback_missing_sandbox_module(self) -> None:
        """测试 datapilot_sandbox 模块不存在时的降级。"""
        executor = PythonTaskExecutor()

        # 模拟延迟导入失败
        with patch(
            "datapilot_dag.executor.python_executor.PythonTaskExecutor._get_sandbox",
            return_value=None,
        ):
            result = await executor.execute(
                node_id="py-fallback-2",
                config={"code": "print('fallback')"},
                context={},
            )

        assert result["success"] is True
        assert result["sandbox_available"] is False

    @pytest.mark.asyncio
    async def test_with_sandbox_available(self) -> None:
        """测试有沙箱时 sandbox_available 为 True。"""
        mock_sandbox = MagicMock()
        mock_exec_result = MagicMock()
        mock_exec_result.stdout = "sandbox output"
        mock_exec_result.stderr = ""
        mock_exec_result.exit_code = 0
        mock_sandbox.execute = AsyncMock(return_value=mock_exec_result)
        # 没有 check_safety 方法，跳过安全检查

        executor = PythonTaskExecutor(sandbox_executor=mock_sandbox)

        result = await executor.execute(
            node_id="py-fallback-3",
            config={"code": "print('test')"},
            context={},
        )

        assert result["success"] is True
        assert result["sandbox_available"] is True
        assert "sandbox output" in result["stdout"]


class TestPythonTaskExecutorCancel:
    """PythonTaskExecutor 取消功能测试。"""

    @pytest.mark.asyncio
    async def test_cancel(self) -> None:
        """测试取消任务。"""
        executor = PythonTaskExecutor()
        result = await executor.cancel("py-cancel-1")
        assert result is True
        assert "py-cancel-1" in executor._cancelled_tasks

    @pytest.mark.asyncio
    async def test_execute_cancelled_node_raises(self) -> None:
        """测试已取消的节点执行时抛出 RuntimeError。"""
        executor = PythonTaskExecutor()
        await executor.cancel("py-cancel-2")

        with pytest.raises(RuntimeError, match="已被取消"):
            await executor.execute(
                node_id="py-cancel-2",
                config={"code": "print('test')"},
                context={},
            )

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        """测试健康检查。"""
        executor = PythonTaskExecutor()
        result = await executor.health_check()
        assert result is True


class TestPythonTaskExecutorTruncateOutput:
    """_truncate_output 静态方法测试。"""

    def test_no_truncation_needed(self) -> None:
        """测试无需截断的情况。"""
        result = PythonTaskExecutor._truncate_output("hello", 100)
        assert result == "hello"

    def test_truncation_applied(self) -> None:
        """测试需要截断的情况。"""
        long_text = "x" * 200
        result = PythonTaskExecutor._truncate_output(long_text, 100)
        assert "已截断" in result
        assert "200" in result
        assert "100" in result

    def test_empty_output(self) -> None:
        """测试空输出。"""
        result = PythonTaskExecutor._truncate_output("", 100)
        assert result == ""

    def test_unicode_output(self) -> None:
        """测试包含 Unicode 字符的输出截断。"""
        # 中文字符每个占 3 字节（UTF-8）
        unicode_text = "你好世界" * 50  # 600 字节
        result = PythonTaskExecutor._truncate_output(unicode_text, 100)
        assert "已截断" in result
