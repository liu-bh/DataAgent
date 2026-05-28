"""DAG 执行记录存储（内存实现）。

提供 DAG 执行的生命周期管理和查询能力。
Phase1 使用内存存储，生产环境可替换为 Redis/PostgreSQL 实现。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class DAGExecutionRecord:
    """DAG 执行记录。"""

    dag_id: str
    status: str
    question: str = ""
    created_at: float = 0.0
    completed_at: float = 0.0
    result: dict[str, Any] | None = None


class DAGExecutionStore:
    """内存中的 DAG 执行记录存储。

    线程安全说明: Phase1 为单进程部署，无需加锁。
    Phase2 多进程部署时需替换为 Redis 或数据库实现。
    """

    def __init__(self) -> None:
        """初始化存储。"""
        self._records: dict[str, DAGExecutionRecord] = {}

    def create(self, dag_id: str, question: str = "") -> DAGExecutionRecord:
        """创建新的 DAG 执行记录。

        Args:
            dag_id: DAG 唯一标识。
            question: 用户原始问题。

        Returns:
            新创建的执行记录。
        """
        record = DAGExecutionRecord(
            dag_id=dag_id,
            status="pending",
            question=question,
            created_at=time.time(),
        )
        self._records[dag_id] = record
        logger.debug("DAG 执行记录已创建", dag_id=dag_id, status="pending")
        return record

    def get(self, dag_id: str) -> DAGExecutionRecord | None:
        """获取 DAG 执行记录。

        Args:
            dag_id: DAG 唯一标识。

        Returns:
            执行记录，不存在时返回 None。
        """
        return self._records.get(dag_id)

    def update(self, dag_id: str, **kwargs: Any) -> None:
        """更新 DAG 执行记录。

        Args:
            dag_id: DAG 唯一标识。
            **kwargs: 要更新的字段。

        Raises:
            KeyError: 当 dag_id 不存在时。
        """
        record = self._records.get(dag_id)
        if record is None:
            raise KeyError(f"DAG 执行记录不存在: {dag_id}")
        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)
        logger.debug("DAG 执行记录已更新", dag_id=dag_id, updated_keys=list(kwargs.keys()))

    def list_records(self, limit: int = 50) -> list[DAGExecutionRecord]:
        """查询 DAG 执行历史（按创建时间倒序）。

        Args:
            limit: 最大返回数量，默认 50。

        Returns:
            执行记录列表，按创建时间倒序排列。
        """
        sorted_records = sorted(
            self._records.values(),
            key=lambda r: r.created_at,
            reverse=True,
        )
        return sorted_records[:limit]

    def cleanup(self, max_age_seconds: int = 3600) -> int:
        """清理过期的执行记录。

        Args:
            max_age_seconds: 最大保留时间（秒），默认 3600（1 小时）。

        Returns:
            清理的记录数量。
        """
        now = time.time()
        expired_ids = [
            dag_id
            for dag_id, record in self._records.items()
            if now - record.created_at > max_age_seconds
        ]
        for dag_id in expired_ids:
            del self._records[dag_id]
        if expired_ids:
            logger.info("清理过期 DAG 执行记录", count=len(expired_ids))
        return len(expired_ids)

    @property
    def size(self) -> int:
        """当前存储的记录数量。"""
        return len(self._records)
