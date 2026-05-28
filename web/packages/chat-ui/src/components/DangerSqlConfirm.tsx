interface DangerSqlConfirmProps {
  /** 待执行的 SQL */
  sql: string;
  /** 风险等级：high=高风险可确认，blocked=被阻止不可确认 */
  riskLevel: 'high' | 'blocked';
  /** 风险原因描述 */
  reason: string;
  /** 确认执行回调 */
  onConfirm: () => void;
  /** 取消回调 */
  onCancel: () => void;
}

/**
 * 危险 SQL 确认组件 —— 在执行高风险 SQL 前进行二次确认
 */
export default function DangerSqlConfirm({
  sql,
  riskLevel,
  reason,
  onConfirm,
  onCancel,
}: DangerSqlConfirmProps) {
  const isBlocked = riskLevel === 'blocked';

  return (
    <div className="rounded-xl border-2 border-red-300 bg-red-50 p-5">
      {/* 警告头部 */}
      <div className="mb-4 flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-100">
          <svg
            className="h-5 w-5 text-red-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
            />
          </svg>
        </div>
        <div className="flex-1">
          <h4 className="font-semibold text-red-800">
            {isBlocked ? 'SQL 已被阻止执行' : '危险操作警告'}
          </h4>
          <p className="mt-1 text-sm text-red-600">
            {isBlocked
              ? '当前 SQL 包含不允许的操作，已被安全策略拦截。'
              : '以下 SQL 包含高风险操作，请确认后再执行。'}
          </p>
        </div>
      </div>

      {/* 风险原因 */}
      <div className="mb-4 rounded-lg border border-red-200 bg-white px-4 py-3">
        <p className="mb-1 text-xs font-medium text-red-500">风险原因</p>
        <p className="text-sm text-red-700">{reason}</p>
      </div>

      {/* SQL 内容 */}
      <div className="mb-5 rounded-lg border border-red-200 bg-gray-900 p-4">
        <div className="mb-2 flex items-center gap-2">
          <span className="rounded bg-red-500/20 px-2 py-0.5 text-xs font-medium text-red-400">
            {riskLevel === 'high' ? 'HIGH RISK' : 'BLOCKED'}
          </span>
          <span className="text-xs text-gray-400">SQL</span>
        </div>
        <pre className="overflow-x-auto text-xs leading-relaxed text-gray-300">
          <code>{sql}</code>
        </pre>
      </div>

      {/* 操作按钮 */}
      <div className="flex items-center justify-end gap-3">
        <button
          onClick={onCancel}
          className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
        >
          取消
        </button>
        {!isBlocked && (
          <button
            onClick={onConfirm}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700"
          >
            确认执行
          </button>
        )}
      </div>
    </div>
  );
}
