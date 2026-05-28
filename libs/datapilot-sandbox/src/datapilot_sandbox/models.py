"""沙箱数据模型定义。"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class SecurityLevel(str, enum.Enum):  # noqa: UP042
    """安全检查问题级别。"""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class SandboxStatus(str, enum.Enum):  # noqa: UP042
    """沙箱执行状态。"""

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SECURITY_ERROR = "security_error"


@dataclass
class SandboxConfig:
    """沙箱执行配置。

    Attributes:
        cpu_limit: CPU 核心数上限。
        memory_limit_mb: 内存上限（MB）。
        timeout_seconds: 执行超时时间（秒）。
        max_output_bytes: 标准输出/错误最大字节数。
        allowed_modules: 允许导入的模块清单，为空则使用默认白名单。
        forbidden_modules: 禁止导入的模块清单。
        read_only_filesystem: 是否启用只读文件系统。
        network_disabled: 是否禁用网络访问。
        extra_env: 额外的环境变量。
    """

    cpu_limit: float = 1.0
    memory_limit_mb: int = 512
    timeout_seconds: float = 30.0
    max_output_bytes: int = 1048576  # 1MB
    allowed_modules: list[str] = field(default_factory=list)
    forbidden_modules: list[str] = field(
        default_factory=lambda: [
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
    )
    read_only_filesystem: bool = True
    network_disabled: bool = True
    extra_env: dict[str, str] = field(default_factory=dict)


@dataclass
class SandboxResult:
    """沙箱执行结果。

    Attributes:
        success: 执行是否成功。
        status: 执行状态枚举。
        return_code: 进程返回码，超时为 -1。
        stdout: 标准输出内容。
        stderr: 标准错误内容。
        output_bytes: 输出总字节数。
        execution_time_ms: 执行耗时（毫秒）。
        error: 错误信息（若执行失败）。
        memory_used_mb: 实际使用的内存（MB）。
        cpu_time_ms: 实际使用的 CPU 时间（毫秒）。
        truncated: 输出是否被截断。
        security_issues: 安全检查发现的问题列表。
    """

    success: bool
    status: SandboxStatus = SandboxStatus.SUCCESS
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""
    output_bytes: int = 0
    execution_time_ms: float = 0.0
    error: str = ""
    memory_used_mb: float = 0.0
    cpu_time_ms: float = 0.0
    truncated: bool = False
    security_issues: list[CodeSecurityIssue] = field(default_factory=list)  # type: ignore[name-defined]


@dataclass
class SandboxInfo:
    """沙箱环境信息。

    Attributes:
        available: 沙箱是否可用。
        python_version: Python 解释器版本。
        platform: 操作系统平台。
        available_modules: 可用模块清单。
        max_memory_mb: 最大可用内存（MB）。
        max_cpu_cores: 最大可用 CPU 核心数。
        sandbox_type: 沙箱类型（local / k8s-pod）。
    """

    available: bool = True
    python_version: str = ""
    platform: str = ""
    available_modules: list[str] = field(default_factory=list)
    max_memory_mb: int = 512
    max_cpu_cores: float = 1.0
    sandbox_type: str = "local"  # local / k8s-pod


@dataclass
class CodeSecurityIssue:
    """代码安全检查问题。

    Attributes:
        level: 严重级别（error / warning / info）。
        rule: 违反的规则标识。
        line: 问题所在行号。
        message: 问题描述。
        node_type: AST 节点类型。
    """

    level: SecurityLevel = SecurityLevel.ERROR
    rule: str = ""
    line: int = 0
    message: str = ""
    node_type: str = ""
