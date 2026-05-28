"""本地进程沙箱执行器。

使用子进程执行 Python 代码，通过以下方式保证安全：
1. AST 级代码安全检查（禁止危险操作）
2. subprocess 隔离（独立进程）
3. resource 模块限制内存
4. asyncio.wait_for 超时控制
5. stdout/stderr 管道输出 + 截断
"""

from __future__ import annotations

from datapilot_sandbox.models import (
    CodeSecurityIssue,
    SandboxConfig,
    SandboxInfo,
    SandboxResult,
    SandboxStatus,
    SecurityLevel,
)
from datapilot_sandbox.sandbox import SandboxExecutor
from datapilot_sandbox.security import CodeSecurityChecker

from .environment import SandboxEnvironment
from .output import OutputTruncator
from .timeout import ProcessTimeout

# 默认禁止在沙箱运行时导入的模块
_DEFAULT_FORBIDDEN_MODULES: list[str] = [
    "os",
    "subprocess",
    "shutil",
    "sys",
    "importlib",
    "ctypes",
    "multiprocessing",
    "threading",
    "signal",
    "socket",
    "http",
    "urllib",
    "ftplib",
    "smtplib",
    "telnetlib",
]


class LocalProcessSandbox(SandboxExecutor):
    """本地进程沙箱执行器。

    使用子进程执行 Python 代码，通过以下方式保证安全：
    1. AST 级代码安全检查（禁止危险操作）
    2. subprocess 隔离（独立进程）
    3. resource 模块限制内存
    4. asyncio.wait_for 超时控制
    5. stdout/stderr 管道输出 + 截断

    Attributes:
        default_config: 默认执行配置。
    """

    def __init__(self, default_config: SandboxConfig | None = None) -> None:
        """初始化本地进程沙箱。

        Args:
            default_config: 默认执行配置，为 None 时使用 SandboxConfig 默认值。
        """
        self.default_config = default_config or SandboxConfig()
        self._security_checker = CodeSecurityChecker()
        self._environment = SandboxEnvironment.detect()

    async def execute(
        self,
        code: str,
        config: SandboxConfig | None = None,
    ) -> SandboxResult:
        """执行 Python 代码。

        流程：
        1. 安全检查（CodeSecurityChecker）
        2. 构建安全的执行环境变量（限制 Python 路径）
        3. 预处理代码（注入内存限制、禁止危险导入的运行时 hook）
        4. 执行子进程
        5. 截断输出
        6. 返回结果

        Args:
            code: 要执行的 Python 代码。
            config: 执行配置，为 None 时使用默认配置。

        Returns:
            执行结果。
        """
        effective_config = config or self.default_config

        # 1. 安全检查
        security_issues = self._check_security(code)
        error_issues = [issue for issue in security_issues if issue.level == SecurityLevel.ERROR]
        if error_issues:
            return SandboxResult(
                success=False,
                status=SandboxStatus.SECURITY_ERROR,
                return_code=-1,
                stdout="",
                stderr="",
                execution_time_ms=0.0,
                security_issues=security_issues,
            )

        # 2. 构建安全前缀 + 合并代码
        prelude = self._build_prelude(effective_config)
        full_code = prelude + code

        # 3. 构建执行环境变量
        extra_env: dict[str, str] = {}
        extra_env.update(effective_config.extra_env)
        extra_env["PYTHONDONTWRITEBYTECODE"] = "1"
        extra_env["PYTHONDONTIMPORTSITE"] = "1"
        extra_env["PYTHONNOUSERSITE"] = "1"

        # 4. 执行子进程
        timeout = ProcessTimeout(timeout_seconds=effective_config.timeout_seconds)
        returncode, stdout, stderr, elapsed_ms = await timeout.run(
            code=full_code,
            extra_env=extra_env,
        )

        # 5. 截断输出
        truncator = OutputTruncator(max_bytes=effective_config.max_output_bytes)
        truncated_stdout, stdout_truncated = truncator.truncate(stdout)
        truncated_stderr, stderr_truncated = truncator.truncate(stderr)
        is_truncated = stdout_truncated or stderr_truncated

        # 6. 确定状态
        if returncode == -1:
            status = SandboxStatus.TIMEOUT
        elif returncode == 0:
            status = SandboxStatus.SUCCESS
        else:
            status = SandboxStatus.FAILED

        return SandboxResult(
            success=(status == SandboxStatus.SUCCESS),
            status=status,
            return_code=returncode,
            stdout=truncated_stdout.decode("utf-8", errors="replace"),
            stderr=truncated_stderr.decode("utf-8", errors="replace"),
            output_bytes=len(stdout) + len(stderr),
            execution_time_ms=elapsed_ms,
            truncated=is_truncated,
            security_issues=security_issues,
        )

    async def health_check(self) -> bool:
        """检查沙箱是否可用（Python 解释器是否存在）。

        Returns:
            沙箱可用时返回 True。
        """
        try:
            timeout = ProcessTimeout(timeout_seconds=5.0)
            returncode, _, _, _ = await timeout.run(code="print('ok')")
            return returncode == 0
        except Exception:
            return False

    async def get_info(self) -> SandboxInfo:
        """获取沙箱环境信息。

        Returns:
            包含 Python 版本、平台和可用模块的沙箱信息。
        """
        return SandboxInfo(
            available=True,
            python_version=self._environment.python_version,
            platform=self._environment.platform,
            available_modules=self._environment.available_modules,
            max_memory_mb=self.default_config.memory_limit_mb,
            max_cpu_cores=self.default_config.cpu_limit,
            sandbox_type="local",
        )

    def _build_prelude(self, config: SandboxConfig) -> str:
        """构建安全前缀代码。

        注入运行时保护：
        - import hook 拦截禁止模块
        - resource.setrlimit 限制内存
        - 禁止 exec / eval

        Args:
            config: 执行配置。

        Returns:
            安全前缀代码字符串。
        """
        forbidden = config.forbidden_modules or _DEFAULT_FORBIDDEN_MODULES
        forbidden_repr = repr(forbidden)
        memory_mb = config.memory_limit_mb

        prelude = f"""
import sys
import importlib
import io

# 内存限制（仅在支持 resource 模块的平台上）
try:
    import resource
    resource.setrlimit(resource.RLIMIT_AS, ({memory_mb} * 1024 * 1024, {memory_mb} * 1024 * 1024))
except (ImportError, ValueError, OSError):
    pass

# 禁止危险 import 的 hook
_original_import = __builtins__.__import__
def _safe_import(name, *args, **kwargs):
    forbidden = {forbidden_repr}
    for f in forbidden:
        if name == f or name.startswith(f + '.'):
            raise ImportError(f"模块 {{name}} 在沙箱中禁止使用")
    return _original_import(name, *args, **kwargs)

__builtins__.__import__ = _safe_import
__builtins__.exec = None  # 禁止 exec
__builtins__.eval = None  # 禁止 eval
"""
        return prelude

    def _check_security(self, code: str) -> list[CodeSecurityIssue]:
        """执行安全检查，如果有 error 级别问题则拒绝执行。

        Args:
            code: 要检查的 Python 代码。

        Returns:
            安全问题列表。
        """
        return self._security_checker.check(code)
