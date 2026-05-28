"""工具参数校验器。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datapilot_tools.models import ToolDefinition, ToolParameter


class ToolParameterValidator:
    """工具参数校验器，对传入参数进行检查。"""

    def validate(self, tool: ToolDefinition, params: dict[str, Any]) -> list[str]:
        """校验工具参数。

        Args:
            tool: 工具定义。
            params: 待校验的参数字典。

        Returns:
            错误消息列表，空列表表示校验通过。
        """
        errors: list[str] = []

        # 校验必填参数
        for param in tool.parameters:
            if param.required and param.name not in params and param.default is None:
                errors.append(f"缺少必填参数: {param.name}")

        # 校验每个传入的参数
        for name, value in params.items():
            param = self._find_param(tool, name)
            if param is None:
                errors.append(f"未知参数: {name}")
                continue

            self._validate_type(param, value, errors)
            self._validate_enum(param, value, errors)
            self._validate_range(param, value, errors)

        return errors

    def _find_param(self, tool: ToolDefinition, name: str) -> ToolParameter | None:
        """根据名称查找参数定义。"""
        for param in tool.parameters:
            if param.name == name:
                return param
        return None

    def _validate_type(self, param: ToolParameter, value: Any, errors: list[str]) -> None:
        """校验参数类型。"""
        type_map: dict[str, type | tuple[type, ...]] = {
            "string": str,
            "integer": int,
            "float": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        expected_type = type_map.get(param.type)
        if expected_type is None:
            return
        if not isinstance(value, expected_type):
            # integer 允许 float（如 1.0 应视为合法 integer）
            if param.type == "integer" and isinstance(value, float) and value == int(value):
                return
            errors.append(
                f"参数 '{param.name}' 类型错误: 期望 {param.type}, 实际 {type(value).__name__}"
            )

    def _validate_enum(self, param: ToolParameter, value: Any, errors: list[str]) -> None:
        """校验枚举值。"""
        if param.enum is not None and value not in param.enum:
            errors.append(f"参数 '{param.name}' 值 '{value}' 不在允许的枚举列表中: {param.enum}")

    def _validate_range(self, param: ToolParameter, value: Any, errors: list[str]) -> None:
        """校验数值范围。"""
        if not isinstance(value, (int, float)):
            return
        if param.minimum is not None and value < param.minimum:
            errors.append(f"参数 '{param.name}' 值 {value} 小于最小值 {param.minimum}")
        if param.maximum is not None and value > param.maximum:
            errors.append(f"参数 '{param.name}' 值 {value} 大于最大值 {param.maximum}")
