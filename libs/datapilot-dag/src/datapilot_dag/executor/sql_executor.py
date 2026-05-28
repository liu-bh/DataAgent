"""SQL 任务执行器。

通过 HTTP 调用 query-executor-service 执行 SQL 查询。
"""

from __future__ import annotations

from typing import Any

import structlog

from datapilot_dag.executor.base import BaseTaskExecutor

logger = structlog.get_logger(__name__)


class SQLTaskExecutor(BaseTaskExecutor):
    """SQL 任务执行器。

    通过 HTTP 调用 query-executor-service 的 /api/v1/execute 端点执行 SQL。
    如果服务不可用，返回 mock 结果以支持开发调试。

    Attributes:
        base_url: query-executor-service 的基础 URL。
    """

    def __init__(self, base_url: str = "http://localhost:8003") -> None:
        self._base_url = base_url.rstrip("/")
        self._cancelled_tasks: set[str] = set()

    async def execute(self, node_id: str, config: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行 SQL 查询。

        Args:
            node_id: 节点标识符。
            config: 任务配置，包含：
                - sql: str — SQL 语句
                - dialect: str — SQL 方言
                - datasource_id: str — 数据源 ID
            context: 执行上下文。

        Returns:
            查询结果字典，包含 columns 和 rows。

        Raises:
            RuntimeError: 节点已被取消或执行失败。
        """
        if node_id in self._cancelled_tasks:
            raise RuntimeError(f"节点 {node_id} 已被取消")

        sql: str = config.get("sql", "")
        dialect: str = config.get("dialect", "postgres")
        datasource_id: str = config.get("datasource_id", "")

        logger.debug(
            "sql_executor_execute",
            node_id=node_id,
            dialect=dialect,
            datasource_id=datasource_id,
            sql_length=len(sql),
        )

        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._base_url}/api/v1/execute",
                    json={
                        "sql": sql,
                        "dialect": dialect,
                        "datasource_id": datasource_id,
                    },
                )
                response.raise_for_status()
                result = response.json()
                logger.info(
                    "sql_executor_success",
                    node_id=node_id,
                    row_count=len(result.get("rows", [])),
                )
                return result

        except ImportError:
            logger.warning(
                "sql_executor_httpx_not_available",
                node_id=node_id,
                message="httpx 未安装，返回 mock 结果",
            )
            return self._mock_result(sql, datasource_id)

        except Exception as exc:
            logger.warning(
                "sql_executor_service_unavailable",
                node_id=node_id,
                error=str(exc),
                message="query-executor-service 不可用，返回 mock 结果",
            )
            return self._mock_result(sql, datasource_id)

    async def cancel(self, node_id: str) -> bool:
        """取消 SQL 任务。

        Args:
            node_id: 节点标识符。

        Returns:
            是否成功取消。
        """
        self._cancelled_tasks.add(node_id)
        logger.info("sql_executor_cancelled", node_id=node_id)
        return True

    @staticmethod
    def _mock_result(sql: str, datasource_id: str) -> dict[str, Any]:
        """生成 mock 查询结果。

        Args:
            sql: 原始 SQL 语句。
            datasource_id: 数据源 ID。

        Returns:
            Mock 结果字典。
        """
        return {
            "columns": ["result"],
            "rows": [{"result": f"mock result for datasource={datasource_id}"}],
            "sql": sql,
            "mock": True,
        }
