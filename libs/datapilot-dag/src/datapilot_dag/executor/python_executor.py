"""Python Sandbox 任务执行器。

在安全沙箱中执行用户提供的 Python 代码，支持超时控制、输出截断和安全检查。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog

from datapilot_dag.executor.base import BaseTaskExecutor

if TYPE_CHECKING:
    from datapilot_sandbox.executor import SandboxExecutor

logger = structlog.get_logger(__name__)

# 默认常量
_DEFAULT_TIMEOUT: float = 30.0
_DEFAULT_MAX_OUTPUT_BYTES: int = 64 * 1024  # 64KB


class PythonTaskExecutor(BaseTaskExecutor):
    """Python 任务执行器（通过 Sandbox）。

    在安全沙箱中执行用户提供的 Python 代码，支持：
    - 超时控制
    - 输出大小限制
    - 安全检查（依赖沙箱提供的安全检查器）
    - 无沙箱时的降级处理

    Attributes:
        _sandbox_executor: SandboxExecutor 实例，可选。
        _cancelled_tasks: 已取消的任务节点 ID 集合。
    """

    def __init__(self, sandbox_executor: SandboxExecutor | None = None) -> None:
        """初始化 Python 任务执行器。

        Args:
            sandbox_executor: SandboxExecutor 实例。如果未提供，
                将在首次执行时尝试延迟导入 LocalProcessSandbox。
        """
        self._sandbox_executor = sandbox_executor
        self._cancelled_tasks: set[str] = set()

    async def execute(
        self,
        node_id: str,
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """在安全沙箱中执行 Python 代码。

        Args:
            node_id: 节点标识符。
            config: 任务配置，包含：
                - code: str — Python 代码
                - timeout: float — 执行超时（秒），默认 30
                - max_output_bytes: int — 输出大小限制（字节），默认 65536
            context: 执行上下文。

        Returns:
            执行结果字典，包含：
            - stdout: str — 标准输出
            - stderr: str — 标准错误
            - success: bool — 是否执行成功
            - execution_time_ms: float — 执行耗时（毫秒）
            - sandbox_available: bool — 沙箱是否可用

        Raises:
            RuntimeError: 节点已被取消。
            ValueError: 缺少必要参数。
        """
        if node_id in self._cancelled_tasks:
            raise RuntimeError(f"节点 {node_id} 已被取消")

        # 提取配置参数
        code: str = config.get("code", "")
        if not code:
            raise ValueError(f"节点 {node_id} 缺少必要参数 'code'")

        timeout: float = config.get("timeout", _DEFAULT_TIMEOUT)
        max_output_bytes: int = config.get("max_output_bytes", _DEFAULT_MAX_OUTPUT_BYTES)

        logger.debug(
            "python_executor_execute",
            node_id=node_id,
            code_length=len(code),
            timeout=timeout,
            max_output_bytes=max_output_bytes,
        )

        start_time = time.perf_counter()
        sandbox = self._get_sandbox()

        try:
            # 如果没有沙箱，使用内置的受限执行
            if sandbox is None:
                logger.warning(
                    "python_executor_no_sandbox",
                    node_id=node_id,
                    message="未配置沙箱执行器，使用内置受限执行",
                )
                result = await self._execute_without_sandbox(
                    code=code,
                    timeout=timeout,
                    max_output_bytes=max_output_bytes,
                    context=context,
                )
            else:
                # 安全检查
                if hasattr(sandbox, "check_safety"):
                    safety_result = sandbox.check_safety(code)
                    if not safety_result.is_safe:
                        logger.warning(
                            "python_executor_safety_check_failed",
                            node_id=node_id,
                            violations=getattr(safety_result, "violations", []),
                        )
                        return {
                            "stdout": "",
                            "stderr": f"代码安全检查未通过: {getattr(safety_result, 'violations', '未知原因')}",
                            "success": False,
                            "execution_time_ms": round(
                                (time.perf_counter() - start_time) * 1000, 2
                            ),
                            "sandbox_available": True,
                        }

                # 在沙箱中执行代码
                exec_result = await sandbox.execute(
                    code=code,
                    timeout=timeout,
                    max_output_bytes=max_output_bytes,
                )
                result = {
                    "stdout": self._truncate_output(exec_result.stdout, max_output_bytes),
                    "stderr": self._truncate_output(exec_result.stderr, max_output_bytes),
                    "success": exec_result.exit_code == 0,
                    "execution_time_ms": round((time.perf_counter() - start_time) * 1000, 2),
                    "sandbox_available": True,
                }

            execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
            result["execution_time_ms"] = execution_time_ms

            log_fn = logger.info if result["success"] else logger.warning
            log_fn(
                "python_executor_completed",
                node_id=node_id,
                success=result["success"],
                execution_time_ms=execution_time_ms,
                sandbox_available=result["sandbox_available"],
            )

            return result

        except TimeoutError:
            logger.warning(
                "python_executor_timeout",
                node_id=node_id,
                timeout=timeout,
            )
            return {
                "stdout": "",
                "stderr": f"代码执行超时（{timeout}秒）",
                "success": False,
                "execution_time_ms": round((time.perf_counter() - start_time) * 1000, 2),
                "sandbox_available": sandbox is not None,
            }
        except Exception as exc:
            logger.error(
                "python_executor_failed",
                node_id=node_id,
                error=str(exc),
            )
            return {
                "stdout": "",
                "stderr": str(exc),
                "success": False,
                "execution_time_ms": round((time.perf_counter() - start_time) * 1000, 2),
                "sandbox_available": sandbox is not None,
            }

    async def cancel(self, node_id: str) -> bool:
        """取消 Python 任务。

        Args:
            node_id: 节点标识符。

        Returns:
            是否成功取消。
        """
        self._cancelled_tasks.add(node_id)
        logger.info("python_executor_cancelled", node_id=node_id)
        return True

    def _get_sandbox(self) -> SandboxExecutor | None:
        """获取沙箱执行器实例。

        如果初始化时未提供，尝试延迟导入 LocalProcessSandbox。

        Returns:
            SandboxExecutor 实例或 None（不可用时）。
        """
        if self._sandbox_executor is not None:
            return self._sandbox_executor

        try:
            from datapilot_sandbox.executor import LocalProcessSandbox

            self._sandbox_executor = LocalProcessSandbox()
            logger.info(
                "python_executor_lazy_loaded_sandbox",
                message="延迟导入 LocalProcessSandbox 成功",
            )
            return self._sandbox_executor
        except ImportError:
            logger.warning(
                "python_executor_sandbox_not_available",
                message="datapilot_sandbox 不可用，将使用内置受限执行",
            )
            return None

    @staticmethod
    def _truncate_output(output: str, max_bytes: int) -> str:
        """截断输出以符合大小限制。

        Args:
            output: 原始输出字符串。
            max_bytes: 最大字节数。

        Returns:
            截断后的字符串。
        """
        encoded = output.encode("utf-8")
        if len(encoded) <= max_bytes:
            return output
        truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
        return f"{truncated}\n... [输出已截断，原始 {len(encoded)} 字节超过 {max_bytes} 字节限制]"

    async def _execute_without_sandbox(
        self,
        code: str,
        timeout: float,
        max_output_bytes: int,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """在没有沙箱时使用受限的内置执行。

        注意：这不是真正的沙箱，仅用于开发/测试环境。
        生产环境必须使用沙箱执行器。

        执行限制：
        - 禁止导入 os, subprocess, sys, shutil, signal 等危险模块
        - 超时控制通过子进程实现（支持强制终止）
        - 输出截断

        Args:
            code: Python 代码。
            timeout: 超时秒数。
            max_output_bytes: 输出大小限制。
            context: 执行上下文。

        Returns:
            执行结果字典。
        """
        import ast

        # 安全检查：禁止危险导入
        _dangerous_imports = {
            "os",
            "subprocess",
            "sys",
            "shutil",
            "signal",
            "socket",
            "ctypes",
            "importlib",
            "runpy",
            "multiprocessing",
            "threading",
            "_thread",
            "posix",
            "nt",
            "builtins",
        }

        # --- 语法和安全检查 ---
        violations: list[str] = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {
                "stdout": "",
                "stderr": "代码安全检查未通过: 代码语法错误",
                "success": False,
                "execution_time_ms": 0.0,
                "sandbox_available": False,
            }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split(".")[0]
                    if module_name in _dangerous_imports:
                        violations.append(f"禁止导入模块: {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                module_name = node.module.split(".")[0]
                if module_name in _dangerous_imports:
                    violations.append(f"禁止从模块导入: {node.module}")

        if violations:
            return {
                "stdout": "",
                "stderr": f"代码安全检查未通过: {'; '.join(violations)}",
                "success": False,
                "execution_time_ms": 0.0,
                "sandbox_available": False,
            }

        # --- 在子进程中执行代码，支持超时强制终止 ---
        return await self._run_in_subprocess(
            code=code,
            context=context,
            timeout=timeout,
            max_output_bytes=max_output_bytes,
        )

    async def _run_in_subprocess(
        self,
        code: str,
        context: dict[str, Any],
        timeout: float,
        max_output_bytes: int,
    ) -> dict[str, Any]:
        """在子进程中执行 Python 代码，超时可强制终止。

        通过 subprocess 启动子进程执行代码，避免线程无法终止的问题。

        Args:
            code: Python 代码。
            context: 执行上下文。
            timeout: 超时秒数。
            max_output_bytes: 输出大小限制。

        Returns:
            执行结果字典。
        """
        import asyncio
        import json
        import sys

        # 构建子进程的启动代码
        exec_globals_str = (
            '{"__builtins__": __builtins__, "__name__": "__datapilot_sandbox__", "context": _ctx}'
        )
        bootstrap_code = (
            "import sys, json\n"
            "_ctx = json.loads(sys.argv[1])\n"
            f"exec(compile(sys.argv[2], '<python_executor>', 'exec'), {exec_globals_str})\n"
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                bootstrap_code,
                json.dumps(context),
                code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )

                stdout_str = stdout_bytes.decode("utf-8", errors="replace")
                stderr_str = stderr_bytes.decode("utf-8", errors="replace")

                return {
                    "stdout": self._truncate_output(stdout_str, max_output_bytes),
                    "stderr": self._truncate_output(stderr_str, max_output_bytes),
                    "success": proc.returncode == 0,
                    "execution_time_ms": 0.0,
                    "sandbox_available": False,
                }

            except TimeoutError:
                proc.kill()
                await proc.wait()
                return {
                    "stdout": "",
                    "stderr": f"代码执行超时（{timeout}秒）",
                    "success": False,
                    "execution_time_ms": 0.0,
                    "sandbox_available": False,
                }

        except Exception as exc:
            return {
                "stdout": "",
                "stderr": f"{type(exc).__name__}: {exc}",
                "success": False,
                "execution_time_ms": 0.0,
                "sandbox_available": False,
            }
