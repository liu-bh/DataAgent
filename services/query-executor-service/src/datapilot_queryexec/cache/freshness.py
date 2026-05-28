"""数据新鲜度标注。

根据数据源类型、数据更新时间和缓存时间，判断数据的新鲜度等级，
帮助用户理解查询结果的时效性。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger(__name__)


class FreshnessLevel:
    """数据新鲜度等级。

    Attributes:
        REALTIME: 实时（<5 分钟）。
        HOURLY: 小时级（<1 小时）。
        DAILY: T+1（<24 小时）。
        STALE: 过期（>=24 小时）。
        UNKNOWN: 未知（缺少时间信息）。
    """

    REALTIME = "realtime"
    HOURLY = "hourly"
    DAILY = "daily"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass
class FreshnessInfo:
    """新鲜度标注信息。

    Attributes:
        level: 新鲜度等级。
        data_cutoff: 数据截止时间（ISO 格式）。
        last_updated: 缓存/结果最后更新时间（ISO 格式）。
    """

    level: str
    data_cutoff: str = ""
    last_updated: str = ""


class FreshnessChecker:
    """数据新鲜度检查器。

    根据数据源类型、数据更新时间和缓存时间，综合判断数据新鲜度。

    对于实时数据源（如数据库直连），主要依据数据更新时间；
    对于离线数据源（如数据仓库 T+1），会额外考虑数据源固有的延迟。
    """

    # 已知实时数据源类型
    _REALTIME_DATASOURCES: frozenset[str] = frozenset({
        "mysql",
        "postgresql",
        "clickhouse",
        "oracle",
        "sqlserver",
    })

    # 已知离线数据源类型（至少 T+1）
    _DAILY_DATASOURCES: frozenset[str] = frozenset({
        "hive",
        "presto",
        "trino_offline",
        "maxcompute",
        "doris_offline",
    })

    def __init__(self) -> None:
        """初始化新鲜度检查器。"""
        pass

    def check(
        self,
        datasource_type: str,
        data_updated_at: datetime | None = None,
        cached_at: datetime | None = None,
    ) -> FreshnessInfo:
        """根据数据源类型和数据更新时间判断新鲜度。

        对于实时数据源，直接根据数据更新时间计算等级；
        对于离线数据源，数据新鲜度上限为 DAILY（T+1）。

        Args:
            datasource_type: 数据源类型（如 mysql、hive）。
            data_updated_at: 数据最后更新时间。
            cached_at: 缓存最后更新时间。

        Returns:
            FreshnessInfo 实例，包含等级和时间信息。
        """
        now = datetime.now(timezone.utc)

        data_cutoff_str = (
            data_updated_at.isoformat() if data_updated_at else ""
        )
        cached_at_str = (
            cached_at.isoformat() if cached_at else ""
        )

        # 确定用于判断的时间基准
        reference_time = data_updated_at or cached_at
        if reference_time is None:
            logger.debug(
                "缺少时间信息，新鲜度等级为 UNKNOWN",
                datasource_type=datasource_type,
            )
            return FreshnessInfo(
                level=FreshnessLevel.UNKNOWN,
                data_cutoff=data_cutoff_str,
                last_updated=cached_at_str,
            )

        # 计算等级
        level = self.determine_level(data_updated_at, cached_at)

        # 离线数据源的上限为 DAILY
        ds_lower = datasource_type.lower()
        if ds_lower in self._DAILY_DATASOURCES and level == FreshnessLevel.REALTIME:
            level = FreshnessLevel.DAILY

        logger.debug(
            "新鲜度检查完成",
            datasource_type=datasource_type,
            level=level,
            data_updated_at=data_cutoff_str,
            cached_at=cached_at_str,
        )

        return FreshnessInfo(
            level=level,
            data_cutoff=data_cutoff_str,
            last_updated=cached_at_str,
        )

    @staticmethod
    def determine_level(
        data_updated_at: datetime | None = None,
        cached_at: datetime | None = None,
    ) -> str:
        """根据时间差判断新鲜度等级。

        优先使用 data_updated_at 与当前时间的差值判断，
        若 data_updated_at 为空则使用 cached_at。

        等级规则：
        - <5 分钟: REALTIME
        - <1 小时: HOURLY
        - <24 小时: DAILY
        - >=24 小时: STALE
        - 无时间信息: UNKNOWN

        Args:
            data_updated_at: 数据最后更新时间。
            cached_at: 缓存最后更新时间。

        Returns:
            新鲜度等级字符串。
        """
        now = datetime.now(timezone.utc)
        reference_time = data_updated_at or cached_at

        if reference_time is None:
            return FreshnessLevel.UNKNOWN

        # 确保 reference_time 是 timezone-aware
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)

        delta = now - reference_time
        total_seconds = delta.total_seconds()

        if total_seconds < 0:
            # 时间在将来，视为实时
            return FreshnessLevel.REALTIME
        elif total_seconds < 300:  # 5 分钟
            return FreshnessLevel.REALTIME
        elif total_seconds < 3600:  # 1 小时
            return FreshnessLevel.HOURLY
        elif total_seconds < 86400:  # 24 小时
            return FreshnessLevel.DAILY
        else:
            return FreshnessLevel.STALE
