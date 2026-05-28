"""Python Sandbox 任务执行器（Sprint 7 实现）。

当前为 stub 实现，Sprint 7 将接入安全沙箱执行 Python 代码。
"""

from __future__ import annotations

from typing import Any

import structlog

from datapilot_dag.executor.base import BaseTaskExecutor

logger = structlog.get_logger(__name__)


class PythonTaskExecutor(BaseTaskExecutor):
    """Python Sandbox 任务执行器。

    Sprint 7 实现：在安全沙箱中执行用户提供的 Python 代码。
    当前为 stub 实现，任何执行请求都会抛出 NotImplementedError。
    """

    async def execute(self, node_id: str, config: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行 Python 代码（当前为 stub）。

        Args:
            node_id: 节点标识符。
            config: 任务配置，包含：
                - code: str — Python 代码
                - timeout: float — 执行超时（秒）
            context: 执行上下文。

        Returns:
            代码执行结果。

        Raises:
            NotImplementedError: 当前版本不支持 Python 执行。
        """
        logger.warning(
            "python_executor_not_implemented",
            node_id=node_id,
            message="Python Sandbox 执行器将在 Sprint 7 实现",
        )
        raise NotImplementedError(
            "Python Sandbox 执行器将在 Sprint 7 实现，"
            f"节点 {node_id} 的 Python 执行任务暂不支持"
        )

    async def cancel(self, node_id: str) -> bool:
        """取消 Python 任务。

        Args:
            node_id: 节点标识符。

        Returns:
            True，当前始终返回成功。
        """
        logger.debug("python_executor_cancel", node_id=node_id)
        return True
