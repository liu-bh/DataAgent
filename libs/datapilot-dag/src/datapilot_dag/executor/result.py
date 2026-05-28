"""任务执行结果数据模型。

定义任务和 DAG 执行过程中的状态、结果和时间信息。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 从 models 导入，保持对外 API 兼容
from datapilot_dag.models import TaskStatus  # noqa: F401


@dataclass
class TaskResult:
    """单个任务的执行结果。

    Attributes:
        node_id: 节点标识符。
        status: 任务状态（TaskStatus 枚举值）。
        output: 任务输出数据。
        error: 错误信息。
        execution_time_ms: 执行耗时（毫秒）。
        retries: 重试次数。
        started_at: 开始时间戳（time.monotonic()）。
        completed_at: 完成时间戳（time.monotonic()）。
    """

    node_id: str
    status: str  # TaskStatus value
    output: Any = None
    error: str = ""
    execution_time_ms: float = 0.0
    retries: int = 0
    started_at: float = 0.0
    completed_at: float = 0.0


@dataclass
class DAGResult:
    """DAG 整体执行结果。

    Attributes:
        dag_id: DAG 标识符。
        status: DAG 整体状态（TaskStatus 枚举值）。
        task_results: 各节点的执行结果，key 为 node_id。
        total_time_ms: 总执行耗时（毫秒）。
        error: 整体错误信息。
        execution_order: 实际执行顺序的节点 ID 列表。
    """

    dag_id: str
    status: str
    task_results: dict[str, TaskResult] = field(default_factory=dict)
    total_time_ms: float = 0.0
    error: str = ""
    execution_order: list[str] = field(default_factory=list)
