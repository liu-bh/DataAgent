"""数据新鲜度标注单元测试。

测试新鲜度等级判断、数据源类型识别和时间差计算。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from datapilot_queryexec.cache.freshness import FreshnessChecker, FreshnessInfo, FreshnessLevel


class TestFreshnessLevel:
    """FreshnessLevel 常量测试。"""

    def test_level_values(self) -> None:
        """验证所有等级常量。"""
        assert FreshnessLevel.REALTIME == "realtime"
        assert FreshnessLevel.HOURLY == "hourly"
        assert FreshnessLevel.DAILY == "daily"
        assert FreshnessLevel.STALE == "stale"
        assert FreshnessLevel.UNKNOWN == "unknown"


class TestDetermineLevel:
    """静态方法 determine_level 测试。"""

    def test_realtime_within_5_min(self) -> None:
        """5 分钟内为实时。"""
        now = datetime.now(timezone.utc)
        data_time = now - timedelta(minutes=3)
        assert FreshnessChecker.determine_level(data_updated_at=data_time) == FreshnessLevel.REALTIME

    def test_realtime_just_under_5_min(self) -> None:
        """4 分 59 秒为实时。"""
        now = datetime.now(timezone.utc)
        data_time = now - timedelta(minutes=4, seconds=59)
        assert FreshnessChecker.determine_level(data_updated_at=data_time) == FreshnessLevel.REALTIME

    def test_hourly_within_1_hour(self) -> None:
        """1 小时内为小时级。"""
        now = datetime.now(timezone.utc)
        data_time = now - timedelta(minutes=30)
        assert FreshnessChecker.determine_level(data_updated_at=data_time) == FreshnessLevel.HOURLY

    def test_hourly_just_over_5_min(self) -> None:
        """5 分 1 秒为小时级。"""
        now = datetime.now(timezone.utc)
        data_time = now - timedelta(minutes=5, seconds=1)
        assert FreshnessChecker.determine_level(data_updated_at=data_time) == FreshnessLevel.HOURLY

    def test_daily_within_24_hours(self) -> None:
        """24 小时内为 T+1。"""
        now = datetime.now(timezone.utc)
        data_time = now - timedelta(hours=12)
        assert FreshnessChecker.determine_level(data_updated_at=data_time) == FreshnessLevel.DAILY

    def test_daily_just_over_1_hour(self) -> None:
        """1 小时 1 秒为 T+1。"""
        now = datetime.now(timezone.utc)
        data_time = now - timedelta(hours=1, seconds=1)
        assert FreshnessChecker.determine_level(data_updated_at=data_time) == FreshnessLevel.DAILY

    def test_stale_over_24_hours(self) -> None:
        """超过 24 小时为过期。"""
        now = datetime.now(timezone.utc)
        data_time = now - timedelta(hours=25)
        assert FreshnessChecker.determine_level(data_updated_at=data_time) == FreshnessLevel.STALE

    def test_stale_exactly_24_hours(self) -> None:
        """恰好 24 小时为过期。"""
        now = datetime.now(timezone.utc)
        data_time = now - timedelta(hours=24)
        # 恰好 24 小时 = 86400 秒，应返回 STALE
        assert FreshnessChecker.determine_level(data_updated_at=data_time) == FreshnessLevel.STALE

    def test_unknown_no_time(self) -> None:
        """无时间信息为未知。"""
        assert FreshnessChecker.determine_level() == FreshnessLevel.UNKNOWN

    def test_fallback_to_cached_at(self) -> None:
        """无 data_updated_at 时使用 cached_at。"""
        now = datetime.now(timezone.utc)
        cached_time = now - timedelta(minutes=2)
        assert FreshnessChecker.determine_level(cached_at=cached_time) == FreshnessLevel.REALTIME

    def test_data_updated_at_priority(self) -> None:
        """data_updated_at 优先于 cached_at。"""
        now = datetime.now(timezone.utc)
        data_time = now - timedelta(minutes=2)  # 实时
        cached_time = now - timedelta(hours=5)  # T+1
        assert FreshnessChecker.determine_level(data_updated_at=data_time, cached_at=cached_time) == FreshnessLevel.REALTIME

    def test_future_time(self) -> None:
        """未来时间视为实时。"""
        now = datetime.now(timezone.utc)
        future_time = now + timedelta(minutes=10)
        assert FreshnessChecker.determine_level(data_updated_at=future_time) == FreshnessLevel.REALTIME

    def test_naive_datetime_converted(self) -> None:
        """无时区的 datetime 自动转换为 UTC。"""
        naive_time = datetime(2025, 1, 1, 0, 0, 0)  # naive
        # 由于是过去的时间，应该返回 STALE
        level = FreshnessChecker.determine_level(data_updated_at=naive_time)
        assert level == FreshnessLevel.STALE


class TestFreshnessCheckerCheck:
    """FreshnessChecker.check 方法测试。"""

    def test_check_realtime_datasource(self) -> None:
        """实时数据源（mysql）应返回正确等级。"""
        checker = FreshnessChecker()
        now = datetime.now(timezone.utc)
        info = checker.check("mysql", data_updated_at=now - timedelta(minutes=2))

        assert info.level == FreshnessLevel.REALTIME
        assert info.data_cutoff == (now - timedelta(minutes=2)).isoformat()

    def test_check_offline_datasource_capped_to_daily(self) -> None:
        """离线数据源（hive）的新鲜度上限为 DAILY。"""
        checker = FreshnessChecker()
        now = datetime.now(timezone.utc)
        info = checker.check("hive", data_updated_at=now - timedelta(minutes=2))

        assert info.level == FreshnessLevel.DAILY  # 被限制为 DAILY

    def test_check_offline_datasource_still_stale(self) -> None:
        """离线数据源过期数据仍为 STALE。"""
        checker = FreshnessChecker()
        now = datetime.now(timezone.utc)
        info = checker.check("hive", data_updated_at=now - timedelta(hours=48))

        assert info.level == FreshnessLevel.STALE

    def test_check_unknown_datasource_type(self) -> None:
        """未知数据源类型正常判断。"""
        checker = FreshnessChecker()
        now = datetime.now(timezone.utc)
        info = checker.check("unknown_db", data_updated_at=now - timedelta(minutes=2))

        # 未知数据源不受离线限制
        assert info.level == FreshnessLevel.REALTIME

    def test_check_no_time_info(self) -> None:
        """无时间信息返回 UNKNOWN。"""
        checker = FreshnessChecker()
        info = checker.check("mysql")

        assert info.level == FreshnessLevel.UNKNOWN
        assert info.data_cutoff == ""
        assert info.last_updated == ""

    def test_check_with_cached_at(self) -> None:
        """仅有 cached_at 时正常工作。"""
        checker = FreshnessChecker()
        now = datetime.now(timezone.utc)
        info = checker.check("mysql", cached_at=now - timedelta(hours=2))

        assert info.level == FreshnessLevel.DAILY
        assert info.last_updated == (now - timedelta(hours=2)).isoformat()
        assert info.data_cutoff == ""

    def test_check_with_both_times(self) -> None:
        """同时提供 data_updated_at 和 cached_at。"""
        checker = FreshnessChecker()
        now = datetime.now(timezone.utc)
        data_time = now - timedelta(minutes=10)
        cached_time = now - timedelta(minutes=1)
        info = checker.check("mysql", data_updated_at=data_time, cached_at=cached_time)

        assert info.level == FreshnessLevel.HOURLY
        assert info.data_cutoff == data_time.isoformat()
        assert info.last_updated == cached_time.isoformat()

    def test_check_all_realtime_datasources(self) -> None:
        """验证所有已知实时数据源。"""
        checker = FreshnessChecker()
        now = datetime.now(timezone.utc)

        for ds in ["mysql", "postgresql", "clickhouse", "oracle", "sqlserver"]:
            info = checker.check(ds, data_updated_at=now - timedelta(minutes=2))
            assert info.level == FreshnessLevel.REALTIME, f"{ds} 应为 REALTIME"

    def test_check_all_offline_datasources(self) -> None:
        """验证所有已知离线数据源被限制为 DAILY。"""
        checker = FreshnessChecker()
        now = datetime.now(timezone.utc)

        for ds in ["hive", "presto", "trino_offline", "maxcompute", "doris_offline"]:
            info = checker.check(ds, data_updated_at=now - timedelta(minutes=2))
            assert info.level == FreshnessLevel.DAILY, f"{ds} 应被限制为 DAILY"

    def test_check_case_insensitive(self) -> None:
        """数据源类型大小写不敏感。"""
        checker = FreshnessChecker()
        now = datetime.now(timezone.utc)

        info_upper = checker.check("MYSQL", data_updated_at=now - timedelta(minutes=2))
        info_mixed = checker.check("PostgreSQL", data_updated_at=now - timedelta(minutes=2))

        assert info_upper.level == FreshnessLevel.REALTIME
        assert info_mixed.level == FreshnessLevel.REALTIME

        info_hive_upper = checker.check("HIVE", data_updated_at=now - timedelta(minutes=2))
        assert info_hive_upper.level == FreshnessLevel.DAILY


class TestFreshnessInfo:
    """FreshnessInfo 数据类测试。"""

    def test_default_values(self) -> None:
        """验证默认值。"""
        info = FreshnessInfo(level="unknown")
        assert info.level == "unknown"
        assert info.data_cutoff == ""
        assert info.last_updated == ""

    def test_full_values(self) -> None:
        """验证完整信息。"""
        info = FreshnessInfo(
            level="realtime",
            data_cutoff="2025-01-01T12:00:00+00:00",
            last_updated="2025-01-01T12:05:00+00:00",
        )
        assert info.level == "realtime"
        assert "2025-01-01" in info.data_cutoff
        assert "2025-01-01" in info.last_updated
