import { useState } from 'react';

interface EmptyStateProps {
  /** 点击示例查询时的回调 */
  onSendExample?: (question: string) => void;
  /** 是否显示新手引导 */
  showOnboarding?: boolean;
}

/** 快速开始查询示例 */
const QUICK_START_QUERIES = [
  '今天订单总量是多少？',
  '各产品类别的销售额占比',
  '最近 7 天的用户活跃趋势',
];

/**
 * 空状态组件 —— 无消息时显示欢迎语和快速开始查询
 */
export default function EmptyState({
  onSendExample,
}: EmptyStateProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  return (
    <div className="flex h-full flex-col items-center justify-center py-20">
      {/* DataPilot 图标 */}
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-500 to-primary-600 shadow-lg shadow-primary-500/20">
        <svg
          className="h-10 w-10 text-white"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5"
          />
        </svg>
      </div>

      {/* 欢迎语 */}
      <h3 className="mb-2 text-xl font-semibold text-gray-900">
        你好，我是 DataPilot 数据助手
      </h3>
      <p className="mb-8 text-sm text-gray-500">
        用自然语言提问，即可查询数据并生成可视化图表
      </p>

      {/* 快速开始查询 */}
      <div className="w-full max-w-lg space-y-2">
        <p className="mb-3 text-center text-xs font-medium tracking-wide text-gray-400 uppercase">
          试试问我
        </p>
        {QUICK_START_QUERIES.map((query, index) => (
          <button
            key={index}
            onClick={() => onSendExample?.(query)}
            onMouseEnter={() => setHoveredIndex(index)}
            onMouseLeave={() => setHoveredIndex(null)}
            className={`flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left text-sm transition-all duration-200 ${
              hoveredIndex === index
                ? 'border-primary-300 bg-primary-50 text-primary-700 shadow-sm'
                : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300 hover:bg-gray-50'
            }`}
          >
            {/* 序号标记 */}
            <span
              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-medium ${
                hoveredIndex === index
                  ? 'bg-primary-200 text-primary-700'
                  : 'bg-gray-100 text-gray-400'
              }`}
            >
              {index + 1}
            </span>
            <span className="flex-1">{query}</span>
            {/* 箭头 */}
            <svg
              className={`h-4 w-4 transition-transform duration-200 ${
                hoveredIndex === index
                  ? 'translate-x-0.5 text-primary-500'
                  : 'text-gray-300'
              }`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"
              />
            </svg>
          </button>
        ))}
      </div>
    </div>
  );
}
