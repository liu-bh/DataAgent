"""PythonTaskExecutor 单元测试（Track D — DAG Python 执行器集成）。

覆盖场景：
1. 基础执行：execute() 不带沙箱执行简单 print 代码，返回 stdout
2. 缺 code 参数：execute() config 中无 code，抛 ValueError
3. 取消节点：cancel() 后 execute() 抛 RuntimeError
4. 超时处理：无限循环代码执行超时后返回 success=False
5. 安全检查：import os 代码返回安全检查未通过
6. 截断输出：大量输出被截断
7. 默认超时：未指定 timeout 时使用 30s 默认值
8. 输出截断工具方法：_truncate_output() 正确截断
9. 内置执行成功：无沙箱时纯计算代码执行成功
10. 内置执行语法错误：无沙箱时代码语法错误返回错误
11. 内置执行危险导入：无沙箱时 import os 被拦截
12. 内置执行异常：代码 raise Exception 返回错误信息
13. 内存占用信息：result 包含 execution_time_ms
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datapilot_dag.executor.python_executor import PythonTaskExecutor


class TestPythonTaskExecutorBasicExecution:
    """基础执行测试：无沙箱模式下的正常代码执行。"""

    @pytest.mark.asyncio
    async def test_simple_print_code(self) -> None:
        """执行简单 print 代码，返回 stdout。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-basic-1",
            config={"code": "print('hello world')"},
            context={},
        )

        assert result["success"] is True
        assert "hello world" in result["stdout"]
        assert result["stderr"] == ""
        assert result["sandbox_available"] is False


class TestPythonTaskExecutorMissingCode:
    """缺少 code 参数时的校验。"""

    @pytest.mark.asyncio
    async def test_missing_code_raises_value_error(self) -> None:
        """config 中无 code 参数时抛出 ValueError。"""
        executor = PythonTaskExecutor()

        with pytest.raises(ValueError, match="code"):
            await executor.execute(
                node_id="py-missing-1",
                config={},
                context={},
            )

    @pytest.mark.asyncio
    async def test_empty_code_raises_value_error(self) -> None:
        """config 中 code 为空字符串时也抛出 ValueError。"""
        executor = PythonTaskExecutor()

        with pytest.raises(ValueError, match="code"):
            await executor.execute(
                node_id="py-missing-2",
                config={"code": ""},
                context={},
            )


class TestPythonTaskExecutorCancel:
    """取消节点测试。"""

    @pytest.mark.asyncio
    async def test_cancel_returns_true(self) -> None:
        """cancel() 返回 True。"""
        executor = PythonTaskExecutor()
        result = await executor.cancel("py-cancel-1")

        assert result is True
        assert "py-cancel-1" in executor._cancelled_tasks

    @pytest.mark.asyncio
    async def test_execute_cancelled_node_raises_runtime_error(self) -> None:
        """cancel() 后 execute() 抛 RuntimeError。"""
        executor = PythonTaskExecutor()
        await executor.cancel("py-cancel-2")

        with pytest.raises(RuntimeError, match="已被取消"):
            await executor.execute(
                node_id="py-cancel-2",
                config={"code": "print('should not run')"},
                context={},
            )

    @pytest.mark.asyncio
    async def test_uncancelled_node_executes_normally(self) -> None:
        """取消一个节点不影响其他节点的执行。"""
        executor = PythonTaskExecutor()
        await executor.cancel("py-cancel-A")

        # 节点 B 不在取消集合中，应正常执行
        result = await executor.execute(
            node_id="py-cancel-B",
            config={"code": "print('ok')"},
            context={},
        )

        assert result["success"] is True


class TestPythonTaskExecutorTimeout:
    """超时处理测试。"""

    @pytest.mark.asyncio
    async def test_infinite_loop_timeout(self) -> None:
        """无限循环代码执行超时后返回 success=False。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-timeout-1",
            config={
                "code": "while True:\n    pass",
                "timeout": 0.5,
            },
            context={},
        )

        assert result["success"] is False
        assert "超时" in result["stderr"]

    @pytest.mark.asyncio
    async def test_default_timeout_value(self) -> None:
        """未指定 timeout 时使用 30s 默认值，正常代码可完成。"""
        executor = PythonTaskExecutor()

        # 不传 timeout 参数，使用默认值 30s
        result = await executor.execute(
            node_id="py-timeout-2",
            config={"code": "print('done')"},
            context={},
        )

        assert result["success"] is True
        assert "done" in result["stdout"]

    @pytest.mark.asyncio
    async def test_short_timeout_valid_code(self) -> None:
        """短超时但代码快速完成，应正常返回。"""
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


class TestPythonTaskExecutorSecurity:
    """安全检查测试：危险导入拦截。"""

    @pytest.mark.asyncio
    async def test_import_os_rejected(self) -> None:
        """import os 代码返回安全检查未通过。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-sec-1",
            config={"code": "import os; os.system('ls')"},
            context={},
        )

        assert result["success"] is False
        assert "os" in result["stderr"]

    @pytest.mark.asyncio
    async def test_from_import_os_rejected(self) -> None:
        """from os import ... 形式也被拦截。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-sec-2",
            config={"code": "from os import system; system('ls')"},
            context={},
        )

        assert result["success"] is False
        assert "os" in result["stderr"]

    @pytest.mark.asyncio
    async def test_import_subprocess_rejected(self) -> None:
        """import subprocess 被拦截。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-sec-3",
            config={"code": "import subprocess"},
            context={},
        )

        assert result["success"] is False
        assert "subprocess" in result["stderr"]

    @pytest.mark.asyncio
    async def test_safe_import_allowed(self) -> None:
        """非危险模块（如 math）允许导入。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-sec-4",
            config={"code": "import math\nprint(math.sqrt(16))"},
            context={},
        )

        assert result["success"] is True
        assert "4" in result["stdout"]

    @pytest.mark.asyncio
    async def test_sandbox_safety_check_failure(self) -> None:
        """有沙箱时，sandbox.check_safety 返回不安全的结果。"""
        mock_sandbox = MagicMock()
        safety_result = MagicMock()
        safety_result.is_safe = False
        safety_result.violations = ["检测到危险操作: 文件写入"]
        mock_sandbox.check_safety = MagicMock(return_value=safety_result)

        executor = PythonTaskExecutor(sandbox_executor=mock_sandbox)

        result = await executor.execute(
            node_id="py-sec-5",
            config={"code": "open('test.txt', 'w')"},
            context={},
        )

        assert result["success"] is False
        assert "文件写入" in result["stderr"]
        assert result["sandbox_available"] is True


class TestPythonTaskExecutorOutputTruncation:
    """输出截断测试。"""

    @pytest.mark.asyncio
    async def test_large_output_truncated(self) -> None:
        """大量输出超过限制时被截断。"""
        executor = PythonTaskExecutor()

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

    @pytest.mark.asyncio
    async def test_output_within_limit_not_truncated(self) -> None:
        """输出在限制内时不被截断。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-truncate-2",
            config={
                "code": "print('short')",
                "max_output_bytes": 1024,
            },
            context={},
        )

        assert result["success"] is True
        assert "已截断" not in result["stdout"]
        assert "short" in result["stdout"]


class TestPythonTaskExecutorTruncateOutputMethod:
    """_truncate_output() 静态方法单元测试。"""

    def test_no_truncation_needed(self) -> None:
        """输出未超限时原样返回。"""
        result = PythonTaskExecutor._truncate_output("hello", 100)
        assert result == "hello"

    def test_truncation_applied(self) -> None:
        """输出超限时包含截断提示信息。"""
        long_text = "x" * 200
        result = PythonTaskExecutor._truncate_output(long_text, 100)

        assert "已截断" in result
        assert "200" in result  # 原始字节数
        assert "100" in result  # 限制字节数

    def test_empty_output(self) -> None:
        """空字符串不截断。"""
        result = PythonTaskExecutor._truncate_output("", 100)
        assert result == ""

    def test_exact_boundary(self) -> None:
        """输出恰好等于限制时不截断。"""
        text = "abc"  # 3 字节
        result = PythonTaskExecutor._truncate_output(text, 3)
        assert result == "abc"

    def test_exceeds_by_one(self) -> None:
        """输出超过限制 1 字节时触发截断。"""
        text = "abcd"  # 4 字节
        result = PythonTaskExecutor._truncate_output(text, 3)

        assert "已截断" in result
        assert "4" in result


class TestPythonTaskExecutorBuiltInExecution:
    """无沙箱降级模式（内置执行）测试。"""

    @pytest.mark.asyncio
    async def test_computation_success(self) -> None:
        """无沙箱时纯计算代码执行成功。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-builtin-1",
            config={"code": "data = [1, 2, 3, 4, 5]\ntotal = sum(data)\nprint(total)"},
            context={},
        )

        assert result["success"] is True
        assert "15" in result["stdout"]
        assert result["sandbox_available"] is False

    @pytest.mark.asyncio
    async def test_syntax_error(self) -> None:
        """无沙箱时代码语法错误返回错误。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-builtin-2",
            config={"code": "def broken("},
            context={},
        )

        assert result["success"] is False
        assert result["stderr"] != ""
        # 语法错误被 AST 安全检查器拦截
        assert "语法错误" in result["stderr"] or "SyntaxError" in result["stderr"]

    @pytest.mark.asyncio
    async def test_dangerous_import_blocked(self) -> None:
        """无沙箱时 import os 被内置安全检查拦截。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-builtin-3",
            config={"code": "import os\nprint(os.getcwd())"},
            context={},
        )

        assert result["success"] is False
        assert "os" in result["stderr"]

    @pytest.mark.asyncio
    async def test_runtime_exception(self) -> None:
        """代码 raise Exception 返回错误信息。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-builtin-4",
            config={"code": "raise Exception('something went wrong')"},
            context={},
        )

        assert result["success"] is False
        assert result["stderr"] != ""
        assert "something went wrong" in result["stderr"]


class TestPythonTaskExecutorExecutionTimeMs:
    """execution_time_ms 字段测试。"""

    @pytest.mark.asyncio
    async def test_result_contains_execution_time_ms(self) -> None:
        """result 包含 execution_time_ms 字段且为非负数。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-perf-1",
            config={"code": "print('hello')"},
            context={},
        )

        assert "execution_time_ms" in result
        assert isinstance(result["execution_time_ms"], float)
        assert result["execution_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_execution_time_ms_present_on_failure(self) -> None:
        """执行失败时 result 仍包含 execution_time_ms。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-perf-2",
            config={"code": "raise ValueError('test error')"},
            context={},
        )

        assert "execution_time_ms" in result
        assert isinstance(result["execution_time_ms"], float)
        assert result["execution_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_execution_time_ms_present_on_timeout(self) -> None:
        """超时时 result 仍包含 execution_time_ms。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-perf-3",
            config={
                "code": "while True:\n    pass",
                "timeout": 0.5,
            },
            context={},
        )

        assert "execution_time_ms" in result
        assert isinstance(result["execution_time_ms"], float)
        assert result["execution_time_ms"] >= 0


class TestPythonTaskExecutorWithSandbox:
    """有沙箱时的执行路径测试。"""

    @pytest.mark.asyncio
    async def test_sandbox_execution_success(self) -> None:
        """有沙箱且无安全检查方法时直接执行。"""
        mock_sandbox = MagicMock()
        mock_exec_result = MagicMock()
        mock_exec_result.stdout = "sandbox output\n"
        mock_exec_result.stderr = ""
        mock_exec_result.exit_code = 0
        mock_sandbox.execute = AsyncMock(return_value=mock_exec_result)
        # 不设置 check_safety 属性，跳过安全检查

        executor = PythonTaskExecutor(sandbox_executor=mock_sandbox)

        result = await executor.execute(
            node_id="py-sandbox-1",
            config={"code": "print('test')"},
            context={},
        )

        assert result["success"] is True
        assert result["sandbox_available"] is True
        assert "sandbox output" in result["stdout"]

    @pytest.mark.asyncio
    async def test_sandbox_execution_failure(self) -> None:
        """有沙箱执行失败时 success=False。"""
        mock_sandbox = MagicMock()
        mock_exec_result = MagicMock()
        mock_exec_result.stdout = ""
        mock_exec_result.stderr = "error from sandbox"
        mock_exec_result.exit_code = 1
        mock_sandbox.execute = AsyncMock(return_value=mock_exec_result)

        executor = PythonTaskExecutor(sandbox_executor=mock_sandbox)

        result = await executor.execute(
            node_id="py-sandbox-2",
            config={"code": "bad code"},
            context={},
        )

        assert result["success"] is False
        assert result["sandbox_available"] is True
        assert "error from sandbox" in result["stderr"]

    @pytest.mark.asyncio
    async def test_sandbox_timeout(self) -> None:
        """沙箱执行超时时返回错误。"""
        mock_sandbox = MagicMock()
        mock_sandbox.execute = AsyncMock(side_effect=TimeoutError("sandbox timeout"))
        # 不设置 check_safety 属性

        executor = PythonTaskExecutor(sandbox_executor=mock_sandbox)

        result = await executor.execute(
            node_id="py-sandbox-3",
            config={
                "code": "print('slow')",
                "timeout": 1.0,
            },
            context={},
        )

        assert result["success"] is False
        assert "超时" in result["stderr"]
        assert result["sandbox_available"] is True


class TestPythonTaskExecutorContext:
    """执行上下文访问测试。"""

    @pytest.mark.asyncio
    async def test_code_can_access_context(self) -> None:
        """代码可以通过 context 变量访问上游数据。"""
        executor = PythonTaskExecutor()

        result = await executor.execute(
            node_id="py-ctx-1",
            config={"code": "print(context['query_result'])"},
            context={"query_result": "SELECT * FROM users"},
        )

        assert result["success"] is True
        assert "SELECT * FROM users" in result["stdout"]


class TestPythonTaskExecutorHealthCheck:
    """健康检查测试。"""

    @pytest.mark.asyncio
    async def test_health_check_returns_true(self) -> None:
        """健康检查默认返回 True。"""
        executor = PythonTaskExecutor()
        result = await executor.health_check()
        assert result is True
