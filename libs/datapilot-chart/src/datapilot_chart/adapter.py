"""数据适配器。

将查询结果（columns + rows）适配为 ChartSeries 列表，并支持自动检测轴字段。
"""

from __future__ import annotations

from typing import Any

from datapilot_chart.models import ChartSeries


class DataAdapter:
    """查询结果到图表数据的适配器。"""

    def adapt(
        self,
        columns: list[str],
        rows: list[list[Any]],
        x_field: str | None = None,
        y_fields: list[str] | None = None,
    ) -> list[ChartSeries]:
        """将查询结果适配为 ChartSeries 列表。

        Args:
            columns: 列名列表。
            rows: 数据行列表。
            x_field: 指定 x 轴字段名，None 则自动检测。
            y_fields: 指定 y 轴字段名列表，None 则使用除 x 外的所有列。

        Returns:
            ChartSeries 列表。
        """
        if not columns or not rows:
            return []

        if x_field is None or y_fields is None:
            x_field, y_fields = self.detect_axes(columns, rows)

        # 确保字段名在 columns 中存在
        if x_field not in columns:
            x_field = columns[0]
        y_fields = [f for f in y_fields if f in columns]
        if not y_fields:
            return []

        x_index = columns.index(x_field)
        y_indices = [columns.index(f) for f in y_fields]

        # 提取 x 轴数据
        x_data: list[Any] = []
        for row in rows:
            if x_index < len(row):
                x_data.append(row[x_index])

        # 为每个 y 字段创建一个 series
        series_list: list[ChartSeries] = []
        for y_field, y_idx in zip(y_fields, y_indices, strict=True):
            y_data: list[Any] = []
            for row in rows:
                if y_idx < len(row):
                    y_data.append(row[y_idx])
            series_list.append(
                ChartSeries(
                    name=y_field,
                    data=y_data,
                )
            )

        # 同时将 x_data 存到第一个 series 的 data 中（用于轴标签提取）
        if series_list and x_data:
            # 用 x_data 作为第一个 series 的 data（适配 ECharts 的 x 轴标签）
            # 实际上 ECharts 的 x 轴标签通常单独设置
            # 这里我们选择在第一个 series 的 encode 中标记
            series_list[0].encode = {"x": x_field}

        return series_list

    def detect_axes(
        self,
        columns: list[str],
        rows: list[list[Any]],
    ) -> tuple[str, list[str]]:
        """自动检测推荐的 x/y 轴字段。

        策略：
        - x 轴优先选择时间类型或文本类型列
        - y 轴优先选择数值类型列
        - 如果没有数值列，选择剩余列

        Args:
            columns: 列名列表。
            rows: 数据行列表。

        Returns:
            (x_field, y_fields) 元组。
        """
        if not columns:
            return "", []

        if not rows:
            # 没有数据时，第一列作为 x，其余作为 y
            return columns[0], columns[1:] if len(columns) > 1 else []

        # 分析每列的数据类型
        col_types: dict[str, str] = {}
        for i, col in enumerate(columns):
            col_values = [row[i] for row in rows if i < len(row) and row[i] is not None]
            col_types[col] = self._classify_column(col_values)

        # 分类列
        time_cols = [c for c, t in col_types.items() if t == "time"]
        text_cols = [c for c, t in col_types.items() if t == "text"]
        numeric_cols = [c for c, t in col_types.items() if t == "numeric"]

        # 选择 x 轴：优先时间列，其次文本列
        x_field: str = ""
        if time_cols:
            x_field = time_cols[0]
        elif text_cols:
            x_field = text_cols[0]
        elif columns:
            x_field = columns[0]

        # 选择 y 轴：数值列
        y_fields = [c for c in numeric_cols if c != x_field]

        # 如果没有数值列，使用非 x 的列
        if not y_fields:
            y_fields = [c for c in columns if c != x_field]

        return x_field, y_fields

    @staticmethod
    def _classify_column(values: list[Any]) -> str:
        """分类列数据类型。

        Returns:
            "time", "numeric", 或 "text"。
        """
        if not values:
            return "text"

        numeric_count = 0
        time_count = 0

        for v in values:
            if isinstance(v, (int, float)):
                numeric_count += 1
            elif isinstance(v, str):
                # 简单的时间检测
                for sep in ["-", "/", "T"]:
                    if sep in v and len(v) >= 8:
                        time_count += 1
                        break

        total = len(values)
        if time_count / total >= 0.6:
            return "time"
        if numeric_count / total >= 0.6:
            return "numeric"
        return "text"
