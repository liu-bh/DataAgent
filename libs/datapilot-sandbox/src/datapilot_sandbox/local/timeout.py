"""进程超时控制器。

使用 asyncio.create_subprocess_exec 执行 Python 代码，
超时后强制终止进程，防止无限循环或资源耗尽。
"""

from __future__ import annotations

import asyncio
import sys
import time


class ProcessTimeout:
    """进程超时控制器。

    使用 asyncio.create_subprocess_exec 执行 Python 代码，
    超时后强制终止进程。

    Attributes:
        timeout_seconds: 执行超时时间（秒）。
    """

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        """初始化超时控制器。

        Args:
            timeout_seconds: 超时时间（秒），默认 30 秒。
        """
        if timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds 必须为正数，当前值: {timeout_seconds}")
        self.timeout_seconds = timeout_seconds

    async def run(
        self,
        code: str,
        python_path: str = sys.executable,
        extra_env: dict[str, str] | None = None,
    ) -> tuple[int, bytes, bytes, float]:
        """执行 Python 代码，返回 (returncode, stdout, stderr, execution_time_ms)。

        通过 stdin 将代码传入子进程执行，使用 -c 参数运行。
        如果超时，kill 进程并返回 (-1, b"", b"", timeout * 1000)。

        Args:
            code: 要执行的 Python 代码。
            python_path: Python 解释器路径，默认当前解释器。
            extra_env: 额外的环境变量。

        Returns:
            元组 (returncode, stdout, stderr, execution_time_ms)。
            超时时 returncode 为 -1。
        """
        import os

        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)

        # 限制 Python 搜索路径
        env["PYTHONPATH"] = ""

        start_time = time.monotonic()

        try:
            process = await asyncio.create_subprocess_exec(
                python_path,
                "-c",
                code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout_seconds,
                )
                elapsed_ms = (time.monotonic() - start_time) * 1000
                return process.returncode or 0, stdout or b"", stderr or b"", elapsed_ms

            except asyncio.TimeoutError:
                # 超时，强制终止进程
                elapsed_ms = (time.monotonic() - start_time) * 1000

                try:
                    process.kill()
                except ProcessLookupError:
                    pass

                try:
                    await process.wait()
                except Exception:
                    pass

                return -1, b"", b"", elapsed_ms

        except FileNotFoundError:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            return -1, b"", f"Python 解释器不存在: {python_path}".encode("utf-8"), elapsed_ms

        except OSError as exc:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            return -1, b"", f"进程启动失败: {exc}".encode("utf-8"), elapsed_ms
