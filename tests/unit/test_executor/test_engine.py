"""查询执行引擎单元测试。"""

from __future__ import annotations

import asyncio

import pytest

from datapilot_queryexec.executor.engine import QueryEngine
from datapilot_queryexec.executor.models import (
    ExecuteRequest,
    FormatType,
    TaskStatus,
)
from datapilot_queryexec.executor.task_manager import AsyncTaskManager


@pytest.fixture
def task_manager() -> AsyncTaskManager:
    """创建干净的 AsyncTaskManager 实例。"""
    return AsyncTaskManager()


@pytest.fixture
def engine(task_manager: AsyncTaskManager) -> QueryEngine:
    """创建无 connector_factory 的 QueryEngine（使用 mock）。"""
    return QueryEngine(task_manager=task_manager)


@pytest.fixture
def engine_with_connector(task_manager: AsyncTaskManager) -> QueryEngine:
    """创建带 mock connector_factory 的 QueryEngine。"""
    async def mock_factory(
        sql: str, dialect: str, datasource_id: str
    ) -> tuple[list[str], list[dict]]:
        return ["id", "name"], [{"id": 1, "name": "test"}]

    return QueryEngine(task_manager=task_manager, connector_factory=mock_factory)


class TestQueryEngine:
    """QueryEngine 测试。"""

    @pytest.mark.asyncio
    async def test_execute_sync_mock(self, engine: QueryEngine) -> None:
        """测试同步执行（mock 模式）。"""
        request = ExecuteRequest(sql="SELECT 1")
        task = await engine.execute_sync(request)

        assert task.status == TaskStatus.COMPLETED
        assert task.result is not None
        assert task.started_at is not None
        assert task.completed_at is not None
        assert task.execution_time_ms > 0
        # mock 结果
        assert "mock_column" in task.result["columns"]

    @pytest.mark.asyncio
    async def test_execute_sync_with_connector(
        self, engine_with_connector: QueryEngine
    ) -> None:
        """测试同步执行（带连接器）。"""
        request = ExecuteRequest(
            sql="SELECT id, name FROM users",
            dialect="postgresql",
            datasource_id="ds-001",
            tenant_id="tenant-001",
        )
        task = await engine_with_connector.execute_sync(request)

        assert task.status == TaskStatus.COMPLETED
        assert task.result is not None
        assert task.result["columns"] == ["id", "name"]
        assert task.result["data"] == [[1, "test"]]
        assert task.result["total_rows"] == 1

    @pytest.mark.asyncio
    async def test_execute_async(self, engine: QueryEngine) -> None:
        """测试异步执行。"""
        request = ExecuteRequest(sql="SELECT 1", async_execution=True)
        task = await engine.execute_async(request)

        # 异步执行应立即返回 PENDING 状态
        assert task.task_id is not None
        # 等待后台任务完成
        await asyncio.sleep(0.1)

        # 检查后台任务是否已完成
        result = await engine.get_result(task.task_id)
        assert result is not None
        assert result.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_result(self, engine: QueryEngine) -> None:
        """测试获取任务结果。"""
        request = ExecuteRequest(sql="SELECT 1")
        task = await engine.execute_sync(request)

        result = await engine.get_result(task.task_id)
        assert result is not None
        assert result.task_id == task.task_id
        assert result.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_result_not_found(self, engine: QueryEngine) -> None:
        """测试获取不存在的任务结果。"""
        result = await engine.get_result("non-existent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_sync_failure(
        self, task_manager: AsyncTaskManager
    ) -> None:
        """测试同步执行失败。"""
        async def failing_factory(
            sql: str, dialect: str, datasource_id: str
        ) -> tuple[list[str], list[dict]]:
            raise RuntimeError("模拟连接失败")

        engine = QueryEngine(
            task_manager=task_manager,
            connector_factory=failing_factory,
        )
        request = ExecuteRequest(sql="SELECT 1")
        task = await engine.execute_sync(request)

        assert task.status == TaskStatus.FAILED
        assert "模拟连接失败" in task.error
        assert task.completed_at is not None

    @pytest.mark.asyncio
    async def test_execute_sync_preserves_request_fields(
        self, engine_with_connector: QueryEngine
    ) -> None:
        """测试执行结果保留请求中的字段。"""
        request = ExecuteRequest(
            sql="SELECT 1",
            dialect="clickhouse",
            datasource_id="ds-999",
            tenant_id="tenant-999",
        )
        task = await engine_with_connector.execute_sync(request)

        assert task.sql == "SELECT 1"
        assert task.dialect == "clickhouse"
        assert task.datasource_id == "ds-999"
        assert task.tenant_id == "tenant-999"

    @pytest.mark.asyncio
    async def test_execute_async_multiple_tasks(
        self, engine: QueryEngine
    ) -> None:
        """测试同时提交多个异步任务。"""
        tasks = []
        for i in range(5):
            request = ExecuteRequest(sql=f"SELECT {i}")
            task = await engine.execute_async(request)
            tasks.append(task)

        # 等待所有后台任务完成
        await asyncio.sleep(0.2)

        for task in tasks:
            result = await engine.get_result(task.task_id)
            assert result is not None
            assert result.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execution_time_recorded(
        self, engine_with_connector: QueryEngine
    ) -> None:
        """测试执行时间被正确记录。"""
        request = ExecuteRequest(sql="SELECT 1")
        task = await engine_with_connector.execute_sync(request)

        assert task.execution_time_ms > 0
        assert task.started_at is not None
        assert task.completed_at is not None

    @pytest.mark.asyncio
    async def test_mock_execute_static_method(self) -> None:
        """测试 _mock_execute 静态方法。"""
        columns, rows = QueryEngine._mock_execute("SELECT * FROM users WHERE id = 1")
        assert columns == ["mock_column"]
        assert len(rows) == 1
        assert "mock_column" in rows[0]
