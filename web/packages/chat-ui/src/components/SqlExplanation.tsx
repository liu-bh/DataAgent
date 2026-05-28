interface SqlExplanationProps {
  /** SQL 自然语言解释 */
  explanation: string;
  /** 数据新鲜度提示 */
  freshnessNote?: string;
  /** 查询结果总行数 */
  totalRows?: number;
}

export default function SqlExplanation({
  explanation,
  freshnessNote,
  totalRows,
}: SqlExplanationProps) {
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2.5">
      {/* SQL 解释 */}
      <div className="flex items-start gap-2">
        <svg
          className="mt-0.5 h-3.5 w-3.5 shrink-0 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <p className="text-xs leading-relaxed text-gray-600">{explanation}</p>
      </div>

      {/* 底部元信息 */}
      <div className="mt-2 flex items-center gap-3 border-t border-gray-200 pt-2 text-xs text-gray-400">
        {totalRows !== undefined && (
          <span>共 {totalRows.toLocaleString()} 行</span>
        )}
        {freshnessNote && (
          <span className="flex items-center gap-1">
            <svg
              className="h-3 w-3"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            {freshnessNote}
          </span>
        )}
      </div>
    </div>
  );
}
