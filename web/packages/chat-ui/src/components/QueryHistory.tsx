import type { QueryHistoryItem } from '@/types/api';

interface QueryHistoryProps {
  /** 查询历史列表 */
  history: QueryHistoryItem[];
  /** 一键复用查询 */
  onReuse: (question: string) => void;
  /** 切换收藏状态 */
  onToggleStar: (id: string) => void;
  /** 清空历史 */
  onClear?: () => void;
}

/**
 * 查询历史组件
 * 展示用户的查询历史列表，支持收藏、复用和清空操作
 */
export default function QueryHistory({
  history,
  onReuse,
  onToggleStar,
  onClear,
}: QueryHistoryProps) {
  if (history.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 px-4">
        <svg
          className="mb-3 h-10 w-10 text-gray-300"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <p className="text-sm text-gray-400">暂无查询历史</p>
      </div>
    );
  }

  /** 格式化时间显示 */
  const formatTime = (isoString: string): string => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMinutes < 1) return '刚刚';
    if (diffMinutes < 60) return `${diffMinutes} 分钟前`;
    if (diffHours < 24) return `${diffHours} 小时前`;
    if (diffDays < 7) return `${diffDays} 天前`;
    return date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="flex h-full flex-col">
      {/* 列表头 */}
      <div className="flex items-center justify-between px-3 py-2">
        <span className="text-xs font-medium text-gray-400">
          共 {history.length} 条记录
        </span>
        {onClear && (
          <button
            onClick={onClear}
            className="rounded px-2 py-1 text-xs text-gray-400 hover:bg-gray-200 hover:text-gray-600 transition-colors"
          >
            清空历史
          </button>
        )}
      </div>

      {/* 历史列表 */}
      <div className="flex-1 overflow-y-auto px-2">
        {history.map((item) => (
          <div
            key={item.id}
            className="group mb-1 rounded-lg border border-transparent px-3 py-2.5 hover:bg-white hover:border-gray-100 transition-colors"
          >
            {/* 问题文本 */}
            <div className="flex items-start gap-2">
              <p className="flex-1 truncate text-sm text-gray-700">
                {item.question}
              </p>
              {/* 收藏按钮 */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleStar(item.id);
                }}
                className="shrink-0 rounded p-0.5 text-gray-300 hover:text-yellow-400 transition-colors"
                title={item.is_starred ? '取消收藏' : '收藏'}
              >
                {item.is_starred ? (
                  <svg
                    className="h-4 w-4 text-yellow-400"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                  >
                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                  </svg>
                ) : (
                  <svg
                    className="h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
                    />
                  </svg>
                )}
              </button>
            </div>

            {/* SQL 摘要 */}
            <p className="mt-1 truncate font-mono text-xs text-gray-400">
              {item.sql.length > 50 ? item.sql.slice(0, 50) + '...' : item.sql}
            </p>

            {/* 底部：时间 + 复用按钮 */}
            <div className="mt-2 flex items-center justify-between">
              <span className="text-xs text-gray-300">
                {formatTime(item.created_at)}
              </span>
              <button
                onClick={() => onReuse(item.question)}
                className="rounded px-2 py-0.5 text-xs text-primary-600 opacity-0 group-hover:opacity-100 hover:bg-primary-50 transition-all"
              >
                一键复用
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
