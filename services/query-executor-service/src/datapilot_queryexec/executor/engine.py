"""查询执行引擎。

负责同步/异步 SQL 执行，协调连接器创建、SQL 执行和结果格式化。
未配置 connector_factory 时使用 mock 执行器返回占位结果。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

import structlog

from datapilot_queryexec.executor.formatter import ResultFormatter
from datapilot_queryexec.executor.models import ExecuteRequest, QueryTask, TaskStatus
from datapilot_queryexec.executor.task_manager import AsyncTaskManager

logger = structlog.get_logger(__name__)

# 连接器工厂类型：接收 (sql, dialect, datasource_id) 返回 (columns, rows)
ConnectorResult = tuple[list[str], list[dict]]
ConnectorFactory = Callable[
    [str, str, str],
    Coroutine[Any, Any, ConnectorResult],
]


class QueryEngine:
    """查询执行引擎。

    Args:
        task_manager: 异步任务管理器实例。
        connector_factory: 可选的连接器工厂函数。未配置时使用 mock 执行器。
    """

    def __init__(
        self,
        task_manager: AsyncTaskManager,
        connector_factory: ConnectorFactory | None = None,
    ) -> None:
        self._task_manager = task_manager
        self._connector_factory = connector_factory

    async def execute_sync(self, request: ExecuteRequest) -> QueryTask:
        """同步执行 SQL 查询。

        创建任务、立即执行并返回结果。

        Args:
            request: 执行请求。

        Returns:
            包含结果的 QueryTask。
        """
        task = await self._task_manager.create_task(
            sql=request.sql,
            dialect=request.dialect,
            datasource_id=request.datasource_id,
            tenant_id=request.tenant_id,
        )
        await self._run_task(task)
        return task

    async def execute_async(self, request: ExecuteRequest) -> QueryTask:
        """提交异步执行任务。

        创建任务并以 asyncio.Task 在后台执行，立即返回 task_id。

        Args:
            request: 执行请求。

        Returns:
            包含 task_id 的 QueryTask（状态为 PENDING）。
        """
        task = await self._task_manager.create_task(
            sql=request.sql,
            dialect=request.dialect,
            datasource_id=request.datasource_id,
            tenant_id=request.tenant_id,
        )
        # 在后台异步执行
        import asyncio

        asyncio.create_task(self._run_task(task))

        logger.info("异步任务已提交", task_id=task.task_id)
        return task

    async def get_result(self, task_id: str) -> QueryTask | None:
        """获取异步任务结果。

        Args:
            task_id: 任务唯一标识。

        Returns:
            QueryTask 实例，不存在时返回 None。
        """
        return await self._task_manager.get_task(task_id)

    async def _run_task(self, task: QueryTask) -> None:
        """内部执行逻辑。

        流程：更新状态为 RUNNING -> 创建连接器执行 SQL -> 格式化结果 -> 更新状态。
        如果 connector_factory 未配置，使用 mock 执行器返回占位结果。

        Args:
            task: 待执行的查询任务。
        """
        await self._task_manager.update_task_status(task.task_id, TaskStatus.RUNNING)

        try:
            columns: list[str]
            rows: list[dict]

            if self._connector_factory is not None:
                columns, rows = await self._connector_factory(
                    task.sql, task.dialect, task.datasource_id
                )
            else:
                # Mock 执行器：返回占位结果
                logger.info(
                    "使用 mock 执行器",
                    task_id=task.task_id,
                    sql=task.sql[:100],
                )
                columns, rows = self._mock_execute(task.sql)

            # 限制最大返回行数
            max_rows = 10000
            original_count = len(rows)
            if original_count > max_rows:
                rows = rows[:max_rows]
                logger.warning(
                    "结果行数超过限制，已截断",
                    task_id=task.task_id,
                    original_count=original_count,
                    max_rows=max_rows,
                )

            # 格式化结果为 JSON 格式存储
            result = ResultFormatter.to_json(columns, rows)
            await self._task_manager.update_task_status(
                task.task_id,
                TaskStatus.COMPLETED,
                result=result,
            )

        except Exception as e:
            logger.error(
                "任务执行失败",
                task_id=task.task_id,
                error=str(e),
            )
            await self._task_manager.update_task_status(
                task.task_id,
                TaskStatus.FAILED,
                error=str(e),
            )

    @staticmethod
    def _mock_execute(sql: str) -> tuple[list[str], list[dict]]:
        """Mock 执行器，返回占位结果。

        Args:
            sql: SQL 语句（用于日志记录）。

        Returns:
            占位的 (列名列表, 行数据列表)。
        """
        return (
            ["mock_column"],
            [{"mock_column": f"mock result for: {sql[:50]}"}],
        )
