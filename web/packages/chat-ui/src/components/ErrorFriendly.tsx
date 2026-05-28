interface ErrorFriendlyProps {
  /** 错误类型 */
  errorType:
    | 'no_match'
    | 'timeout'
    | 'out_of_scope'
    | 'quota_exceeded'
    | 'unknown';
  /** 原始错误信息 */
  errorMessage?: string;
  /** 重试回调 */
  onRetry?: () => void;
  /** 建议查询回调 */
  onSuggest?: (suggestion: string) => void;
}

/** 各错误类型的配置 */
const ERROR_CONFIG = {
  no_match: {
    icon: 'M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z',
    title: '未找到匹配的指标',
    description: '未找到匹配的指标，请尝试更换描述方式',
    suggestions: [
      '使用更精确的业务术语',
      '检查指标名称是否有拼写差异',
      '尝试拆分为多个简单问题',
    ],
    actionLabel: null,
  },
  timeout: {
    icon: 'M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z',
    title: '查询超时',
    description: '查询超时，请尝试缩小查询范围或添加 LIMIT',
    suggestions: [
      '缩小时间范围，例如只查询近 7 天',
      '添加 LIMIT 限制返回行数',
      '减少查询的维度数量',
    ],
    actionLabel: null,
  },
  out_of_scope: {
    icon: 'M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636',
    title: '超出查询范围',
    description: '这个问题超出数据查询范围，试试问我数据相关的问题',
    suggestions: [
      '今天订单总量是多少？',
      '各产品类别的销售额占比',
      '最近 7 天的用户活跃趋势',
    ],
    actionLabel: '试试这些问题',
  },
  quota_exceeded: {
    icon: 'M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z',
    title: '查询次数已达上限',
    description: '今日查询次数已达上限，请明天再试或联系管理员',
    suggestions: [
      '当前每日免费额度为 100 次',
      '如需更多查询次数，请联系管理员提升额度',
    ],
    actionLabel: null,
  },
  unknown: {
    icon: 'M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z',
    title: '出了点问题',
    description: '服务暂时出现异常，请稍后再试',
    suggestions: [],
    actionLabel: null,
  },
};

/**
 * 友好错误提示组件 —— 将技术错误转化为用户易懂的提示
 */
export default function ErrorFriendly({
  errorType,
  errorMessage,
  onRetry,
  onSuggest,
}: ErrorFriendlyProps) {
  const config = ERROR_CONFIG[errorType];
  const isUnknown = errorType === 'unknown';
  const isNoMatch = errorType === 'no_match';

  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50 p-5">
      {/* 错误头部 */}
      <div className="mb-3 flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-orange-100">
          <svg
            className="h-5 w-5 text-orange-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d={config.icon}
            />
          </svg>
        </div>
        <div className="flex-1">
          <h4 className="font-medium text-gray-900">{config.title}</h4>
          <p className="mt-0.5 text-sm text-gray-500">{config.description}</p>
        </div>
      </div>

      {/* 原始错误信息（折叠） */}
      {errorMessage && errorMessage !== config.description && (
        <details className="mb-3">
          <summary className="cursor-pointer text-xs text-gray-400 hover:text-gray-600">
            技术详情
          </summary>
          <pre className="mt-2 overflow-x-auto rounded-lg bg-gray-900 p-3 text-xs text-gray-400">
            {errorMessage}
          </pre>
        </details>
      )}

      {/* 建议列表 */}
      {config.suggestions.length > 0 && (
        <div className="mb-4 space-y-2">
          <p className="text-xs font-medium text-gray-400">建议</p>
          <ul className="space-y-1.5">
            {config.suggestions.map((suggestion, index) => (
              <li key={index}>
                {onSuggest && (isNoMatch || errorType === 'out_of_scope') ? (
                  <button
                    onClick={() => onSuggest(suggestion)}
                    className="flex w-full items-start gap-2 rounded-lg px-3 py-2 text-left text-sm text-gray-600 transition-colors hover:bg-white hover:text-primary-600"
                  >
                    <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-gray-200 text-[10px] text-gray-500">
                      {index + 1}
                    </span>
                    <span>{suggestion}</span>
                  </button>
                ) : (
                  <span className="flex items-start gap-2 px-3 py-1 text-sm text-gray-500">
                    <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-gray-200 text-[10px] text-gray-500">
                      {index + 1}
                    </span>
                    <span>{suggestion}</span>
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 操作按钮 */}
      {(isUnknown || config.actionLabel) && (
        <div className="flex items-center gap-2">
          {isUnknown && onRetry && (
            <button
              onClick={onRetry}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700"
            >
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182"
                />
              </svg>
              重试
            </button>
          )}
        </div>
      )}
    </div>
  );
}
