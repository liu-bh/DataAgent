"""结果格式化器单元测试。"""

import pytest

from datapilot_queryexec.executor.formatter import ResultFormatter
from datapilot_queryexec.executor.models import FormatType


class TestResultFormatter:
    """ResultFormatter 测试。"""

    def setup_method(self) -> None:
        """准备测试数据。"""
        self.columns = ["id", "name", "age"]
        self.rows = [
            {"id": 1, "name": "Alice", "age": 30},
            {"id": 2, "name": "Bob", "age": 25},
            {"id": 3, "name": "Charlie", "age": 35},
        ]

    def test_to_json_basic(self) -> None:
        """测试 JSON 格式化基本功能。"""
        result = ResultFormatter.to_json(self.columns, self.rows)
        assert result["columns"] == self.columns
        assert result["total_rows"] == 3
        assert len(result["data"]) == 3
        # 验证数据按列顺序排列
        assert result["data"][0] == [1, "Alice", 30]
        assert result["data"][1] == [2, "Bob", 25]
        assert result["data"][2] == [3, "Charlie", 35]

    def test_to_json_empty(self) -> None:
        """测试空数据集的 JSON 格式化。"""
        result = ResultFormatter.to_json([], [])
        assert result["columns"] == []
        assert result["data"] == []
        assert result["total_rows"] == 0

    def test_to_json_extra_columns_in_row(self) -> None:
        """测试行中包含额外列时只保留指定列。"""
        rows = [{"id": 1, "name": "Alice", "age": 30, "extra": "ignored"}]
        result = ResultFormatter.to_json(["id", "name"], rows)
        assert len(result["data"][0]) == 2
        assert result["data"][0] == [1, "Alice"]

    def test_to_json_missing_columns_in_row(self) -> None:
        """测试行中缺少某些列时使用 None。"""
        rows = [{"id": 1}]
        result = ResultFormatter.to_json(["id", "name"], rows)
        assert result["data"][0] == [1, None]

    def test_to_csv_basic(self) -> None:
        """测试 CSV 格式化基本功能。"""
        result = ResultFormatter.to_csv(self.columns, self.rows)

        # 验证 UTF-8 BOM
        assert result.startswith("\ufeff")

        # 验证内容包含表头和数据
        assert "id,name,age" in result
        assert "1,Alice,30" in result
        assert "2,Bob,25" in result
        assert "3,Charlie,35" in result

    def test_to_csv_empty(self) -> None:
        """测试空数据集的 CSV 格式化。"""
        result = ResultFormatter.to_csv([], [])
        assert result == "\ufeff"

    def test_to_csv_with_comma_in_value(self) -> None:
        """测试 CSV 值中包含逗号时正确转义。"""
        rows = [{"id": 1, "name": "Alice, Jr.", "age": 30}]
        result = ResultFormatter.to_csv(self.columns, rows)
        # 逗号应被引号包裹
        assert '"Alice, Jr."' in result

    def test_to_csv_column_order(self) -> None:
        """测试 CSV 列顺序。"""
        rows = [{"id": 1, "name": "Alice", "age": 30}]
        result = ResultFormatter.to_csv(["age", "id", "name"], rows)
        lines = result.strip().split("\n")
        # 跳过 BOM 行
        header_line = lines[0] if lines[0] == "\ufeff" or not lines[0].startswith("\ufeff") else lines[1]

    def test_format_json(self) -> None:
        """测试 format 方法 JSON 格式。"""
        result = ResultFormatter.format(self.columns, self.rows, FormatType.JSON)
        assert isinstance(result, dict)
        assert "columns" in result
        assert "data" in result

    def test_format_csv(self) -> None:
        """测试 format 方法 CSV 格式。"""
        result = ResultFormatter.format(self.columns, self.rows, FormatType.CSV)
        assert isinstance(result, str)
        assert result.startswith("\ufeff")

    def test_format_default(self) -> None:
        """测试 format 方法默认格式为 JSON。"""
        result = ResultFormatter.format(self.columns, self.rows)
        assert isinstance(result, dict)
