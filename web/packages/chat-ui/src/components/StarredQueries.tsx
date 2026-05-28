import type { StarredQuery } from '@/types/api';

interface StarredQueriesProps {
  /** 收藏查询列表 */
  queries: StarredQuery[];
  /** 一键复用查询 */
  onReuse: (question: string) => void;
  /** 取消收藏 */
  onUnstar: (id: string) => void;
}

/**
 * 收藏查询组件
 * 展示用户收藏的查询列表，支持复用和取消收藏
 */
export default function StarredQueries({
  queries,
  onReuse,
  onUnstar,
}: StarredQueriesProps) {
  if (queries.length === 0) {
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
            d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z"
          />
        </svg>
        <p className="text-sm text-gray-400">暂无收藏查询</p>
      </div>
    );
  }

  /** 格式化时间显示 */
  const formatTime = (isoString: string): string => {
    const date = new Date(isoString);
    return date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="flex h-full flex-col">
      {/* 列表头 */}
      <div className="px-3 py-2">
        <span className="text-xs font-medium text-gray-400">
          共 {queries.length} 条收藏
        </span>
      </div>

      {/* 收藏列表 */}
      <div className="flex-1 overflow-y-auto px-2">
        {queries.map((query) => (
          <div
            key={query.id}
            className="group mb-1 rounded-lg border border-transparent px-3 py-2.5 hover:bg-white hover:border-gray-100 transition-colors"
          >
            {/* 问题文本 */}
            <div className="flex items-start gap-2">
              <svg
                className="mt-0.5 h-3.5 w-3.5 shrink-0 text-yellow-400"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
              </svg>
              <p className="flex-1 truncate text-sm text-gray-700">
                {query.question}
              </p>
            </div>

            {/* SQL 摘要 */}
            <p className="mt-1 ml-5.5 truncate font-mono text-xs text-gray-400">
              {query.sql.length > 50 ? query.sql.slice(0, 50) + '...' : query.sql}
            </p>

            {/* 底部：时间 + 操作按钮 */}
            <div className="mt-2 ml-5.5 flex items-center justify-between">
              <span className="text-xs text-gray-300">
                收藏于 {formatTime(query.starred_at)}
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => onReuse(query.question)}
                  className="rounded px-2 py-0.5 text-xs text-primary-600 opacity-0 group-hover:opacity-100 hover:bg-primary-50 transition-all"
                >
                  复用
                </button>
                <button
                  onClick={() => onUnstar(query.id)}
                  className="rounded px-2 py-0.5 text-xs text-gray-400 opacity-0 group-hover:opacity-100 hover:bg-gray-100 hover:text-gray-600 transition-all"
                >
                  取消收藏
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
