"""异步任务管理器单元测试。"""

import asyncio

import pytest

from datapilot_queryexec.executor.models import TaskStatus
from datapilot_queryexec.executor.task_manager import AsyncTaskManager


@pytest.fixture
def manager() -> AsyncTaskManager:
    """创建干净的 AsyncTaskManager 实例。"""
    return AsyncTaskManager()


class TestAsyncTaskManager:
    """AsyncTaskManager 测试。"""

    @pytest.mark.asyncio
    async def test_create_task(self, manager: AsyncTaskManager) -> None:
        """测试创建任务。"""
        task = await manager.create_task(
            sql="SELECT 1",
            dialect="mysql",
            datasource_id="ds-001",
            tenant_id="tenant-001",
        )
        assert task.task_id is not None
        assert len(task.task_id) > 0
        assert task.sql == "SELECT 1"
        assert task.dialect == "mysql"
        assert task.datasource_id == "ds-001"
        assert task.tenant_id == "tenant-001"
        assert task.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_create_task_unique_id(self, manager: AsyncTaskManager) -> None:
        """测试每次创建的任务 ID 唯一。"""
        task1 = await manager.create_task(sql="SELECT 1")
        task2 = await manager.create_task(sql="SELECT 2")
        assert task1.task_id != task2.task_id

    @pytest.mark.asyncio
    async def test_get_task(self, manager: AsyncTaskManager) -> None:
        """测试获取任务。"""
        created = await manager.create_task(sql="SELECT 1")
        fetched = await manager.get_task(created.task_id)
        assert fetched is not None
        assert fetched.task_id == created.task_id
        assert fetched.sql == "SELECT 1"

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, manager: AsyncTaskManager) -> None:
        """测试获取不存在的任务返回 None。"""
        result = await manager.get_task("non-existent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_task_status_running(self, manager: AsyncTaskManager) -> None:
        """测试更新任务状态为 RUNNING。"""
        task = await manager.create_task(sql="SELECT 1")
        await manager.update_task_status(task.task_id, TaskStatus.RUNNING)

        updated = await manager.get_task(task.task_id)
        assert updated is not None
        assert updated.status == TaskStatus.RUNNING
        assert updated.started_at is not None

    @pytest.mark.asyncio
    async def test_update_task_status_completed(self, manager: AsyncTaskManager) -> None:
        """测试更新任务状态为 COMPLETED。"""
        task = await manager.create_task(sql="SELECT 1")
        await manager.update_task_status(task.task_id, TaskStatus.RUNNING)
        await manager.update_task_status(
            task.task_id,
            TaskStatus.COMPLETED,
            result={"columns": ["1"], "data": [[1]]},
        )

        updated = await manager.get_task(task.task_id)
        assert updated is not None
        assert updated.status == TaskStatus.COMPLETED
        assert updated.completed_at is not None
        assert updated.execution_time_ms > 0
        assert updated.result is not None
        assert updated.result["columns"] == ["1"]

    @pytest.mark.asyncio
    async def test_update_task_status_failed(self, manager: AsyncTaskManager) -> None:
        """测试更新任务状态为 FAILED。"""
        task = await manager.create_task(sql="SELECT 1")
        await manager.update_task_status(task.task_id, TaskStatus.RUNNING)
        await manager.update_task_status(
            task.task_id,
            TaskStatus.FAILED,
            error="连接超时",
        )

        updated = await manager.get_task(task.task_id)
        assert updated is not None
        assert updated.status == TaskStatus.FAILED
        assert updated.error == "连接超时"
        assert updated.completed_at is not None
        assert updated.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_update_nonexistent_task(self, manager: AsyncTaskManager) -> None:
        """测试更新不存在的任务不抛异常。"""
        # 不应抛出异常
        await manager.update_task_status("non-existent", TaskStatus.RUNNING)

    @pytest.mark.asyncio
    async def test_cancel_pending_task(self, manager: AsyncTaskManager) -> None:
        """测试取消 PENDING 状态的任务。"""
        task = await manager.create_task(sql="SELECT 1")
        result = await manager.cancel_task(task.task_id)
        assert result is True

        updated = await manager.get_task(task.task_id)
        assert updated is not None
        assert updated.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_running_task(self, manager: AsyncTaskManager) -> None:
        """测试取消 RUNNING 状态的任务。"""
        task = await manager.create_task(sql="SELECT 1")
        await manager.update_task_status(task.task_id, TaskStatus.RUNNING)
        result = await manager.cancel_task(task.task_id)
        assert result is True

        updated = await manager.get_task(task.task_id)
        assert updated is not None
        assert updated.status == TaskStatus.CANCELLED
        assert updated.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_cancel_completed_task(self, manager: AsyncTaskManager) -> None:
        """测试取消已完成任务应返回 False。"""
        task = await manager.create_task(sql="SELECT 1")
        await manager.update_task_status(task.task_id, TaskStatus.COMPLETED)
        result = await manager.cancel_task(task.task_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self, manager: AsyncTaskManager) -> None:
        """测试取消不存在的任务返回 False。"""
        result = await manager.cancel_task("non-existent")
        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_completed(self, manager: AsyncTaskManager) -> None:
        """测试清理已完成的任务。"""
        # 创建并完成多个任务
        task1 = await manager.create_task(sql="SELECT 1")
        task2 = await manager.create_task(sql="SELECT 2")
        await manager.update_task_status(task1.task_id, TaskStatus.COMPLETED)
        await manager.update_task_status(task2.task_id, TaskStatus.FAILED)

        # 创建一个运行中的任务
        task3 = await manager.create_task(sql="SELECT 3")
        await manager.update_task_status(task3.task_id, TaskStatus.RUNNING)

        # 清理所有已完成的任务（max_age_seconds=0 立即清理）
        cleaned = await manager.cleanup_completed(max_age_seconds=0)
        assert cleaned == 2

        # 已完成的任务应被删除
        assert await manager.get_task(task1.task_id) is None
        assert await manager.get_task(task2.task_id) is None

        # 运行中的任务应保留
        assert await manager.get_task(task3.task_id) is not None

    @pytest.mark.asyncio
    async def test_cleanup_respects_max_age(self, manager: AsyncTaskManager) -> None:
        """测试清理时遵守 max_age_seconds。"""
        task = await manager.create_task(sql="SELECT 1")
        await manager.update_task_status(task.task_id, TaskStatus.COMPLETED)

        # max_age_seconds=3600，不应清理刚完成的任务
        cleaned = await manager.cleanup_completed(max_age_seconds=3600)
        assert cleaned == 0

        # 任务仍存在
        assert await manager.get_task(task.task_id) is not None

    @pytest.mark.asyncio
    async def test_concurrent_create(self, manager: AsyncTaskManager) -> None:
        """测试并发创建任务。"""
        tasks = await asyncio.gather(*[
            manager.create_task(sql=f"SELECT {i}") for i in range(10)
        ])
        assert len(tasks) == 10
        # 所有任务 ID 应唯一
        task_ids = {t.task_id for t in tasks}
        assert len(task_ids) == 10
