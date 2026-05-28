"""工具描述构建器：生成符合 OpenAI Function Calling 格式的 JSON Schema。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datapilot_tools.models import ToolDefinition
    from datapilot_tools.registry import ToolRegistry


class ToolDescriptionBuilder:
    """构建工具的 JSON Schema 描述。"""

    def build_tool_schema(self, tool: ToolDefinition) -> dict[str, Any]:
        """生成单个工具的 JSON Schema。

        Args:
            tool: 工具定义。

        Returns:
            符合 OpenAI Function Calling 格式的字典。
        """
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param in tool.parameters:
            prop: dict[str, Any] = {"type": param.type, "description": param.description}
            if param.enum is not None:
                prop["enum"] = list(param.enum)
            if param.minimum is not None:
                prop["minimum"] = param.minimum
            if param.maximum is not None:
                prop["maximum"] = param.maximum
            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        parameters_schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }
        parameters_schema["required"] = required

        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": parameters_schema,
            },
        }

    def build_all_schemas(self, registry: ToolRegistry) -> list[dict[str, Any]]:
        """生成注册表中所有工具的 JSON Schema。

        Args:
            registry: 工具注册表。

        Returns:
            符合 OpenAI Function Calling 格式的字典列表。
        """
        tools = registry.discover()
        return [self.build_tool_schema(tool) for tool in tools]
