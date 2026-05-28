"""DAG 执行调度器。

按拓扑排序并行调度各层级任务，支持重试、超时和条件分支控制。
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

import structlog

from datapilot_dag.executor.result import DAGResult, TaskResult, TaskStatus

if TYPE_CHECKING:
    from datapilot_dag.models import DAGNode, DAGraph

logger = structlog.get_logger(__name__)


class DAGScheduler:
    """DAG 执行调度器。

    按拓扑排序获取执行层级，逐层并行执行任务。
    支持重试（指数退避）、超时控制和条件分支跳过。

    Attributes:
        _registry: 执行器注册表。
        _max_depth: DAG 最大执行深度。
        _max_retry: 单任务最大重试次数。
        _task_timeout: 单任务执行超时（秒）。
    """

    def __init__(
        self,
        registry: ExecutorRegistry | None = None,
        max_depth: int = 5,
        max_retry: int = 3,
        task_timeout: float = 30.0,
    ) -> None:
        from datapilot_dag.executor.registry import ExecutorRegistry

        self._registry = registry or ExecutorRegistry()
        self._max_depth = max_depth
        self._max_retry = max_retry
        self._task_timeout = task_timeout

    async def execute(
        self,
        dag: DAGraph,
        context: dict[str, Any] | None = None,
    ) -> DAGResult:
        """执行 DAG。

        流程：
        1. 拓扑排序获取执行层级
        2. 逐层并行执行
        3. 收集结果并传递给下一层（context 注入）
        4. 处理条件分支（跳过不满足条件的节点）
        5. 处理失败（根据 max_retry 重试）
        6. 超时控制（asyncio.wait_for）

        Args:
            dag: DAG 图实例。
            context: 初始执行上下文。

        Returns:
            DAGResult 执行结果。
        """
        if context is None:
            context = {}

        dag_id = dag.dag_id
        start_time = time.perf_counter()
        results: dict[str, TaskResult] = {}

        logger.info(
            "dag_execution_started",
            dag_id=dag_id,
            node_count=len(dag.nodes),
        )

        try:
            # 拓扑排序获取层级
            levels = dag.topological_levels()

            if len(levels) > self._max_depth:
                raise ValueError(
                    f"DAG 执行深度 {len(levels)} 超过最大限制 {self._max_depth}"
                )

            # 逐层执行
            for level_idx, level in enumerate(levels):
                logger.debug(
                    "dag_executing_level",
                    dag_id=dag_id,
                    level=level_idx,
                    node_ids=level,
                )

                await self._execute_level(level, dag, context, results)

                # 检查层级执行结果，如有失败则终止后续层级
                level_failed = any(
                    results[nid].status == TaskStatus.FAILED.value
                    for nid in level
                    if nid in results
                )
                if level_failed:
                    error_msgs = [
                        results[nid].error
                        for nid in level
                        if nid in results and results[nid].status == TaskStatus.FAILED.value
                    ]
                    logger.error(
                        "dag_level_failed",
                        dag_id=dag_id,
                        level=level_idx,
                        errors=error_msgs,
                    )
                    return DAGResult(
                        dag_id=dag_id,
                        status=TaskStatus.FAILED.value,
                        task_results=results,
                        total_time_ms=(time.perf_counter() - start_time) * 1000,
                        error="; ".join(filter(None, error_msgs)),
                        execution_order=list(results.keys()),
                    )

            # 检查是否有全部被跳过的情况
            all_skipped = all(
                r.status == TaskStatus.SKIPPED.value
                for r in results.values()
            )
            if all_skipped:
                return DAGResult(
                    dag_id=dag_id,
                    status=TaskStatus.COMPLETED.value,
                    task_results=results,
                    total_time_ms=(time.perf_counter() - start_time) * 1000,
                    execution_order=list(results.keys()),
                )

            logger.info(
                "dag_execution_completed",
                dag_id=dag_id,
                task_count=len(results),
                total_time_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )

            return DAGResult(
                dag_id=dag_id,
                status=TaskStatus.COMPLETED.value,
                task_results=results,
                total_time_ms=(time.perf_counter() - start_time) * 1000,
                execution_order=list(results.keys()),
            )

        except Exception as exc:
            logger.error(
                "dag_execution_error",
                dag_id=dag_id,
                error=str(exc),
            )
            return DAGResult(
                dag_id=dag_id,
                status=TaskStatus.FAILED.value,
                task_results=results,
                total_time_ms=(time.perf_counter() - start_time) * 1000,
                error=str(exc),
                execution_order=list(results.keys()),
            )

    async def _execute_level(
        self,
        level: list[str],
        dag: DAGraph,
        context: dict[str, Any],
        results: dict[str, TaskResult],
    ) -> None:
        """并行执行同一层级的所有任务。

        Args:
            level: 当前层级的节点 ID 列表。
            dag: DAG 图实例。
            context: 执行上下文。
            results: 已有执行结果（会被更新）。
        """
        # 筛选需要执行的任务（跳过条件不满足的节点）
        tasks_to_execute: list[str] = []
        for node_id in level:
            node = dag.nodes[node_id]
            if self._should_skip(node, context, results):
                results[node_id] = TaskResult(
                    node_id=node_id,
                    status=TaskStatus.SKIPPED.value,
                )
                logger.debug(
                    "task_skipped",
                    node_id=node_id,
                    reason="条件分支不满足",
                )
            else:
                tasks_to_execute.append(node_id)

        if not tasks_to_execute:
            return

        # 并行执行
        coroutines = [
            self._execute_task_with_retry(dag.nodes[nid], context)
            for nid in tasks_to_execute
        ]
        level_results = await asyncio.gather(*coroutines, return_exceptions=True)

        for node_id, result in zip(tasks_to_execute, level_results):
            if isinstance(result, Exception):
                results[node_id] = TaskResult(
                    node_id=node_id,
                    status=TaskStatus.FAILED.value,
                    error=str(result),
                )
                logger.error(
                    "task_execution_exception",
                    node_id=node_id,
                    error=str(result),
                )
            else:
                results[node_id] = result
                # 将成功结果注入上下文，供下游节点使用
                if result.status == TaskStatus.COMPLETED.value:
                    context[f"__result_{node_id}"] = result.output

    async def _execute_task_with_retry(
        self,
        node: DAGNode,
        context: dict[str, Any],
    ) -> TaskResult:
        """执行单个任务，带重试逻辑。

        使用指数退避策略：base_delay * (2 ** attempt)。

        Args:
            node: DAG 节点实例。
            context: 执行上下文。

        Returns:
            TaskResult 执行结果。
        """
        node_id = node.node_id
        task_type = node.task_type
        config = node.config

        # 获取执行器
        try:
            executor = self._registry.get(task_type)
        except KeyError as exc:
            return TaskResult(
                node_id=node_id,
                status=TaskStatus.FAILED.value,
                error=str(exc),
            )

        last_error = ""
        retries = 0
        base_delay = 0.5  # 基础重试延迟（秒）

        for attempt in range(self._max_retry + 1):
            started_at = time.monotonic()
            task_start = time.perf_counter()

            try:
                output = await asyncio.wait_for(
                    executor.execute(node_id, config, context),
                    timeout=self._task_timeout,
                )

                completed_at = time.monotonic()
                execution_time_ms = (time.perf_counter() - task_start) * 1000

                logger.info(
                    "task_completed",
                    node_id=node_id,
                    task_type=task_type,
                    attempt=attempt,
                    execution_time_ms=round(execution_time_ms, 2),
                )

                return TaskResult(
                    node_id=node_id,
                    status=TaskStatus.COMPLETED.value,
                    output=output,
                    execution_time_ms=execution_time_ms,
                    retries=attempt,
                    started_at=started_at,
                    completed_at=completed_at,
                )

            except asyncio.TimeoutError:
                last_error = f"任务执行超时（{self._task_timeout}s）"
                logger.warning(
                    "task_timeout",
                    node_id=node_id,
                    task_type=task_type,
                    attempt=attempt,
                    timeout=self._task_timeout,
                )

            except asyncio.CancelledError:
                return TaskResult(
                    node_id=node_id,
                    status=TaskStatus.CANCELLED.value,
                    error="任务被取消",
                    retries=attempt,
                    started_at=time.monotonic(),
                )

            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "task_failed",
                    node_id=node_id,
                    task_type=task_type,
                    attempt=attempt,
                    error=last_error,
                )

            retries = attempt + 1

            # 如果还有重试机会，等待指数退避时间
            if attempt < self._max_retry:
                delay = base_delay * (2 ** attempt)
                logger.debug(
                    "task_retry_waiting",
                    node_id=node_id,
                    attempt=attempt,
                    next_delay=delay,
                )
                await asyncio.sleep(delay)

        # 所有重试均失败
        completed_at = time.monotonic()
        return TaskResult(
            node_id=node_id,
            status=TaskStatus.FAILED.value,
            error=last_error,
            retries=retries,
            started_at=0.0,
            completed_at=completed_at,
        )

    def _should_skip(
        self,
        node: DAGNode,
        context: dict[str, Any],
        results: dict[str, TaskResult],
    ) -> bool:
        """判断节点是否应该跳过（条件分支不满足时跳过）。

        如果节点没有条件表达式，始终执行。
        如果条件表达式为空字符串，也始终执行。

        Args:
            node: DAG 节点实例。
            context: 执行上下文。
            results: 已有执行结果。

        Returns:
            True 表示应该跳过。
        """
        condition = getattr(node, "condition", None)
        if not condition:
            return False

        # 如果有上游依赖且上游被跳过，当前节点也跳过
        upstream_ids = getattr(node, "dependencies", [])
        if upstream_ids:
            upstream_skipped = any(
                results.get(uid) and results[uid].status == TaskStatus.SKIPPED.value
                for uid in upstream_ids
            )
            if upstream_skipped:
                return True

        return not self._evaluate_condition(condition, context, results)

    def _evaluate_condition(
        self,
        condition: str,
        context: dict[str, Any],
        results: dict[str, TaskResult],
    ) -> bool:
        """评估条件表达式。

        支持简单表达式格式：
        - "context.key == value" — 检查上下文值
        - "result.node_id.key == value" — 检查上游节点结果
        - "always" — 始终为 True
        - "never" — 始终为 False

        Args:
            condition: 条件表达式字符串。
            context: 执行上下文。
            results: 已有执行结果。

        Returns:
            条件评估结果。
        """
        condition = condition.strip()

        # 特殊关键字
        if condition.lower() == "always":
            return True
        if condition.lower() == "never":
            return False

        # 解析 context. 前缀
        if condition.startswith("context."):
            key_path = condition[len("context."):]
            parts = key_path.split(".")
            value = context
            for part in parts:
                if isinstance(value, dict):
                    # 去除可能的 == value 部分
                    if " == " in part:
                        part_key, expected = part.split(" == ", 1)
                        actual = value.get(part_key)
                        return str(actual) == expected.strip("'\"")
                    value = value.get(part)
                else:
                    return False
            return bool(value)

        # 解析 result.node_id. 前缀
        if condition.startswith("result."):
            key_path = condition[len("result."):]
            parts = key_path.split(".")
            if len(parts) < 2:
                return False

            node_id = parts[0]
            task_result = results.get(node_id)
            if task_result is None:
                return False

            # 检查节点状态
            if parts[1] == "status":
                if len(parts) >= 3:
                    return task_result.status == parts[2]
                return task_result.status == TaskStatus.COMPLETED.value

            # 检查节点输出
            if parts[1] == "output" and task_result.output and len(parts) >= 3:
                output = task_result.output
                for key in parts[2:]:
                    if isinstance(output, dict):
                        output = output.get(key)
                    else:
                        return False
                return bool(output)

            return False

        logger.warning(
            "condition_unrecognized",
            condition=condition,
            message="无法识别的条件表达式，默认返回 True",
        )
        return True
