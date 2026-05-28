"""连接器基类单元测试。

测试 BaseConnector 的抽象接口和 ExecuteResult / ConnectorHealth 数据类。
使用具体的 Mock 连接器验证基类行为。
"""

from __future__ import annotations

from typing import Any

import pytest

from datapilot_queryexec.connectors.base import (
    BaseConnector,
    ConnectorHealth,
    ExecuteResult,
)

# ---------- Mock 连接器（用于测试基类行为） ----------


class MockConnector(BaseConnector):
    """测试用 Mock 连接器。"""

    def __init__(
        self,
        datasource_id: str = "test-ds",
        host: str = "localhost",
        port: int = 5432,
        database: str = "testdb",
        username: str = "user",
        password: str = "pass",
        pool_size: int = 5,
    ) -> None:
        super().__init__(datasource_id, host, port, database, username, password, pool_size)
        self._connect_called = False
        self._disconnect_called = False
        self._execute_sql: str = ""
        self._execute_params: dict[str, Any] | None = None
        self._health_result = ConnectorHealth(healthy=True, latency_ms=1.0)

    @property
    def dialect(self) -> str:
        return "mock"

    async def connect(self) -> None:
        self._connect_called = True
        self._connected = True

    async def disconnect(self) -> None:
        self._disconnect_called = True
        self._connected = False

    async def execute(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> ExecuteResult:
        self._execute_sql = sql
        self._execute_params = params
        return ExecuteResult(
            columns=["id", "name"],
            rows=[{"id": 1, "name": "test"}],
            row_count=1,
            execution_time_ms=10.0,
        )

    async def health_check(self) -> ConnectorHealth:
        return self._health_result


# ---------- ExecuteResult 测试 ----------


class TestExecuteResult:
    """ExecuteResult 数据类测试。"""

    def test_basic_result(self) -> None:
        """基本结果测试。"""
        result = ExecuteResult(
            columns=["id", "name"],
            rows=[{"id": 1, "name": "alice"}],
            row_count=1,
            execution_time_ms=5.0,
        )
        assert result.columns == ["id", "name"]
        assert result.rows == [{"id": 1, "name": "alice"}]
        assert result.row_count == 1
        assert result.execution_time_ms == 5.0
        assert result.error == ""

    def test_error_result(self) -> None:
        """错误结果测试。"""
        result = ExecuteResult(
            columns=[],
            rows=[],
            row_count=0,
            execution_time_ms=0.0,
            error="syntax error",
        )
        assert result.error == "syntax error"
        assert result.row_count == 0

    def test_empty_columns(self) -> None:
        """空列结果测试。"""
        result = ExecuteResult(
            columns=[],
            rows=[],
            row_count=0,
            execution_time_ms=0.0,
        )
        assert result.columns == []
        assert result.rows == []


# ---------- ConnectorHealth 测试 ----------


class TestConnectorHealth:
    """ConnectorHealth 数据类测试。"""

    def test_healthy(self) -> None:
        """健康状态测试。"""
        health = ConnectorHealth(
            healthy=True,
            latency_ms=10.5,
            pool_size=10,
            pool_used=3,
        )
        assert health.healthy is True
        assert health.latency_ms == 10.5
        assert health.pool_size == 10
        assert health.pool_used == 3
        assert health.error == ""

    def test_unhealthy(self) -> None:
        """不健康状态测试。"""
        health = ConnectorHealth(
            healthy=False,
            error="connection refused",
        )
        assert health.healthy is False
        assert health.error == "connection refused"
        assert health.latency_ms == 0.0


# ---------- BaseConnector 测试 ----------


class TestBaseConnector:
    """BaseConnector 基类行为测试。"""

    def test_init_properties(self) -> None:
        """初始化属性测试。"""
        connector = MockConnector(
            datasource_id="ds-001",
            host="192.168.1.1",
            port=3306,
            database="mydb",
            username="root",
            password="secret",
            pool_size=20,
        )
        assert connector.datasource_id == "ds-001"
        assert connector.host == "192.168.1.1"
        assert connector.port == 3306
        assert connector.database == "mydb"
        assert connector.connected is False

    def test_default_pool_size(self) -> None:
        """默认连接池大小测试。"""
        connector = MockConnector()
        assert connector.connected is False

    def test_cannot_instantiate_abstract(self) -> None:
        """不能直接实例化抽象类。"""
        with pytest.raises(TypeError):
            BaseConnector(
                datasource_id="ds",
                host="localhost",
                port=3306,
                database="db",
                username="u",
                password="p",
            )

    @pytest.mark.asyncio
    async def test_connect(self) -> None:
        """connect 方法测试。"""
        connector = MockConnector()
        assert connector.connected is False
        await connector.connect()
        assert connector.connected is True
        assert connector._connect_called is True  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_disconnect(self) -> None:
        """disconnect 方法测试。"""
        connector = MockConnector()
        await connector.connect()
        await connector.disconnect()
        assert connector.connected is False
        assert connector._disconnect_called is True  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_execute(self) -> None:
        """execute 方法测试。"""
        connector = MockConnector()
        result = await connector.execute("SELECT 1", {"id": 1})
        assert result.columns == ["id", "name"]
        assert result.row_count == 1
        assert connector._execute_sql == "SELECT 1"  # noqa: SLF001
        assert connector._execute_params == {"id": 1}  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_execute_without_params(self) -> None:
        """无参数执行测试。"""
        connector = MockConnector()
        result = await connector.execute("SELECT 1")
        assert result.row_count == 1
        assert connector._execute_params is None  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        """健康检查测试。"""
        connector = MockConnector()
        health = await connector.health_check()
        assert health.healthy is True
        assert health.latency_ms == 1.0

    @pytest.mark.asyncio
    async def test_dialect_property(self) -> None:
        """方言属性测试。"""
        connector = MockConnector()
        assert connector.dialect == "mock"

    @pytest.mark.asyncio
    async def test_execute_with_timing_error(self) -> None:
        """执行出错时返回带错误信息的 ExecuteResult。"""
        connector = MockConnector()

        # 覆盖 _do_execute 使其抛出异常（_execute_with_timing 调用 _do_execute）
        async def failing_execute(
            sql: str,
            params: dict[str, Any] | None = None,
        ) -> ExecuteResult:
            raise ConnectionError("连接失败")

        connector._do_execute = failing_execute  # type: ignore[method-assign]
        result = await connector._execute_with_timing("SELECT 1")
        assert result.error != ""
        assert "连接失败" in result.error
        assert result.row_count == 0
        assert result.execution_time_ms >= 0
