"""LLM 任务执行器。

调用 datapilot-llm 的 LLMRouter 执行 LLM 推理任务。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from datapilot_dag.executor.base import BaseTaskExecutor

if TYPE_CHECKING:
    from datapilot_llm.router import LLMRouter

logger = structlog.get_logger(__name__)


class LLMTaskExecutor(BaseTaskExecutor):
    """LLM 任务执行器。

    通过 LLMRouter 调用大语言模型，支持多种使用场景。
    如果没有传入 llm_router，返回 mock 结果以支持开发调试。

    Attributes:
        _llm_router: LLMRouter 实例，可选。
    """

    def __init__(self, llm_router: LLMRouter | None = None) -> None:
        self._llm_router = llm_router
        self._cancelled_tasks: set[str] = set()

    async def execute(self, node_id: str, config: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行 LLM 推理任务。

        Args:
            node_id: 节点标识符。
            config: 任务配置，包含：
                - prompt: str — 提示词
                - scene: str — 使用场景 (nl2sql/intent/explanation/correction/chitchat)
                - response_format: str — 响应格式 (json/text)
            context: 执行上下文。

        Returns:
            LLM 响应文本或解析后的 JSON。

        Raises:
            RuntimeError: 节点已被取消。
        """
        if node_id in self._cancelled_tasks:
            raise RuntimeError(f"节点 {node_id} 已被取消")

        prompt: str = config.get("prompt", "")
        scene: str = config.get("scene", "nl2sql")
        response_format: str = config.get("response_format", "text")

        logger.debug(
            "llm_executor_execute",
            node_id=node_id,
            scene=scene,
            response_format=response_format,
            prompt_length=len(prompt),
        )

        if self._llm_router is None:
            logger.warning(
                "llm_executor_no_router",
                node_id=node_id,
                message="未配置 LLMRouter，返回 mock 结果",
            )
            return self._mock_result(prompt, scene, response_format)

        try:
            from datapilot_llm.router import Scene

            scene_enum = Scene(scene)
            json_mode = response_format == "json"

            response = await self._llm_router.generate(
                scene=scene_enum,
                prompt=prompt,
                json_mode=json_mode,
            )

            logger.info(
                "llm_executor_success",
                node_id=node_id,
                scene=scene,
                model=response.model,
                latency_ms=response.latency_ms,
            )

            return response.content

        except Exception as exc:
            logger.error(
                "llm_executor_failed",
                node_id=node_id,
                scene=scene,
                error=str(exc),
            )
            raise

    async def cancel(self, node_id: str) -> bool:
        """取消 LLM 任务。

        Args:
            node_id: 节点标识符。

        Returns:
            是否成功取消。
        """
        self._cancelled_tasks.add(node_id)
        logger.info("llm_executor_cancelled", node_id=node_id)
        return True

    @staticmethod
    def _mock_result(prompt: str, scene: str, response_format: str) -> dict[str, Any]:
        """生成 mock LLM 结果。

        Args:
            prompt: 原始提示词。
            scene: 使用场景。
            response_format: 响应格式。

        Returns:
            Mock 结果字典。
        """
        if response_format == "json":
            return {
                "content": '{"result": "mock llm response"}',
                "scene": scene,
                "mock": True,
            }
        return {
            "content": f"[mock {scene}] 响应提示词: {prompt[:50]}...",
            "scene": scene,
            "mock": True,
        }
