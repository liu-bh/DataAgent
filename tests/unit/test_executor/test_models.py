"""查询执行器数据模型单元测试。"""

from datetime import datetime

import pytest

from datapilot_queryexec.executor.models import ExecuteRequest, FormatType, QueryTask, TaskStatus


class TestTaskStatus:
    """TaskStatus 枚举测试。"""

    def test_values(self) -> None:
        """测试所有状态值。"""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"

    def test_is_str_enum(self) -> None:
        """测试枚举可以直接作为字符串使用。"""
        assert isinstance(TaskStatus.PENDING, str)
        assert TaskStatus.PENDING == "pending"


class TestFormatType:
    """FormatType 枚举测试。"""

    def test_values(self) -> None:
        """测试格式类型值。"""
        assert FormatType.JSON == "json"
        assert FormatType.CSV == "csv"


class TestQueryTask:
    """QueryTask 模型测试。"""

    def test_default_values(self) -> None:
        """测试默认值。"""
        task = QueryTask(task_id="test-123", sql="SELECT 1")
        assert task.task_id == "test-123"
        assert task.sql == "SELECT 1"
        assert task.dialect == "mysql"
        assert task.datasource_id == ""
        assert task.tenant_id == ""
        assert task.status == TaskStatus.PENDING
        assert task.result is None
        assert task.error == ""
        assert task.started_at is None
        assert task.completed_at is None
        assert task.execution_time_ms == 0.0

    def test_custom_values(self) -> None:
        """测试自定义值。"""
        now = datetime.utcnow()
        task = QueryTask(
            task_id="t-001",
            sql="SELECT name FROM users",
            dialect="postgresql",
            datasource_id="ds-001",
            tenant_id="tenant-001",
            status=TaskStatus.RUNNING,
            result={"columns": ["name"], "data": [["Alice"]]},
            error="",
            created_at=now,
            started_at=now,
        )
        assert task.task_id == "t-001"
        assert task.sql == "SELECT name FROM users"
        assert task.dialect == "postgresql"
        assert task.datasource_id == "ds-001"
        assert task.tenant_id == "tenant-001"
        assert task.status == TaskStatus.RUNNING
        assert task.result is not None
        assert task.result["columns"] == ["name"]
        assert task.started_at == now

    def test_model_serialization(self) -> None:
        """测试模型序列化。"""
        task = QueryTask(task_id="t-001", sql="SELECT 1")
        data = task.model_dump()
        assert data["task_id"] == "t-001"
        assert data["sql"] == "SELECT 1"
        assert data["status"] == "pending"
        assert data["result"] is None

    def test_model_from_dict(self) -> None:
        """测试从字典创建模型。"""
        data = {
            "task_id": "t-002",
            "sql": "SELECT 2",
            "status": "completed",
            "result": {"columns": ["1"], "data": [[2]]},
        }
        task = QueryTask.model_validate(data)
        assert task.task_id == "t-002"
        assert task.status == TaskStatus.COMPLETED
        assert task.result is not None

    def test_created_at_auto(self) -> None:
        """测试 created_at 自动生成。"""
        before = datetime.utcnow()
        task = QueryTask(task_id="t-003", sql="SELECT 3")
        after = datetime.utcnow()
        assert before <= task.created_at <= after


class TestExecuteRequest:
    """ExecuteRequest 模型测试。"""

    def test_default_values(self) -> None:
        """测试默认值。"""
        req = ExecuteRequest(sql="SELECT 1")
        assert req.sql == "SELECT 1"
        assert req.dialect == "mysql"
        assert req.datasource_id == ""
        assert req.tenant_id == ""
        assert req.format == FormatType.JSON
        assert req.async_execution is False
        assert req.max_rows == 10000

    def test_custom_values(self) -> None:
        """测试自定义值。"""
        req = ExecuteRequest(
            sql="SELECT * FROM orders",
            dialect="postgresql",
            datasource_id="ds-002",
            tenant_id="tenant-002",
            format=FormatType.CSV,
            async_execution=True,
            max_rows=500,
        )
        assert req.sql == "SELECT * FROM orders"
        assert req.dialect == "postgresql"
        assert req.datasource_id == "ds-002"
        assert req.format == FormatType.CSV
        assert req.async_execution is True
        assert req.max_rows == 500

    def test_sql_required(self) -> None:
        """测试 sql 为必填字段。"""
        with pytest.raises(Exception):
            ExecuteRequest()  # type: ignore[call-arg]

    def test_max_rows_validation(self) -> None:
        """测试 max_rows 接受各种整数值。"""
        req = ExecuteRequest(sql="SELECT 1", max_rows=1)
        assert req.max_rows == 1

    def test_model_serialization(self) -> None:
        """测试请求模型序列化。"""
        req = ExecuteRequest(sql="SELECT 1", format=FormatType.CSV)
        data = req.model_dump()
        assert data["format"] == "csv"
        assert data["async_execution"] is False
