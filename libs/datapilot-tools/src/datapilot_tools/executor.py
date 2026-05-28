"""工具执行器抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from datapilot_tools.validator import ToolParameterValidator

if TYPE_CHECKING:
    from datapilot_tools.models import ToolDefinition, ToolExecutionResult


class BaseToolExecutor(ABC):
    """工具执行器抽象基类，提供参数校验和执行接口。"""

    def __init__(self) -> None:
        self._validator = ToolParameterValidator()

    @abstractmethod
    async def execute(self, name: str, params: dict[str, Any]) -> ToolExecutionResult:
        """执行工具。

        Args:
            name: 工具名称。
            params: 工具参数。

        Returns:
            工具执行结果。
        """

    async def validate(self, name: str, params: dict[str, Any]) -> list[str]:
        """校验工具参数。

        Args:
            name: 工具名称。
            params: 工具参数。

        Returns:
            错误消息列表，空列表表示校验通过。
        """
        tool = self.get_tool(name)
        if tool is None:
            return [f"工具 '{name}' 不存在"]
        return self._validator.validate(tool, params)

    @abstractmethod
    def get_info(self) -> dict[str, Any]:
        """获取执行器信息。

        Returns:
            执行器元信息字典。
        """

    @abstractmethod
    def get_tool(self, name: str) -> ToolDefinition | None:
        """获取工具定义。

        Args:
            name: 工具名称。

        Returns:
            工具定义，不存在时返回 None。
        """
