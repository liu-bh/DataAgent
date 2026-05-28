"""查询执行器数据模型。

定义异步任务状态、执行请求/响应、结果格式等 Pydantic 模型。
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(StrEnum):
    """异步任务状态枚举。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FormatType(StrEnum):
    """结果格式类型枚举。"""

    JSON = "json"
    CSV = "csv"


class QueryTask(BaseModel):
    """异步查询任务模型。

    Attributes:
        task_id: 任务唯一标识。
        sql: 待执行的 SQL 语句。
        dialect: SQL 方言，默认 mysql。
        datasource_id: 数据源 ID。
        tenant_id: 租户 ID。
        status: 当前任务状态。
        result: 查询结果，JSON 格式。
        error: 错误信息。
        created_at: 任务创建时间。
        started_at: 任务开始执行时间。
        completed_at: 任务完成时间。
        execution_time_ms: 执行耗时（毫秒）。
    """

    model_config = ConfigDict(from_attributes=True)

    task_id: str
    sql: str
    dialect: str = "mysql"
    datasource_id: str = ""
    tenant_id: str = ""
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    execution_time_ms: float = 0.0


class ExecuteRequest(BaseModel):
    """SQL 执行请求模型。

    Attributes:
        sql: 待执行的 SQL 语句。
        dialect: SQL 方言，默认 mysql。
        datasource_id: 数据源 ID。
        tenant_id: 租户 ID。
        format: 结果格式，默认 JSON。
        async_execution: 是否异步执行，默认同步。
        max_rows: 最大返回行数，默认 10000。
    """

    model_config = ConfigDict(from_attributes=True)

    sql: str
    dialect: str = "mysql"
    datasource_id: str = ""
    tenant_id: str = ""
    format: FormatType = FormatType.JSON
    async_execution: bool = False
    max_rows: int = 10000
