"""沙箱执行器抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datapilot_sandbox.models import SandboxConfig, SandboxInfo, SandboxResult


class SandboxExecutor(ABC):
    """Python 代码沙箱执行器抽象接口。

    所有沙箱实现（本地子进程 / K8s Pod 等）均需继承此类，
    并实现 execute、health_check、get_info 三个核心方法。
    """

    @abstractmethod
    async def execute(self, code: str, config: SandboxConfig | None = None) -> SandboxResult:
        """在沙箱中执行 Python 代码。

        Args:
            code: 待执行的 Python 代码。
            config: 执行配置，为空则使用默认配置。

        Returns:
            沙箱执行结果。
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """检查沙箱环境是否健康。

        Returns:
            沙箱是否可用。
        """

    @abstractmethod
    async def get_info(self) -> SandboxInfo:
        """获取沙箱环境信息。

        Returns:
            沙箱环境信息。
        """
