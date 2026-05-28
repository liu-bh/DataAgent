"""datapilot_queryexec.monitor.health 单元测试。

覆盖 DataSourceMonitor 的注册/注销、健康检查、定期检查启停和查询记录。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datapilot_queryexec.monitor.health import DataSourceMonitor
from datapilot_queryexec.monitor.models import CircuitState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def monitor() -> DataSourceMonitor:
    """创建监控器实例。"""
    return DataSourceMonitor(check_interval_seconds=1)


@pytest.fixture()
def registered_monitor(monitor: DataSourceMonitor) -> DataSourceMonitor:
    """创建已注册数据源的监控器实例。"""
    monitor.register(
        datasource_id="ds-1",
        name="测试数据源",
        dialect="postgres",
        host="localhost",
        port=5432,
    )
    return monitor


# ---------------------------------------------------------------------------
# 注册/注销测试
# ---------------------------------------------------------------------------


class TestRegister:
    """数据源注册测试。"""

    def test_register_success(self, monitor: DataSourceMonitor) -> None:
        """成功注册数据源。"""
        monitor.register(
            datasource_id="ds-1",
            name="测试数据源",
            dialect="postgres",
            host="localhost",
            port=5432,
        )

        status = monitor.get_status("ds-1")
        assert status is not None
        assert status.datasource_id == "ds-1"
        assert status.name == "测试数据源"
        assert status.dialect == "postgres"
        assert status.host == "localhost"
        assert status.port == 5432
        assert status.healthy is True
        assert status.circuit_state == CircuitState.CLOSED

    def test_register_with_connector(self, monitor: DataSourceMonitor) -> None:
        """注册带 connector 的数据源。"""
        mock_connector = MagicMock()
        monitor.register(
            datasource_id="ds-2",
            name="MySQL数据源",
            dialect="mysql",
            host="10.0.0.1",
            port=3306,
            connector=mock_connector,
        )

        status = monitor.get_status("ds-2")
        assert status is not None
        assert status.dialect == "mysql"

    def test_register_overwrite(self, monitor: DataSourceMonitor) -> None:
        """重复注册覆盖旧配置。"""
        monitor.register(
            datasource_id="ds-1",
            name="旧名称",
            dialect="postgres",
            host="localhost",
            port=5432,
        )
        monitor.register(
            datasource_id="ds-1",
            name="新名称",
            dialect="mysql",
            host="10.0.0.1",
            port=3306,
        )

        status = monitor.get_status("ds-1")
        assert status is not None
        assert status.name == "新名称"
        assert status.dialect == "mysql"


class TestUnregister:
    """数据源注销测试。"""

    def test_unregister_success(self, registered_monitor: DataSourceMonitor) -> None:
        """成功注销数据源。"""
        registered_monitor.unregister("ds-1")
        status = registered_monitor.get_status("ds-1")
        assert status is None

    def test_unregister_nonexistent(self, monitor: DataSourceMonitor) -> None:
        """注销不存在的数据源不报错。"""
        monitor.unregister("non-existent")


# ---------------------------------------------------------------------------
# 健康检查测试
# ---------------------------------------------------------------------------


class TestCheckOne:
    """单个数据源健康检查测试。"""

    async def test_check_tcp_success(self, registered_monitor: DataSourceMonitor) -> None:
        """TCP 端口探测成功。"""
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch(
            "datapilot_queryexec.monitor.health.asyncio.open_connection",
            new_callable=AsyncMock,
            return_value=(mock_reader, mock_writer),
        ):
            status = await registered_monitor.check_one("ds-1")

        assert status.healthy is True
        assert status.latency_ms >= 0
        assert status.consecutive_failures == 0
        assert status.last_check_at is not None

    async def test_check_tcp_failure(self, registered_monitor: DataSourceMonitor) -> None:
        """TCP 端口探测失败。"""
        with patch(
            "datapilot_queryexec.monitor.health.asyncio.open_connection",
            new_callable=AsyncMock,
            side_effect=ConnectionRefusedError("连接被拒绝"),
        ):
            status = await registered_monitor.check_one("ds-1")

        assert status.healthy is False
        assert status.consecutive_failures == 1

    async def test_check_with_connector_success(self, monitor: DataSourceMonitor) -> None:
        """通过 connector 检查成功。"""
        mock_connector = AsyncMock()
        mock_connector.health_check = AsyncMock(return_value=True)

        monitor.register(
            datasource_id="ds-3",
            name="Connector数据源",
            dialect="mysql",
            host="localhost",
            port=3306,
            connector=mock_connector,
        )

        status = await monitor.check_one("ds-3")
        assert status.healthy is True

    async def test_check_with_connector_failure(self, monitor: DataSourceMonitor) -> None:
        """通过 connector 检查失败。"""
        mock_connector = AsyncMock()
        mock_connector.health_check = AsyncMock(return_value=False)

        monitor.register(
            datasource_id="ds-4",
            name="Connector故障源",
            dialect="mysql",
            host="localhost",
            port=3306,
            connector=mock_connector,
        )

        status = await monitor.check_one("ds-4")
        assert status.healthy is False

    async def test_check_nonexistent(self, monitor: DataSourceMonitor) -> None:
        """检查未注册的数据源抛出 KeyError。"""
        with pytest.raises(KeyError):
            await monitor.check_one("non-existent")


class TestCheckAll:
    """批量检查测试。"""

    async def test_check_all_empty(self, monitor: DataSourceMonitor) -> None:
        """无数据源时返回空列表。"""
        results = await monitor.check_all()
        assert results == []

    async def test_check_all_multiple(self, monitor: DataSourceMonitor) -> None:
        """多个数据源批量检查。"""
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        monitor.register(
            datasource_id="ds-a",
            name="数据源A",
            dialect="postgres",
            host="localhost",
            port=5432,
        )
        monitor.register(
            datasource_id="ds-b",
            name="数据源B",
            dialect="mysql",
            host="localhost",
            port=3306,
        )

        with patch(
            "datapilot_queryexec.monitor.health.asyncio.open_connection",
            new_callable=AsyncMock,
            return_value=(mock_reader, mock_writer),
        ):
            results = await monitor.check_all()

        assert len(results) == 2


class TestGetStatus:
    """获取状态测试。"""

    def test_get_status_exists(self, registered_monitor: DataSourceMonitor) -> None:
        """获取已注册数据源状态。"""
        status = registered_monitor.get_status("ds-1")
        assert status is not None
        assert status.datasource_id == "ds-1"

    def test_get_status_nonexistent(self, monitor: DataSourceMonitor) -> None:
        """获取未注册数据源状态返回 None。"""
        status = monitor.get_status("non-existent")
        assert status is None

    def test_get_all_statuses(self, registered_monitor: DataSourceMonitor) -> None:
        """获取所有数据源状态。"""
        statuses = registered_monitor.get_all_statuses()
        assert len(statuses) == 1
        assert statuses[0].datasource_id == "ds-1"


# ---------------------------------------------------------------------------
# 定期检查测试
# ---------------------------------------------------------------------------


class TestPeriodicCheck:
    """定期检查启停测试。"""

    async def test_start_and_stop(self, monitor: DataSourceMonitor) -> None:
        """启动和停止定期检查。"""
        monitor.register(
            datasource_id="ds-1",
            name="测试数据源",
            dialect="postgres",
            host="localhost",
            port=5432,
        )

        await monitor.start_periodic_check()
        # 确保任务已启动
        await asyncio.sleep(0.1)
        await monitor.stop_periodic_check()

    async def test_start_twice(self, monitor: DataSourceMonitor) -> None:
        """重复启动不创建多余任务。"""
        await monitor.start_periodic_check()
        await monitor.start_periodic_check()
        await monitor.stop_periodic_check()

    async def test_stop_without_start(self, monitor: DataSourceMonitor) -> None:
        """未启动时停止不报错。"""
        await monitor.stop_periodic_check()


# ---------------------------------------------------------------------------
# 查询记录测试
# ---------------------------------------------------------------------------


class TestRecordQuery:
    """查询记录测试。"""

    def test_record_success(self, registered_monitor: DataSourceMonitor) -> None:
        """记录成功查询。"""
        registered_monitor.record_query("ds-1", success=True, latency_ms=10.0)

        status = registered_monitor.get_status("ds-1")
        assert status is not None
        assert status.total_queries == 1
        assert status.error_queries == 0
        assert status.avg_latency_ms == 10.0

    def test_record_failure(self, registered_monitor: DataSourceMonitor) -> None:
        """记录失败查询。"""
        registered_monitor.record_query("ds-1", success=False, latency_ms=50.0)

        status = registered_monitor.get_status("ds-1")
        assert status is not None
        assert status.total_queries == 1
        assert status.error_queries == 1

    def test_record_multiple_queries(self, registered_monitor: DataSourceMonitor) -> None:
        """记录多次查询，验证移动平均。"""
        registered_monitor.record_query("ds-1", success=True, latency_ms=10.0)
        registered_monitor.record_query("ds-1", success=True, latency_ms=20.0)
        registered_monitor.record_query("ds-1", success=False, latency_ms=30.0)

        status = registered_monitor.get_status("ds-1")
        assert status is not None
        assert status.total_queries == 3
        assert status.error_queries == 1
        assert status.avg_latency_ms == pytest.approx(20.0)

    def test_record_nonexistent(self, monitor: DataSourceMonitor) -> None:
        """记录未注册数据源不报错。"""
        monitor.record_query("non-existent", success=True, latency_ms=10.0)

    def test_circuit_state_after_failures(self, registered_monitor: DataSourceMonitor) -> None:
        """连续失败触发熔断。"""
        # 连续失败 5 次（默认阈值）
        for _ in range(5):
            registered_monitor.record_query("ds-1", success=False, latency_ms=0.0)

        status = registered_monitor.get_status("ds-1")
        assert status is not None
        assert status.circuit_state == CircuitState.OPEN
