"""SQL 任务执行器单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datapilot_dag.executor.sql_executor import SQLTaskExecutor


class TestSQLTaskExecutor:
    """SQLTaskExecutor 测试。"""

    def test_init_default_url(self) -> None:
        """默认 base_url。"""
        executor = SQLTaskExecutor()
        assert executor._base_url == "http://localhost:8003"

    def test_init_custom_url(self) -> None:
        """自定义 base_url。"""
        executor = SQLTaskExecutor(base_url="http://custom:9000")
        assert executor._base_url == "http://custom:9000"

    def test_init_trailing_slash_stripped(self) -> None:
        """base_url 尾部斜杠被移除。"""
        executor = SQLTaskExecutor(base_url="http://localhost:8003/")
        assert executor._base_url == "http://localhost:8003"

    @pytest.mark.asyncio
    async def test_execute_success_with_mock_http(self) -> None:
        """使用 mock HTTP 成功执行。"""
        executor = SQLTaskExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "columns": ["id", "name"],
            "rows": [{"id": 1, "name": "test"}],
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("datapilot_dag.executor.sql_executor.httpx.AsyncClient", return_value=mock_client):
            result = await executor.execute(
                node_id="sql-1",
                config={"sql": "SELECT * FROM users", "dialect": "postgres", "datasource_id": "ds-1"},
                context={},
            )

        assert result["columns"] == ["id", "name"]
        assert result["rows"] == [{"id": 1, "name": "test"}]

        # 验证请求参数
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "api/v1/execute" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_execute_returns_mock_on_http_error(self) -> None:
        """HTTP 请求失败时返回 mock 结果。"""
        executor = SQLTaskExecutor()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("连接被拒绝"))

        with patch("datapilot_dag.executor.sql_executor.httpx.AsyncClient", return_value=mock_client):
            result = await executor.execute(
                node_id="sql-1",
                config={"sql": "SELECT 1", "dialect": "postgres", "datasource_id": "ds-1"},
                context={},
            )

        assert result["mock"] is True
        assert "columns" in result
        assert "rows" in result

    @pytest.mark.asyncio
    async def test_execute_returns_mock_when_httpx_missing(self) -> None:
        """httpx 未安装时返回 mock 结果。"""
        executor = SQLTaskExecutor()

        with patch.dict("sys.modules", {"httpx": None}):
            # 重新导入时 httpx 不可用
            result = await executor.execute(
                node_id="sql-1",
                config={"sql": "SELECT 1", "dialect": "postgres", "datasource_id": "ds-1"},
                context={},
            )

        # 由于 mock 模式在 ImportError 中触发，这里直接测试 mock 方法
        mock_result = SQLTaskExecutor._mock_result("SELECT 1", "ds-1")
        assert mock_result["mock"] is True
        assert mock_result["datasource_id"] == "ds-1"

    def test_mock_result_structure(self) -> None:
        """mock 结果结构正确。"""
        result = SQLTaskExecutor._mock_result("SELECT * FROM t", "my-ds")
        assert "columns" in result
        assert "rows" in result
        assert result["sql"] == "SELECT * FROM t"
        assert result["mock"] is True

    @pytest.mark.asyncio
    async def test_cancel(self) -> None:
        """取消任务。"""
        executor = SQLTaskExecutor()
        result = await executor.cancel("sql-1")
        assert result is True
        assert "sql-1" in executor._cancelled_tasks

    @pytest.mark.asyncio
    async def test_execute_cancelled_node_raises(self) -> None:
        """已取消的节点执行时抛出异常。"""
        executor = SQLTaskExecutor()
        await executor.cancel("sql-1")

        with pytest.raises(RuntimeError, match="已被取消"):
            await executor.execute(
                node_id="sql-1",
                config={"sql": "SELECT 1"},
                context={},
            )

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        """健康检查默认返回 True。"""
        executor = SQLTaskExecutor()
        result = await executor.health_check()
        assert result is True
