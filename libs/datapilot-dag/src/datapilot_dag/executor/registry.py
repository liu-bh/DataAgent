"""执行器注册表。

根据 TaskType 分发到对应的任务执行器实例。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from datapilot_dag.executor.llm_executor import LLMTaskExecutor
from datapilot_dag.executor.python_executor import PythonTaskExecutor
from datapilot_dag.executor.sql_executor import SQLTaskExecutor

if TYPE_CHECKING:
    from datapilot_dag.executor.base import BaseTaskExecutor
    from datapilot_llm.router import LLMRouter
    from datapilot_sandbox.executor import SandboxExecutor

logger = structlog.get_logger(__name__)


class ExecutorRegistry:
    """任务执行器注册表。

    管理所有可用的任务执行器，根据 TaskType 查找并返回对应的执行器实例。

    支持的 TaskType:
    - sql: SQL 查询执行器
    - llm: LLM 推理执行器
    - python: Python 代码执行器（Sprint 7）
    """

    def __init__(self) -> None:
        self._executors: dict[str, BaseTaskExecutor] = {}

    def register(self, task_type: str, executor: BaseTaskExecutor) -> None:
        """注册任务执行器。

        Args:
            task_type: 任务类型标识符。
            executor: 执行器实例。
        """
        if task_type in self._executors:
            logger.warning(
                "executor_overridden",
                task_type=task_type,
                old_executor=type(self._executors[task_type]).__name__,
                new_executor=type(executor).__name__,
            )
        self._executors[task_type] = executor
        logger.info(
            "executor_registered",
            task_type=task_type,
            executor=type(executor).__name__,
        )

    def get(self, task_type: str) -> BaseTaskExecutor:
        """获取指定类型的任务执行器。

        Args:
            task_type: 任务类型标识符。

        Returns:
            对应的任务执行器实例。

        Raises:
            KeyError: 未找到对应类型的执行器。
        """
        executor = self._executors.get(task_type)
        if executor is None:
            available = list(self._executors.keys())
            raise KeyError(f"未找到任务类型 '{task_type}' 对应的执行器，可用类型: {available}")
        return executor

    def has(self, task_type: str) -> bool:
        """检查是否注册了指定类型的执行器。

        Args:
            task_type: 任务类型标识符。

        Returns:
            是否已注册。
        """
        return task_type in self._executors

    def list_types(self) -> list[str]:
        """列出所有已注册的任务类型。

        Returns:
            任务类型列表。
        """
        return list(self._executors.keys())

    def register_defaults(
        self,
        llm_router: LLMRouter | None = None,
        query_base_url: str = "http://localhost:8003",
        sandbox_executor: SandboxExecutor | None = None,
    ) -> None:
        """注册所有默认执行器。

        Args:
            llm_router: LLMRouter 实例，可选。
            query_base_url: query-executor-service 基础 URL。
            sandbox_executor: SandboxExecutor 实例，可选。
                传入后 Python 执行器将使用沙箱运行代码。
        """
        self.register("sql", SQLTaskExecutor(base_url=query_base_url))
        self.register("llm", LLMTaskExecutor(llm_router=llm_router))
        self.register("python", PythonTaskExecutor(sandbox_executor=sandbox_executor))
        logger.info(
            "default_executors_registered",
            query_base_url=query_base_url,
            llm_available=llm_router is not None,
            sandbox_available=sandbox_executor is not None,
        )
