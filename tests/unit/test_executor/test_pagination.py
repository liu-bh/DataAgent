"""游标分页单元测试。"""

import pytest

from datapilot_queryexec.executor.pagination import CursorPaginator, PageResult


class TestCursorPaginator:
    """CursorPaginator 测试。"""

    def setup_method(self) -> None:
        """准备测试数据。"""
        self.columns = ["id", "name"]
        self.rows = [
            {"id": i, "name": f"item_{i}"}
            for i in range(1, 11)  # 10 条数据
        ]
        self.paginator = CursorPaginator(default_page_size=3, max_page_size=10)

    def test_first_page(self) -> None:
        """测试第一页。"""
        result = self.paginator.paginate(self.columns, self.rows, page=1, page_size=3)
        assert result.columns == self.columns
        assert len(result.rows) == 3
        assert result.rows[0]["id"] == 1
        assert result.rows[2]["id"] == 3
        assert result.total_count == 10
        assert result.page == 1
        assert result.page_size == 3
        assert result.has_next is True
        assert result.next_cursor is not None

    def test_middle_page(self) -> None:
        """测试中间页。"""
        result = self.paginator.paginate(self.columns, self.rows, page=2, page_size=3)
        assert len(result.rows) == 3
        assert result.rows[0]["id"] == 4
        assert result.rows[2]["id"] == 6
        assert result.has_next is True

    def test_last_page(self) -> None:
        """测试最后一页。"""
        # 10 条数据，每页 3 条：第 4 页只有 1 条
        result = self.paginator.paginate(self.columns, self.rows, page=4, page_size=3)
        assert len(result.rows) == 1
        assert result.rows[0]["id"] == 10
        assert result.has_next is False
        assert result.next_cursor is None

    def test_beyond_last_page(self) -> None:
        """测试超出最后一页。"""
        result = self.paginator.paginate(self.columns, self.rows, page=5, page_size=3)
        assert len(result.rows) == 0
        assert result.has_next is False
        assert result.next_cursor is None

    def test_page_size_clamped_to_max(self) -> None:
        """测试 page_size 被限制到最大值。"""
        result = self.paginator.paginate(self.columns, self.rows, page=1, page_size=100)
        assert result.page_size == 10  # max_page_size
        assert len(result.rows) == 10

    def test_page_size_minimum(self) -> None:
        """测试 page_size 最小为 1。"""
        result = self.paginator.paginate(self.columns, self.rows, page=1, page_size=0)
        assert result.page_size == 1
        assert len(result.rows) == 1

    def test_page_size_negative(self) -> None:
        """测试 page_size 为负数时使用最小值。"""
        result = self.paginator.paginate(self.columns, self.rows, page=1, page_size=-5)
        assert result.page_size == 1

    def test_default_page_size(self) -> None:
        """测试默认 page_size。"""
        result = self.paginator.paginate(self.columns, self.rows, page=1)
        assert result.page_size == 3

    def test_empty_data(self) -> None:
        """测试空数据集。"""
        result = self.paginator.paginate([], [], page=1, page_size=10)
        assert len(result.rows) == 0
        assert result.total_count == 0
        assert result.has_next is False
        assert result.next_cursor is None

    def test_encode_decode_cursor(self) -> None:
        """测试游标编解码。"""
        cursor = CursorPaginator.encode_cursor(page=3, last_value="item_10")
        page, value = CursorPaginator.decode_cursor(cursor)
        assert page == 3
        assert value == "item_10"

    def test_encode_cursor_without_value(self) -> None:
        """测试无参考值的游标编码。"""
        cursor = CursorPaginator.encode_cursor(page=5)
        page, value = CursorPaginator.decode_cursor(cursor)
        assert page == 5
        assert value is None

    def test_decode_invalid_cursor(self) -> None:
        """测试解码无效游标抛出异常。"""
        with pytest.raises(ValueError, match="无效的游标格式"):
            CursorPaginator.decode_cursor("invalid-cursor")

    def test_decode_empty_cursor(self) -> None:
        """测试解码空字符串游标抛出异常。"""
        with pytest.raises(ValueError):
            CursorPaginator.decode_cursor("")

    def test_cursor_pagination(self) -> None:
        """测试使用游标进行分页。"""
        # 获取第一页
        page1 = self.paginator.paginate(self.columns, self.rows, page=1, page_size=3)
        assert page1.has_next is True

        # 使用第一页的游标获取第二页
        page2 = self.paginator.paginate(
            self.columns, self.rows, cursor=page1.next_cursor
        )
        assert page2.page == 2
        assert len(page2.rows) == 3
        assert page2.rows[0]["id"] == 4

    def test_cursor_overrides_page(self) -> None:
        """测试游标参数优先于页码。"""
        cursor = CursorPaginator.encode_cursor(page=3)
        result = self.paginator.paginate(
            self.columns, self.rows, page=1, cursor=cursor
        )
        assert result.page == 3

    def test_page_result_is_dataclass(self) -> None:
        """测试 PageResult 是 dataclass。"""
        result = PageResult(
            columns=["id"],
            rows=[{"id": 1}],
            total_count=1,
            page=1,
            page_size=1,
        )
        assert result.columns == ["id"]
        assert result.has_next is False
        assert result.next_cursor is None
