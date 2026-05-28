"""异步任务管理器。

使用内存字典存储任务状态，通过 asyncio.Lock 保证并发安全。
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import structlog

from datapilot_queryexec.executor.models import QueryTask, TaskStatus

logger = structlog.get_logger(__name__)


class AsyncTaskManager:
    """内存中的异步任务管理器。

    维护一个 task_id -> QueryTask 的字典，提供任务的创建、查询、状态更新、
    取消和清理功能。所有写操作通过 asyncio.Lock 保证并发安全。
    """

    def __init__(self) -> None:
        self._tasks: dict[str, QueryTask] = {}
        self._lock = asyncio.Lock()

    async def create_task(
        self,
        sql: str,
        dialect: str = "mysql",
        datasource_id: str = "",
        tenant_id: str = "",
    ) -> QueryTask:
        """创建新的异步查询任务。

        Args:
            sql: 待执行的 SQL 语句。
            dialect: SQL 方言。
            datasource_id: 数据源 ID。
            tenant_id: 租户 ID。

        Returns:
            创建的 QueryTask 实例。
        """
        task = QueryTask(
            task_id=str(uuid.uuid4()),
            sql=sql,
            dialect=dialect,
            datasource_id=datasource_id,
            tenant_id=tenant_id,
        )
        async with self._lock:
            self._tasks[task.task_id] = task

        logger.info(
            "任务已创建",
            task_id=task.task_id,
            dialect=dialect,
            datasource_id=datasource_id,
            tenant_id=tenant_id,
        )
        return task

    async def get_task(self, task_id: str) -> QueryTask | None:
        """根据 task_id 获取任务。

        Args:
            task_id: 任务唯一标识。

        Returns:
            QueryTask 实例，不存在时返回 None。
        """
        return self._tasks.get(task_id)

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: dict | None = None,
        error: str = "",
    ) -> None:
        """更新任务状态。

        Args:
            task_id: 任务唯一标识。
            status: 新的任务状态。
            result: 查询结果（可选）。
            error: 错误信息（可选）。
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                logger.warning("更新状态时任务不存在", task_id=task_id)
                return

            now = datetime.now(UTC)
            task.status = status

            if status == TaskStatus.RUNNING and task.started_at is None:
                task.started_at = now

            if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                task.completed_at = now
                if task.started_at is not None:
                    task.execution_time_ms = (
                        task.completed_at - task.started_at
                    ).total_seconds() * 1000

            if result is not None:
                task.result = result

            if error:
                task.error = error

        logger.info(
            "任务状态已更新",
            task_id=task_id,
            status=status.value,
            execution_time_ms=task.execution_time_ms,
        )

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务。

        仅当任务处于 PENDING 或 RUNNING 状态时可取消。

        Args:
            task_id: 任务唯一标识。

        Returns:
            是否取消成功。
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False

            if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now(UTC)
                if task.started_at is not None:
                    task.execution_time_ms = (
                        task.completed_at - task.started_at
                    ).total_seconds() * 1000

                logger.info("任务已取消", task_id=task_id)
                return True

            return False

    async def cleanup_completed(self, max_age_seconds: int = 3600) -> int:
        """清理已完成的过期任务。

        Args:
            max_age_seconds: 任务保留时长（秒），默认 3600。

        Returns:
            清理的任务数量。
        """
        now = datetime.now(UTC)
        removed_count = 0

        async with self._lock:
            to_remove: list[str] = []
            for task_id, task in self._tasks.items():
                if (
                    task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
                    and task.completed_at is not None
                ):
                    age = (now - task.completed_at).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(task_id)

            for task_id in to_remove:
                del self._tasks[task_id]
                removed_count += 1

        if removed_count > 0:
            logger.info("已清理过期任务", count=removed_count)

        return removed_count
