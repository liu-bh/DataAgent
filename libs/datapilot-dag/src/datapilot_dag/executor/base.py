"""任务执行器基类。

定义任务执行器的统一接口，所有具体执行器都需继承此基类。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTaskExecutor(ABC):
    """任务执行器基类。

    提供执行、取消和健康检查的标准接口。
    """

    @abstractmethod
    async def execute(self, node_id: str, config: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行任务，返回结果。

        Args:
            node_id: 节点标识符。
            config: 任务配置，包含执行所需参数。
            context: 执行上下文，包含上游节点的输出。

        Returns:
            任务执行结果。

        Raises:
            Exception: 执行失败时抛出异常。
        """

    @abstractmethod
    async def cancel(self, node_id: str) -> bool:
        """取消正在执行的任务。

        Args:
            node_id: 节点标识符。

        Returns:
            是否成功取消。
        """

    async def health_check(self) -> bool:
        """健康检查。

        Returns:
            True 表示执行器健康可用。
        """
        return True
