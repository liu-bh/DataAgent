"""Dashboard 过滤器。

应用过滤器到数据并验证过滤器值。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import DashboardFilterDef


class DashboardFilter:
    """Dashboard 数据过滤器。

    支持按字段值过滤数据列表，兼容 select、multi_select、time_range 类型。
    """

    def apply(
        self,
        data: list[dict[str, Any]],
        filters: dict[str, Any],
        filter_defs: list[DashboardFilterDef] | None = None,
    ) -> list[dict[str, Any]]:
        """应用过滤器到数据。

        Args:
            data: 原始数据列表。
            filters: 过滤器键值对，key 为 filter_id，value 为过滤值。
            filter_defs: 过滤器定义列表，用于匹配字段名。如果不提供，
                        则直接用 filter_id 作为字段名。

        Returns:
            过滤后的数据列表。
        """
        if not data or not filters:
            return list(data)

        # 构建 filter_id -> filter_def 映射
        filter_def_map: dict[str, DashboardFilterDef] = {}
        if filter_defs:
            for fd in filter_defs:
                filter_def_map[fd.filter_id] = fd

        result = list(data)

        for filter_id, filter_value in filters.items():
            if filter_value is None:
                continue

            # 获取对应的字段名
            if filter_id in filter_def_map:
                field_name = filter_def_map[filter_id].field
            else:
                field_name = filter_id

            # 根据过滤器定义判断是否为多选
            filter_type = (
                filter_def_map[filter_id].filter_type if filter_id in filter_def_map else "select"
            )

            if filter_type == "multi_select":
                if isinstance(filter_value, list):
                    result = [
                        row
                        for row in result
                        if str(row.get(field_name, "")) in [str(v) for v in filter_value]
                    ]
                else:
                    # 单个值当作单值匹配
                    result = [
                        row for row in result if str(row.get(field_name, "")) == str(filter_value)
                    ]
            else:
                # select / time_range: 精确匹配
                result = [
                    row for row in result if str(row.get(field_name, "")) == str(filter_value)
                ]

        return result

    def validate(
        self,
        filters: dict[str, Any],
        filter_defs: list[DashboardFilterDef],
    ) -> list[str]:
        """验证过滤器值是否合法。

        检查项：
        - 过滤器 ID 是否在定义中
        - 过滤器值是否在可选项中（如果有 options）
        - multi_select 过滤器值是否为列表

        Args:
            filters: 过滤器键值对。
            filter_defs: 过滤器定义列表。

        Returns:
            验证问题列表，空列表表示全部合法。
        """
        issues: list[str] = []
        filter_def_map = {fd.filter_id: fd for fd in filter_defs}

        for filter_id, filter_value in filters.items():
            # 检查过滤器 ID 是否在定义中
            if filter_id not in filter_def_map:
                issues.append(f"未知的过滤器 ID: '{filter_id}'")
                continue

            filter_def = filter_def_map[filter_id]

            # multi_select 类型值必须为列表
            if filter_def.filter_type == "multi_select" and not isinstance(filter_value, list):
                issues.append(
                    f"过滤器 '{filter_id}' 是 multi_select 类型，但值不是列表: {filter_value}"
                )
                continue

            # 检查值是否在可选项中（如果有 options）
            if filter_def.options:
                values_to_check = filter_value if isinstance(filter_value, list) else [filter_value]
                for val in values_to_check:
                    if str(val) not in [str(o) for o in filter_def.options]:
                        issues.append(
                            f"过滤器 '{filter_id}' 的值 '{val}' 不在可选项中: {filter_def.options}"
                        )

        return issues
