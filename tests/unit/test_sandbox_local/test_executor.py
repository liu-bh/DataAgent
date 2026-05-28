"""本地进程沙箱执行器单元测试。"""

from __future__ import annotations

import pytest

from datapilot_sandbox.models import (
    SandboxConfig,
    SandboxInfo,
    SandboxStatus,
    SecurityLevel,
)
from datapilot_sandbox.local.executor import LocalProcessSandbox


class TestLocalProcessSandbox:
    """LocalProcessSandbox 测试。"""

    @pytest.fixture
    def sandbox(self) -> LocalProcessSandbox:
        """创建沙箱实例，使用短超时。"""
        return LocalProcessSandbox(
            default_config=SandboxConfig(timeout_seconds=10.0, memory_limit_mb=128)
        )

    @pytest.mark.asyncio
    async def test_safe_code_success(self, sandbox: LocalProcessSandbox) -> None:
        """测试安全代码成功执行。"""
        result = await sandbox.execute("result = 1 + 1\nprint(result)")
        assert result.status == SandboxStatus.SUCCESS
        assert result.return_code == 0
        assert "2" in result.stdout

    @pytest.mark.asyncio
    async def test_syntax_error(self, sandbox: LocalProcessSandbox) -> None:
        """测试语法错误代码。"""
        result = await sandbox.execute("this is not valid python syntax !!!")
        # 语法错误在安全检查阶段被检测为 SECURITY_ERROR
        assert result.status == SandboxStatus.SECURITY_ERROR
        assert result.return_code == -1

    @pytest.mark.asyncio
    async def test_forbidden_import_rejected(self, sandbox: LocalProcessSandbox) -> None:
        """测试禁止导入的模块被拒绝。"""
        result = await sandbox.execute("import os\nprint(os.getcwd())")
        assert result.status == SandboxStatus.SECURITY_ERROR
        assert result.return_code == -1

    @pytest.mark.asyncio
    async def test_forbidden_subprocess_rejected(self, sandbox: LocalProcessSandbox) -> None:
        """测试禁止 subprocess 模块。"""
        result = await sandbox.execute("import subprocess")
        assert result.status == SandboxStatus.SECURITY_ERROR

    @pytest.mark.asyncio
    async def test_forbidden_builtins_rejected(self, sandbox: LocalProcessSandbox) -> None:
        """测试禁止 exec 调用。"""
        result = await sandbox.execute("exec('print(1)')")
        assert result.status == SandboxStatus.SECURITY_ERROR

    @pytest.mark.asyncio
    async def test_forbidden_eval_rejected(self, sandbox: LocalProcessSandbox) -> None:
        """测试禁止 eval 调用。"""
        result = await sandbox.execute("eval('1+1')")
        assert result.status == SandboxStatus.SECURITY_ERROR

    @pytest.mark.asyncio
    async def test_timeout_handling(self) -> None:
        """测试超时处理。"""
        sandbox = LocalProcessSandbox(
            default_config=SandboxConfig(timeout_seconds=2.0)
        )
        result = await sandbox.execute(
            "import time\ntime.sleep(60)"
        )
        # 注意：exec/eval 被禁止，但 time 模块本身不在禁止列表中
        # time.sleep 应该能导入，但是 time 不在 AST 级别的禁止列表中
        # 安全前缀中会禁止 os/subprocess 等，但 time 不在其中
        # 所以 time.sleep 会执行但超时
        assert result.status == SandboxStatus.TIMEOUT
        assert result.return_code == -1

    @pytest.mark.asyncio
    async def test_output_truncation(self) -> None:
        """测试输出截断。"""
        sandbox = LocalProcessSandbox(
            default_config=SandboxConfig(
                timeout_seconds=10.0,
                max_output_bytes=100,
            )
        )
        # 生成大量输出
        code = "for i in range(10000):\n    print(f'line {i}')"
        result = await sandbox.execute(code)
        assert result.truncated is True
        assert "[output truncated]" in result.stdout

    @pytest.mark.asyncio
    async def test_empty_code(self, sandbox: LocalProcessSandbox) -> None:
        """测试空代码。"""
        result = await sandbox.execute("")
        assert result.status == SandboxStatus.SUCCESS
        assert result.return_code == 0

    @pytest.mark.asyncio
    async def test_whitespace_code(self, sandbox: LocalProcessSandbox) -> None:
        """测试纯空白代码。"""
        result = await sandbox.execute("   \n  \n  ")
        assert result.status == SandboxStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_runtime_error(self, sandbox: LocalProcessSandbox) -> None:
        """测试运行时错误。"""
        result = await sandbox.execute("x = 1 / 0")
        assert result.status == SandboxStatus.FAILED
        assert "ZeroDivisionError" in result.stderr

    @pytest.mark.asyncio
    async def test_custom_config(self, sandbox: LocalProcessSandbox) -> None:
        """测试自定义配置覆盖默认配置。"""
        custom_config = SandboxConfig(
            timeout_seconds=5.0,
            memory_limit_mb=64,
            max_output_bytes=500,
        )
        result = await sandbox.execute("print('hello')", config=custom_config)
        assert result.status == SandboxStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_math_operations(self, sandbox: LocalProcessSandbox) -> None:
        """测试数学运算。"""
        code = """
import math
result = math.sqrt(144)
print(result)
"""
        result = await sandbox.execute(code)
        assert result.status == SandboxStatus.SUCCESS
        assert "12" in result.stdout

    @pytest.mark.asyncio
    async def test_string_operations(self, sandbox: LocalProcessSandbox) -> None:
        """测试字符串操作。"""
        code = """
s = "hello"
result = s.upper() + " " + "WORLD"
print(result)
"""
        result = await sandbox.execute(code)
        assert result.status == SandboxStatus.SUCCESS
        assert "HELLO WORLD" in result.stdout

    @pytest.mark.asyncio
    async def test_forbidden_open_write_rejected(self, sandbox: LocalProcessSandbox) -> None:
        """测试禁止以写模式打开文件。"""
        result = await sandbox.execute("open('/tmp/test.txt', 'w')")
        assert result.status == SandboxStatus.SECURITY_ERROR

    @pytest.mark.asyncio
    async def test_open_read_mode_allowed(self, sandbox: LocalProcessSandbox) -> None:
        """测试以读模式打开文件允许（但可能因文件不存在而失败）。"""
        # open() 读模式不触发安全错误，但可能因文件不存在而执行失败
        result = await sandbox.execute("open('/etc/passwd', 'r')")
        # 不应返回安全错误，读模式是允许的
        assert result.status != SandboxStatus.SECURITY_ERROR

    @pytest.mark.asyncio
    async def test_health_check(self, sandbox: LocalProcessSandbox) -> None:
        """测试健康检查。"""
        is_healthy = await sandbox.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_get_info(self, sandbox: LocalProcessSandbox) -> None:
        """测试获取沙箱信息。"""
        info = await sandbox.get_info()
        assert info.available is True
        assert info.python_version != ""
        assert info.platform != ""
        assert isinstance(info.available_modules, list)
        assert len(info.available_modules) > 0

    @pytest.mark.asyncio
    async def test_execution_time_measured(self, sandbox: LocalProcessSandbox) -> None:
        """测试执行时间被正确测量。"""
        result = await sandbox.execute("print('test')")
        assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_default_config_used_when_none(self, sandbox: LocalProcessSandbox) -> None:
        """测试不传配置时使用默认配置。"""
        result = await sandbox.execute("print('default')")
        assert result.status == SandboxStatus.SUCCESS

    def test_default_config_values(self) -> None:
        """测试默认配置值正确。"""
        sandbox = LocalProcessSandbox()
        config = sandbox.default_config
        assert config.cpu_limit == 1.0
        assert config.memory_limit_mb == 512
        assert config.timeout_seconds == 30.0
        assert config.max_output_bytes == 1048576
        assert config.read_only_filesystem is True
        assert config.network_disabled is True
        assert isinstance(config.forbidden_modules, list)
        assert len(config.forbidden_modules) > 0
        assert "os" in config.forbidden_modules

    @pytest.mark.asyncio
    async def test_get_info_returns_sandbox_info(self) -> None:
        """测试 get_info() 返回 SandboxInfo 实例。"""
        sandbox = LocalProcessSandbox()
        info = await sandbox.get_info()
        assert isinstance(info, SandboxInfo)
        assert info.sandbox_type == "local"

    @pytest.mark.asyncio
    async def test_get_info_contains_environment_details(self) -> None:
        """测试 get_info() 包含完整的环境信息。"""
        sandbox = LocalProcessSandbox()
        info = await sandbox.get_info()
        assert info.available is True
        assert info.python_version != ""
        assert info.platform != ""
        assert len(info.available_modules) > 0
        assert info.max_memory_mb == sandbox.default_config.memory_limit_mb
        assert info.max_cpu_cores == sandbox.default_config.cpu_limit

    def test_build_prelude_contains_resource_setrlimit(self) -> None:
        """测试 _build_prelude() 包含 resource.setrlimit。"""
        sandbox = LocalProcessSandbox()
        config = SandboxConfig(memory_limit_mb=256)
        prelude = sandbox._build_prelude(config)
        assert "resource.setrlimit" in prelude
        assert "RLIMIT_AS" in prelude

    def test_build_prelude_contains_import_hook(self) -> None:
        """测试 _build_prelude() 包含 __import__ hook。"""
        sandbox = LocalProcessSandbox()
        config = SandboxConfig()
        prelude = sandbox._build_prelude(config)
        assert "__builtins__.__import__" in prelude
        assert "_safe_import" in prelude

    @pytest.mark.asyncio
    async def test_execute_hello_returns_success(self) -> None:
        """测试正常执行 print('hello') 返回 success。"""
        sandbox = LocalProcessSandbox()
        result = await sandbox.execute("print('hello')")
        assert result.success is True
        assert result.status == SandboxStatus.SUCCESS
        assert "hello" in result.stdout

    @pytest.mark.asyncio
    async def test_execute_dangerous_import_returns_security_error(self) -> None:
        """测试危险代码（import os）返回 security_error。"""
        sandbox = LocalProcessSandbox()
        result = await sandbox.execute("import os")
        assert result.success is False
        assert result.status == SandboxStatus.SECURITY_ERROR

    @pytest.mark.asyncio
    async def test_execute_security_issues_contain_error_level(self) -> None:
        """测试安全检查结果包含 error 级别的问题。"""
        sandbox = LocalProcessSandbox()
        result = await sandbox.execute("import os; os.system('echo test')")
        assert len(result.security_issues) > 0
        has_error = any(
            issue.level == SecurityLevel.ERROR for issue in result.security_issues
        )
        assert has_error
