"""查询结果格式化。

支持 JSON 和 CSV 两种格式输出，CSV 使用带 BOM 的 UTF-8 编码。
"""

from __future__ import annotations

import csv
import io
from typing import Any

from datapilot_queryexec.executor.models import FormatType


class ResultFormatter:
    """查询结果格式化器。

    提供 JSON 和 CSV 两种格式的转换能力。
    """

    @staticmethod
    def to_json(columns: list[str], rows: list[dict]) -> dict[str, Any]:
        """将查询结果转换为 JSON 格式。

        Args:
            columns: 列名列表。
            rows: 行数据列表，每行为 {列名: 值} 的字典。

        Returns:
            包含 columns 和 data 的字典。
        """
        # 确保每行只保留 columns 中定义的列，按列顺序排列
        formatted_rows: list[list[Any]] = []
        for row in rows:
            formatted_rows.append([row.get(col) for col in columns])

        return {
            "columns": columns,
            "data": formatted_rows,
            "total_rows": len(rows),
        }

    @staticmethod
    def to_csv(columns: list[str], rows: list[dict]) -> str:
        """将查询结果转换为 CSV 格式。

        使用带 BOM 的 UTF-8 编码，方便 Excel 直接打开。

        Args:
            columns: 列名列表。
            rows: 行数据列表，每行为 {列名: 值} 的字典。

        Returns:
            CSV 格式字符串。
        """
        output = io.StringIO()
        # 写入 UTF-8 BOM
        output.write("\ufeff")
        writer = csv.writer(output)

        # 写入表头
        writer.writerow(columns)

        # 写入数据行，按列顺序
        for row in rows:
            writer.writerow([row.get(col) for col in columns])

        return output.getvalue()

    @staticmethod
    def format(
        columns: list[str],
        rows: list[dict],
        fmt: FormatType = FormatType.JSON,
    ) -> Any:
        """根据格式类型格式化查询结果。

        Args:
            columns: 列名列表。
            rows: 行数据列表。
            fmt: 目标格式类型。

        Returns:
            JSON 格式返回 dict，CSV 格式返回 str。
        """
        if fmt == FormatType.CSV:
            return ResultFormatter.to_csv(columns, rows)
        return ResultFormatter.to_json(columns, rows)
