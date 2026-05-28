"""图表类型推断引擎。

根据数据列的类型和分布，推荐最合适的图表类型。
"""

from __future__ import annotations

from enum import StrEnum

from datapilot_chart.models import ChartType


class _ColumnType(StrEnum):
    """内部使用的列类型标识。"""

    TEXT = "text"
    NUMERIC = "numeric"
    TIME = "time"
    PERCENTAGE = "percentage"


def _detect_column_type(values: list) -> _ColumnType:
    """检测一列数据的类型。

    按优先级判断：time > percentage > numeric > text。
    """
    if not values:
        return _ColumnType.TEXT

    numeric_count = 0
    time_count = 0
    percentage_count = 0

    for v in values:
        if v is None:
            continue
        # 检测时间类型
        if isinstance(v, str):
            if _is_time_value(v):
                time_count += 1
                continue
            # 检测百分比
            if _is_percentage_value(v):
                percentage_count += 1
                continue
        if isinstance(v, (int, float)):
            numeric_count += 1

    total = len(values)
    if total == 0:
        return _ColumnType.TEXT

    non_none_total = sum(1 for v in values if v is not None)
    if non_none_total == 0:
        return _ColumnType.TEXT

    # 超过 60% 认为是该类型
    if time_count / non_none_total >= 0.6:
        return _ColumnType.TIME
    if percentage_count / non_none_total >= 0.6:
        return _ColumnType.PERCENTAGE
    if numeric_count / non_none_total >= 0.6:
        return _ColumnType.NUMERIC

    return _ColumnType.TEXT


def _is_time_value(value: str) -> bool:
    """判断字符串是否为时间值。"""
    # 常见日期格式特征
    time_separators = ["-", "/", "T"]
    time_keywords = ["年", "月", "日", "时", "分", "秒"]
    for sep in time_separators:
        if sep in value and len(value) >= 8:
            return True
    return any(kw in value for kw in time_keywords)


def _is_percentage_value(value: str) -> bool:
    """判断字符串是否为百分比值。"""
    return value.endswith("%")


class ChartTypeInferrer:
    """图表类型推断器。

    根据数据列的类型组合，推荐最合适的图表类型并按匹配度排序。
    """

    def infer(
        self,
        columns: list[str],
        rows: list[list],
    ) -> list[ChartType]:
        """根据数据列类型推荐图表类型。

        Args:
            columns: 列名列表。
            rows: 数据行列表，每行是值的列表。

        Returns:
            按匹配度排序的 ChartType 列表，匹配度最高的在前。
        """
        if not columns or not rows:
            return [ChartType.BAR]

        # 转置得到各列的值
        col_count = len(columns)
        col_values: dict[str, list] = {col: [] for col in columns}
        for row in rows:
            for i, col in enumerate(columns):
                if i < col_count and i < len(row):
                    col_values[col].append(row[i])

        # 检测每列的类型
        col_types: dict[str, _ColumnType] = {}
        for col, vals in col_values.items():
            col_types[col] = _detect_column_type(vals)

        type_counts = {
            _ColumnType.TEXT: sum(1 for t in col_types.values() if t == _ColumnType.TEXT),
            _ColumnType.NUMERIC: sum(1 for t in col_types.values() if t == _ColumnType.NUMERIC),
            _ColumnType.TIME: sum(1 for t in col_types.values() if t == _ColumnType.TIME),
            _ColumnType.PERCENTAGE: sum(
                1 for t in col_types.values() if t == _ColumnType.PERCENTAGE
            ),
        }

        has_time = type_counts[_ColumnType.TIME] > 0
        has_numeric = type_counts[_ColumnType.NUMERIC] > 0
        has_text = type_counts[_ColumnType.TEXT] > 0
        has_percentage = type_counts[_ColumnType.PERCENTAGE] > 0
        text_count = type_counts[_ColumnType.TEXT]
        numeric_count = type_counts[_ColumnType.NUMERIC]

        scores: dict[ChartType, int] = {}

        # 时间 + 数值 -> line
        if has_time and has_numeric:
            scores[ChartType.LINE] = 100
            scores[ChartType.BAR] = 70

        # 维度(文本) + 数值 -> bar
        if has_text and has_numeric:
            scores[ChartType.BAR] = max(scores.get(ChartType.BAR, 0), 90)
            # 少量维度 -> pie（文本列的唯一值数量少于等于行数的一定比例时）
            if text_count == 1 and rows:
                text_col = next((c for c, t in col_types.items() if t == _ColumnType.TEXT), None)
                if text_col:
                    unique_vals = set(col_values[text_col])
                    if 2 <= len(unique_vals) <= min(8, len(rows)):
                        scores[ChartType.PIE] = 95

        # 双数值 -> scatter
        if numeric_count >= 2 and not has_text and not has_time:
            scores[ChartType.SCATTER] = 95
            scores[ChartType.LINE] = max(scores.get(ChartType.LINE, 0), 60)

        # 多维度 -> radar
        if numeric_count >= 3 and text_count == 1:
            scores[ChartType.RADAR] = 80

        # 数值 + 百分比 -> gauge
        if has_percentage and numeric_count >= 1:
            scores[ChartType.GAUGE] = 85

        # 纯文本列 -> table
        if has_text and not has_numeric and not has_time:
            scores[ChartType.TABLE] = 90

        # 如果没有任何规则命中，默认 bar
        if not scores:
            scores[ChartType.BAR] = 50
            scores[ChartType.TABLE] = 60

        # 按分数降序排序
        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [ct for ct, _ in sorted_types]
