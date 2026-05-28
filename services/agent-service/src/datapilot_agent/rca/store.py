"""RCA 分析记录存储。

提供 RCA 分析报告的内存存储，支持增删改查。
Phase1 使用内存存储，生产环境可替换为 Redis/PostgreSQL 实现。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from datapilot_agent.rca.models import RCAReport

logger = structlog.get_logger(__name__)


class RCAStore:
    """内存 RCA 分析记录存储。

    线程安全说明: Phase1 为单进程部署，无需加锁。
    Phase2 多进程部署时需替换为 Redis 或数据库实现。
    """

    def __init__(self) -> None:
        """初始化存储。"""
        self._records: dict[str, RCAReport] = {}

    def save(self, report: RCAReport) -> str:
        """保存分析结果，返回 analysis_id。

        Args:
            report: RCA 分析报告。

        Returns:
            分析记录的 analysis_id。
        """
        self._records[report.analysis_id] = report
        logger.debug("RCA 分析记录已保存", analysis_id=report.analysis_id)
        return report.analysis_id

    def get(self, analysis_id: str) -> RCAReport | None:
        """获取分析结果。

        Args:
            analysis_id: 分析记录唯一标识。

        Returns:
            RCA 分析报告，不存在时返回 None。
        """
        return self._records.get(analysis_id)

    def list_all(self, limit: int = 50) -> list[RCAReport]:
        """列出最近的分析记录。

        按执行时间倒序排列。

        Args:
            limit: 最大返回数量，默认 50。

        Returns:
            RCA 分析报告列表。
        """
        sorted_records = sorted(
            self._records.values(),
            key=lambda r: r.execution_time_ms,
            reverse=True,
        )
        return sorted_records[:limit]

    def delete(self, analysis_id: str) -> bool:
        """删除分析记录。

        Args:
            analysis_id: 分析记录唯一标识。

        Returns:
            是否成功删除（记录存在时返回 True，不存在返回 False）。
        """
        if analysis_id in self._records:
            del self._records[analysis_id]
            logger.debug("RCA 分析记录已删除", analysis_id=analysis_id)
            return True
        logger.debug("RCA 分析记录不存在，删除跳过", analysis_id=analysis_id)
        return False

    @property
    def size(self) -> int:
        """当前存储的记录数量。"""
        return len(self._records)
