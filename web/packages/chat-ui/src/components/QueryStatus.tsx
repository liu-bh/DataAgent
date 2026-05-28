import type { QueryStatusType } from '@/types/api';

interface QueryStatusProps {
  /** 当前查询状态 */
  status: QueryStatusType;
  /** 错误信息 */
  errorMessage?: string;
  /** 重试回调 */
  onRetry?: () => void;
}

/** 各状态对应的展示文案和动画 */
const STATUS_CONFIG: Record<
  Exclude<QueryStatusType, 'idle' | 'done' | 'error'>,
  { label: string }
> = {
  analyzing_intent: { label: '正在分析意图...' },
  generating_sql: { label: '正在生成 SQL...' },
  executing: { label: '正在执行查询...' },
};

export default function QueryStatus({
  status,
  errorMessage,
  onRetry,
}: QueryStatusProps) {
  // idle 和 done 不展示
  if (status === 'idle' || status === 'done') return null;

  const isFailed = status === 'error';
  const config = !isFailed ? STATUS_CONFIG[status] : null;

  return (
    <div className="flex justify-start mb-4">
      <div
        className={`flex items-center gap-2.5 rounded-2xl px-4 py-3 shadow-sm border ${
          isFailed
            ? 'bg-red-50 border-red-200'
            : 'bg-white border-gray-100'
        }`}
      >
        {/* 旋转动画 */}
        {!isFailed && (
          <svg
            className="h-4 w-4 animate-spin text-primary-500"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )}

        {/* 错误图标 */}
        {isFailed && (
          <svg
            className="h-4 w-4 text-red-500 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
            />
          </svg>
        )}

        {/* 状态文字 */}
        <div className="flex items-center gap-2">
          <span
            className={`text-sm ${
              isFailed ? 'text-red-600' : 'text-gray-500'
            }`}
          >
            {isFailed ? '查询失败' : config?.label}
          </span>

          {/* 错误详情和重试 */}
          {isFailed && errorMessage && (
            <>
              <span className="text-xs text-red-400">
                {errorMessage}
              </span>
              {onRetry && (
                <button
                  onClick={onRetry}
                  className="ml-1 rounded-md bg-red-100 px-2 py-0.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-200"
                >
                  重试
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
