"""工具注册表：工具的注册、发现、查询和 JSON Schema 生成。"""

from __future__ import annotations

from typing import Any

from datapilot_tools.models import ToolCategory, ToolDefinition
from datapilot_tools.description import ToolDescriptionBuilder


# 工具执行器类型：接收参数字典，返回执行结果
ToolExecutorFunc = Any


class ToolRegistry:
    """工具注册表，管理工具定义和执行器的注册与发现。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._executors: dict[str, ToolExecutorFunc] = {}
        self._description_builder = ToolDescriptionBuilder()

    def register(
        self,
        tool: ToolDefinition,
        executor: ToolExecutorFunc | None = None,
    ) -> None:
        """注册工具及其执行器。

        Args:
            tool: 工具定义。
            executor: 可选的工具执行器。
        """
        self._tools[tool.name] = tool
        if executor is not None:
            self._executors[tool.name] = executor

    def unregister(self, name: str) -> bool:
        """注销工具。

        Args:
            name: 工具名称。

        Returns:
            是否成功注销（工具是否存在）。
        """
        if name not in self._tools:
            return False
        del self._tools[name]
        self._executors.pop(name, None)
        return True

    def discover(self) -> list[ToolDefinition]:
        """发现所有已注册的工具。

        Returns:
            所有工具定义的列表。
        """
        return list(self._tools.values())

    def get(self, name: str) -> ToolDefinition | None:
        """获取工具定义。

        Args:
            name: 工具名称。

        Returns:
            工具定义，不存在时返回 None。
        """
        return self._tools.get(name)

    def get_executor(self, name: str) -> ToolExecutorFunc | None:
        """获取工具执行器。

        Args:
            name: 工具名称。

        Returns:
            工具执行器，不存在时返回 None。
        """
        return self._executors.get(name)

    def search_by_category(self, category: ToolCategory) -> list[ToolDefinition]:
        """按类别搜索工具。

        Args:
            category: 工具类别。

        Returns:
            匹配类别的工具定义列表。
        """
        return [tool for tool in self._tools.values() if tool.category == category]

    def search_by_capability(self, keyword: str) -> list[ToolDefinition]:
        """按关键词搜索工具（在 description 和 parameters 中搜索）。

        Args:
            keyword: 搜索关键词。

        Returns:
            匹配关键词的工具定义列表。
        """
        keyword_lower = keyword.lower()
        results: list[ToolDefinition] = []
        for tool in self._tools.values():
            if keyword_lower in tool.description.lower():
                results.append(tool)
                continue
            for param in tool.parameters:
                if (
                    keyword_lower in param.name.lower()
                    or keyword_lower in param.description.lower()
                ):
                    results.append(tool)
                    break
        return results

    def to_function_schemas(self) -> list[dict[str, Any]]:
        """生成 OpenAI Function Calling 格式的 tools JSON。

        Returns:
            符合 OpenAI tools 格式的字典列表。
        """
        return self._description_builder.build_all_schemas(self)
