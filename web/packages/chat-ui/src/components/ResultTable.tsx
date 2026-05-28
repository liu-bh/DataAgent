import { useState, useMemo, useCallback } from 'react';

interface ResultTableProps {
  /** 列名列表 */
  columns: string[];
  /** 查询结果数据 */
  data: Record<string, unknown>[];
  /** 最大高度（CSS 值） */
  maxHeight?: string;
}

/** 每页显示条数 */
const PAGE_SIZE = 20;

export default function ResultTable({
  columns,
  data,
  maxHeight,
}: ResultTableProps) {
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [currentPage, setCurrentPage] = useState(1);

  /** 排序后的数据 */
  const sortedData = useMemo(() => {
    if (!sortColumn) return [...data];

    return [...data].sort((a, b) => {
      const aVal = a[sortColumn];
      const bVal = b[sortColumn];

      // null 值排到最后
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;

      let comparison = 0;
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        comparison = aVal - bVal;
      } else {
        comparison = String(aVal).localeCompare(String(bVal), 'zh-CN');
      }

      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }, [data, sortColumn, sortDirection]);

  /** 总页数 */
  const totalPages = Math.max(1, Math.ceil(sortedData.length / PAGE_SIZE));

  /** 当前页数据 */
  const pageData = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return sortedData.slice(start, start + PAGE_SIZE);
  }, [sortedData, currentPage]);

  /** 点击表头排序 */
  const handleSort = useCallback(
    (column: string) => {
      if (sortColumn === column) {
        setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortColumn(column);
        setSortDirection('asc');
      }
      setCurrentPage(1);
    },
    [sortColumn],
  );

  /** 导出 CSV */
  const handleExportCsv = useCallback(() => {
    if (data.length === 0) return;

    const header = columns.join(',');
    const rows = data.map((row) =>
      columns
        .map((col) => {
          const val = row[col];
          if (val == null) return '';
          const strVal = String(val);
          // CSV 中包含逗号或引号的值需要用双引号包裹
          if (strVal.includes(',') || strVal.includes('"') || strVal.includes('\n')) {
            return `"${strVal.replace(/"/g, '""')}"`;
          }
          return strVal;
        })
        .join(','),
    );

    const csv = [header, ...rows].join('\n');
    const blob = new Blob(['\uFEFF' + csv], {
      type: 'text/csv;charset=utf-8;',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `query-result-${Date.now()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }, [data, columns]);

  /** 排序指示图标 */
  const SortIcon = ({ column }: { column: string }) => {
    if (sortColumn !== column) {
      return (
        <svg
          className="ml-1 inline h-3 w-3 text-gray-300"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"
          />
        </svg>
      );
    }
    return sortDirection === 'asc' ? (
      <svg
        className="ml-1 inline h-3 w-3 text-primary-600"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M5 15l7-7 7 7"
        />
      </svg>
    ) : (
      <svg
        className="ml-1 inline h-3 w-3 text-primary-600"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M19 9l-7 7-7-7"
        />
      </svg>
    );
  };

  /** 空数据 */
  if (data.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-8 text-center text-sm text-gray-400">
        暂无数据
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* 工具栏：总数 + 导出 */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500">
          共 {data.length.toLocaleString()} 条记录
        </span>
        <button
          onClick={handleExportCsv}
          className="flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-800"
        >
          <svg
            className="h-3.5 w-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
            />
          </svg>
          导出 CSV
        </button>
      </div>

      {/* 表格 */}
      <div
        className="overflow-x-auto rounded-lg border border-gray-200"
        style={maxHeight ? { maxHeight } : undefined}
      >
        <table className="w-full text-xs">
          <thead className="sticky top-0 z-10">
            <tr className="bg-gray-50 border-b border-gray-200">
              {columns.map((col) => (
                <th
                  key={col}
                  onClick={() => handleSort(col)}
                  className="cursor-pointer select-none px-3 py-2 text-left font-medium text-gray-600 whitespace-nowrap transition-colors hover:bg-gray-100"
                >
                  {col}
                  <SortIcon column={col} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageData.map((row, idx) => (
              <tr
                key={idx}
                className="border-b border-gray-100 last:border-b-0 transition-colors hover:bg-gray-50"
              >
                {columns.map((col) => (
                  <td
                    key={col}
                    className="px-3 py-2 text-gray-700 whitespace-nowrap max-w-[200px] truncate"
                    title={String(row[col] ?? '')}
                  >
                    {row[col] === null ? (
                      <span className="text-gray-300">NULL</span>
                    ) : (
                      String(row[col])
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">
            第 {(currentPage - 1) * PAGE_SIZE + 1}-
            {Math.min(currentPage * PAGE_SIZE, data.length)} 条，共{' '}
            {data.length.toLocaleString()} 条
          </span>
          <div className="flex items-center gap-1">
            {/* 上一页 */}
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
              className="rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600 transition-colors hover:bg-gray-50 disabled:border-gray-100 disabled:bg-gray-50 disabled:text-gray-300 disabled:cursor-not-allowed"
            >
              上一页
            </button>

            {/* 页码按钮 */}
            {generatePageNumbers(currentPage, totalPages).map((page, idx) =>
              page === '...' ? (
                <span
                  key={`ellipsis-${idx}`}
                  className="px-1 text-xs text-gray-400"
                >
                  ...
                </span>
              ) : (
                <button
                  key={page}
                  onClick={() => setCurrentPage(page as number)}
                  className={`rounded px-2 py-1 text-xs transition-colors ${
                    currentPage === page
                      ? 'bg-primary-600 text-white'
                      : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {page}
                </button>
              ),
            )}

            {/* 下一页 */}
            <button
              onClick={() =>
                setCurrentPage((p) => Math.min(totalPages, p + 1))
              }
              disabled={currentPage >= totalPages}
              className="rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600 transition-colors hover:bg-gray-50 disabled:border-gray-100 disabled:bg-gray-50 disabled:text-gray-300 disabled:cursor-not-allowed"
            >
              下一页
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/** 生成页码数组（含省略号） */
function generatePageNumbers(
  current: number,
  total: number,
): (number | '...')[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: (number | '...')[] = [1];

  if (current > 3) {
    pages.push('...');
  }

  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);

  for (let i = start; i <= end; i++) {
    pages.push(i);
  }

  if (current < total - 2) {
    pages.push('...');
  }

  pages.push(total);

  return pages;
}
