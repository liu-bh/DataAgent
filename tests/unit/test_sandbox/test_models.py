"""Sandbox 数据模型单元测试。"""

from __future__ import annotations

from datapilot_sandbox.models import (
    CodeSecurityIssue,
    SandboxConfig,
    SandboxInfo,
    SandboxResult,
    SandboxStatus,
    SecurityLevel,
)


class TestSecurityLevel:
    """SecurityLevel 枚举测试。"""

    def test_error_value(self) -> None:
        """测试 error 级别。"""
        assert SecurityLevel.ERROR == "error"

    def test_warning_value(self) -> None:
        """测试 warning 级别。"""
        assert SecurityLevel.WARNING == "warning"

    def test_info_value(self) -> None:
        """测试 info 级别。"""
        assert SecurityLevel.INFO == "info"


class TestSandboxStatus:
    """SandboxStatus 枚举测试。"""

    def test_success_value(self) -> None:
        """测试 success 状态。"""
        assert SandboxStatus.SUCCESS == "success"

    def test_failed_value(self) -> None:
        """测试 failed 状态。"""
        assert SandboxStatus.FAILED == "failed"

    def test_timeout_value(self) -> None:
        """测试 timeout 状态。"""
        assert SandboxStatus.TIMEOUT == "timeout"

    def test_security_error_value(self) -> None:
        """测试 security_error 状态。"""
        assert SandboxStatus.SECURITY_ERROR == "security_error"


class TestSandboxConfig:
    """SandboxConfig 测试。"""

    def test_default_values(self) -> None:
        """测试默认配置值。"""
        config = SandboxConfig()
        assert config.cpu_limit == 1.0
        assert config.memory_limit_mb == 512
        assert config.timeout_seconds == 30.0
        assert config.max_output_bytes == 1048576
        assert config.allowed_modules == []
        assert config.read_only_filesystem is True
        assert config.network_disabled is True

    def test_default_forbidden_modules(self) -> None:
        """测试默认禁止模块列表不为空。"""
        config = SandboxConfig()
        assert len(config.forbidden_modules) > 0
        assert "os" in config.forbidden_modules
        assert "subprocess" in config.forbidden_modules
        assert "socket" in config.forbidden_modules

    def test_custom_values(self) -> None:
        """测试自定义配置。"""
        config = SandboxConfig(
            cpu_limit=2.0,
            memory_limit_mb=1024,
            timeout_seconds=60.0,
            max_output_bytes=2097152,
            allowed_modules=["math", "json"],
            read_only_filesystem=False,
            network_disabled=False,
        )
        assert config.cpu_limit == 2.0
        assert config.memory_limit_mb == 1024
        assert config.timeout_seconds == 60.0
        assert config.max_output_bytes == 2097152
        assert config.allowed_modules == ["math", "json"]
        assert config.read_only_filesystem is False
        assert config.network_disabled is False

    def test_allowed_modules_mutable_default(self) -> None:
        """测试 allowed_modules 默认值独立于其他实例。"""
        config1 = SandboxConfig()
        config2 = SandboxConfig()
        config1.allowed_modules.append("math")
        assert "math" not in config2.allowed_modules

    def test_extra_env_default(self) -> None:
        """测试 extra_env 默认为空字典。"""
        config = SandboxConfig()
        assert config.extra_env == {}

    def test_extra_env_custom(self) -> None:
        """测试自定义环境变量。"""
        config = SandboxConfig(extra_env={"DEBUG": "1"})
        assert config.extra_env == {"DEBUG": "1"}


class TestSandboxResult:
    """SandboxResult 测试。"""

    def test_success_result(self) -> None:
        """测试成功执行结果。"""
        result = SandboxResult(
            success=True,
            stdout="hello",
            execution_time_ms=50.0,
        )
        assert result.success is True
        assert result.stdout == "hello"
        assert result.stderr == ""
        assert result.error == ""
        assert result.execution_time_ms == 50.0
        assert result.truncated is False
        assert result.status == SandboxStatus.SUCCESS
        assert result.return_code == 0

    def test_failure_result(self) -> None:
        """测试失败执行结果。"""
        result = SandboxResult(
            success=False,
            error="TimeoutError",
            stderr="Traceback ...",
            status=SandboxStatus.FAILED,
            return_code=1,
        )
        assert result.success is False
        assert result.error == "TimeoutError"
        assert "Traceback" in result.stderr
        assert result.status == SandboxStatus.FAILED

    def test_truncated_result(self) -> None:
        """测试截断结果。"""
        result = SandboxResult(
            success=True,
            stdout="... truncated ...",
            output_bytes=2097152,
            truncated=True,
        )
        assert result.truncated is True
        assert result.output_bytes == 2097152

    def test_default_status_success(self) -> None:
        """测试默认状态为 SUCCESS。"""
        result = SandboxResult(success=True)
        assert result.status == SandboxStatus.SUCCESS

    def test_default_return_code_zero(self) -> None:
        """测试默认返回码为 0。"""
        result = SandboxResult(success=True)
        assert result.return_code == 0

    def test_security_issues_default_empty(self) -> None:
        """测试默认安全问题列表为空。"""
        result = SandboxResult(success=True)
        assert result.security_issues == []


class TestSandboxInfo:
    """SandboxInfo 测试。"""

    def test_default_values(self) -> None:
        """测试默认信息。"""
        info = SandboxInfo()
        assert info.python_version == ""
        assert info.available_modules == []
        assert info.max_memory_mb == 512
        assert info.max_cpu_cores == 1.0
        assert info.sandbox_type == "local"
        assert info.available is True
        assert info.platform == ""

    def test_k8s_pod_info(self) -> None:
        """测试 K8s Pod 沙箱信息。"""
        info = SandboxInfo(
            python_version="3.11.5",
            available_modules=["math", "json"],
            max_memory_mb=2048,
            max_cpu_cores=4.0,
            sandbox_type="k8s-pod",
            platform="linux",
        )
        assert info.python_version == "3.11.5"
        assert info.sandbox_type == "k8s-pod"
        assert info.max_cpu_cores == 4.0
        assert info.platform == "linux"


class TestCodeSecurityIssue:
    """CodeSecurityIssue 测试。"""

    def test_error_issue(self) -> None:
        """测试 error 级别问题。"""
        issue = CodeSecurityIssue(
            level=SecurityLevel.ERROR,
            line=5,
            message="禁止导入模块 'os'",
            node_type="Import",
        )
        assert issue.level == SecurityLevel.ERROR
        assert issue.line == 5
        assert issue.node_type == "Import"

    def test_warning_issue(self) -> None:
        """测试 warning 级别问题。"""
        issue = CodeSecurityIssue(
            level=SecurityLevel.WARNING,
            line=10,
            message="可疑调用 'system'",
        )
        assert issue.level == SecurityLevel.WARNING
        assert issue.node_type == ""

    def test_default_level_is_error(self) -> None:
        """测试默认级别为 ERROR。"""
        issue = CodeSecurityIssue(line=1, message="test")
        assert issue.level == SecurityLevel.ERROR

    def test_rule_field(self) -> None:
        """测试 rule 字段。"""
        issue = CodeSecurityIssue(
            level=SecurityLevel.ERROR,
            rule="dangerous-import",
            line=1,
            message="禁止导入模块 'os'",
        )
        assert issue.rule == "dangerous-import"

    def test_level_is_string_comparable(self) -> None:
        """测试 level 枚举的值与字符串一致。"""
        issue = CodeSecurityIssue(level=SecurityLevel.ERROR, line=1, message="test")
        assert issue.level.value == "error"
        assert str(issue.level.value) == "error"

    def test_all_fields_default_to_empty_or_zero(self) -> None:
        """测试所有字段默认值。"""
        issue = CodeSecurityIssue()
        assert issue.level == SecurityLevel.ERROR
        assert issue.rule == ""
        assert issue.line == 0
        assert issue.message == ""
        assert issue.node_type == ""


class TestSecurityLevelEnumeration:
    """SecurityLevel 枚举完整测试。"""

    def test_has_three_members(self) -> None:
        """SecurityLevel 应有三个成员。"""
        assert len(SecurityLevel) == 3

    def test_members_are_unique(self) -> None:
        """枚举成员值应唯一。"""
        values = [level.value for level in SecurityLevel]
        assert len(values) == len(set(values))

    def test_is_str_subclass(self) -> None:
        """SecurityLevel 应继承 str。"""
        assert issubclass(SecurityLevel, str)


class TestSandboxStatusEnumeration:
    """SandboxStatus 枚举完整测试。"""

    def test_has_four_members(self) -> None:
        """SandboxStatus 应有四个成员。"""
        assert len(SandboxStatus) == 4

    def test_members_are_unique(self) -> None:
        """枚举成员值应唯一。"""
        values = [status.value for status in SandboxStatus]
        assert len(values) == len(set(values))

    def test_is_str_subclass(self) -> None:
        """SandboxStatus 应继承 str。"""
        assert issubclass(SandboxStatus, str)


class TestSandboxResultExtended:
    """SandboxResult 扩展测试。"""

    def test_timeout_result(self) -> None:
        """测试超时执行结果。"""
        result = SandboxResult(
            success=False,
            status=SandboxStatus.TIMEOUT,
            return_code=-1,
            error="Execution timed out",
        )
        assert result.success is False
        assert result.status == SandboxStatus.TIMEOUT
        assert result.return_code == -1
        assert result.error == "Execution timed out"

    def test_security_error_result(self) -> None:
        """测试安全错误结果。"""
        result = SandboxResult(
            success=False,
            status=SandboxStatus.SECURITY_ERROR,
            security_issues=[
                CodeSecurityIssue(
                    level=SecurityLevel.ERROR,
                    rule="forbidden_import",
                    line=1,
                    message="禁止导入模块 'os'",
                    node_type="Import",
                )
            ],
        )
        assert result.status == SandboxStatus.SECURITY_ERROR
        assert len(result.security_issues) == 1
        assert result.security_issues[0].rule == "forbidden_import"

    def test_result_with_performance_metrics(self) -> None:
        """测试包含性能指标的结果。"""
        result = SandboxResult(
            success=True,
            memory_used_mb=128.5,
            cpu_time_ms=45.2,
            execution_time_ms=100.0,
            output_bytes=2048,
        )
        assert result.memory_used_mb == 128.5
        assert result.cpu_time_ms == 45.2
        assert result.execution_time_ms == 100.0
        assert result.output_bytes == 2048

    def test_result_security_issues_mutable_default(self) -> None:
        """测试 security_issues 默认值独立于其他实例。"""
        result1 = SandboxResult(success=True)
        result2 = SandboxResult(success=True)
        result1.security_issues.append(
            CodeSecurityIssue(level=SecurityLevel.ERROR, line=1, message="test"),
        )
        assert len(result2.security_issues) == 0

    def test_result_with_large_output(self) -> None:
        """测试大输出结果。"""
        large_output = "x" * 2000000
        result = SandboxResult(
            success=True,
            stdout=large_output,
            output_bytes=len(large_output),
            truncated=True,
        )
        assert len(result.stdout) == 2000000
        assert result.truncated is True


class TestSandboxConfigExtended:
    """SandboxConfig 扩展测试。"""

    def test_forbidden_modules_contains_expected_defaults(self) -> None:
        """测试默认禁止模块列表包含所有预期模块。"""
        config = SandboxConfig()
        expected_forbidden = [
            "os", "subprocess", "shutil", "sys", "importlib",
            "ctypes", "multiprocessing", "threading", "signal",
            "socket", "http", "urllib", "ftplib", "smtplib", "telnetlib",
        ]
        for module in expected_forbidden:
            assert module in config.forbidden_modules, f"应禁止模块: {module}"

    def test_forbidden_modules_mutable_default(self) -> None:
        """测试 forbidden_modules 默认值独立于其他实例。"""
        config1 = SandboxConfig()
        config2 = SandboxConfig()
        config1.forbidden_modules.append("custom_forbidden")
        assert "custom_forbidden" not in config2.forbidden_modules

    def test_extra_env_mutable_default(self) -> None:
        """测试 extra_env 默认值独立于其他实例。"""
        config1 = SandboxConfig()
        config2 = SandboxConfig()
        config1.extra_env["KEY"] = "VALUE"
        assert "KEY" not in config2.extra_env

    def test_all_numeric_limits_are_positive(self) -> None:
        """测试所有数值限制默认值为正数。"""
        config = SandboxConfig()
        assert config.cpu_limit > 0
        assert config.memory_limit_mb > 0
        assert config.timeout_seconds > 0
        assert config.max_output_bytes > 0


class TestSandboxInfoExtended:
    """SandboxInfo 扩展测试。"""

    def test_available_modules_mutable_default(self) -> None:
        """测试 available_modules 默认值独立于其他实例。"""
        info1 = SandboxInfo()
        info2 = SandboxInfo()
        info1.available_modules.append("math")
        assert "math" not in info2.available_modules

    def test_unavailable_info(self) -> None:
        """测试沙箱不可用时的信息。"""
        info = SandboxInfo(available=False)
        assert info.available is False

    def test_full_info(self) -> None:
        """测试完整沙箱信息。"""
        info = SandboxInfo(
            available=True,
            python_version="3.12.0",
            platform="linux",
            available_modules=["math", "json", "pandas", "numpy"],
            max_memory_mb=4096,
            max_cpu_cores=8.0,
            sandbox_type="k8s-pod",
        )
        assert info.available is True
        assert info.python_version == "3.12.0"
        assert info.platform == "linux"
        assert len(info.available_modules) == 4
        assert info.max_memory_mb == 4096
        assert info.max_cpu_cores == 8.0
        assert info.sandbox_type == "k8s-pod"
