"""游标分页模块。

支持基于页码的分页和基于游标的分页两种模式。
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field


@dataclass
class PageResult:
    """分页结果。

    Attributes:
        columns: 列名列表。
        rows: 当前页的行数据。
        total_count: 总记录数。
        page: 当前页码（从 1 开始）。
        page_size: 每页大小。
        has_next: 是否有下一页。
        next_cursor: 下一页的游标，无下一页时为 None。
    """

    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    total_count: int = 0
    page: int = 1
    page_size: int = 20
    has_next: bool = False
    next_cursor: str | None = None


class CursorPaginator:
    """游标分页器。

    支持基于页码和基于游标的分页。游标使用 base64 编码的 JSON 字符串，
    包含页码和最后一条记录的值。

    Args:
        default_page_size: 默认每页大小，默认 20。
        max_page_size: 最大每页大小，默认 1000。
    """

    def __init__(
        self,
        default_page_size: int = 20,
        max_page_size: int = 1000,
    ) -> None:
        self._default_page_size = default_page_size
        self._max_page_size = max_page_size

    def paginate(
        self,
        columns: list[str],
        rows: list[dict],
        page: int = 1,
        page_size: int | None = None,
        cursor: str | None = None,
    ) -> PageResult:
        """对查询结果进行分页。

        优先使用游标分页，如果未提供游标则使用页码分页。

        Args:
            columns: 列名列表。
            rows: 全部行数据。
            page: 页码（从 1 开始），默认 1。
            page_size: 每页大小，默认使用构造函数的默认值。
            cursor: 游标字符串，优先于页码。

        Returns:
            PageResult 分页结果。
        """
        # 限制 page_size 范围
        if page_size is None:
            page_size = self._default_page_size
        page_size = max(1, min(page_size, self._max_page_size))

        # 如果提供了游标，解析游标获取页码
        if cursor is not None:
            page, _ = self.decode_cursor(cursor)

        total_count = len(rows)

        # 计算偏移量
        offset = (page - 1) * page_size
        end = offset + page_size

        page_rows = rows[offset:end]

        has_next = end < total_count

        # 生成下一页游标
        next_cursor: str | None = None
        if has_next and page_rows:
            last_row = page_rows[-1]
            # 使用第一列的值作为游标参考值
            last_value = str(last_row.get(columns[0], "")) if columns else ""
            next_cursor = self.encode_cursor(page + 1, last_value)

        return PageResult(
            columns=columns,
            rows=page_rows,
            total_count=total_count,
            page=page,
            page_size=page_size,
            has_next=has_next,
            next_cursor=next_cursor,
        )

    @staticmethod
    def encode_cursor(page: int, last_value: str | None = None) -> str:
        """编码游标。

        将页码和最后值编码为 base64 字符串。

        Args:
            page: 下一页页码。
            last_value: 最后一条记录的参考值。

        Returns:
            base64 编码的游标字符串。
        """
        data = {"page": page, "v": last_value}
        json_str = json.dumps(data, separators=(",", ":"))
        return base64.urlsafe_b64encode(json_str.encode("utf-8")).decode("utf-8")

    @staticmethod
    def decode_cursor(cursor: str) -> tuple[int, str | None]:
        """解码游标。

        将 base64 编码的游标字符串解码为页码和参考值。

        Args:
            cursor: base64 编码的游标字符串。

        Returns:
            元组 (页码, 参考值)。

        Raises:
            ValueError: 游标格式无效时抛出。
        """
        try:
            json_str = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
            data = json.loads(json_str)
            return data.get("page", 1), data.get("v")
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
            raise ValueError(f"无效的游标格式: {cursor}") from e
