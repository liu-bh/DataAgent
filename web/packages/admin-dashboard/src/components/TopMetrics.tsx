import type { TopMetricItem } from '@/types/dashboard';

/** 热门指标排行 Props */
interface TopMetricsProps {
  /** 排行数据 */
  metrics: TopMetricItem[];
  /** 最多展示数量 */
  maxItems?: number;
}

/** 前三名排名徽章颜色 */
const RANK_BADGE_COLORS: Record<number, string> = {
  1: 'bg-yellow-400 text-yellow-900',
  2: 'bg-gray-300 text-gray-700',
  3: 'bg-amber-600 text-white',
};

/** 延迟等级颜色 */
function latencyColor(ms: number): string {
  if (ms < 200) return 'text-green-600';
  if (ms < 500) return 'text-yellow-600';
  return 'text-red-600';
}

export default function TopMetrics({ metrics, maxItems = 10 }: TopMetricsProps) {
  const items = metrics.slice(0, maxItems);

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="border-b border-gray-100 px-5 py-4">
        <h3 className="text-base font-semibold text-gray-800">热门指标排行</h3>
        <p className="mt-0.5 text-xs text-gray-400">按查询次数降序排列</p>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-100">
          <thead className="bg-gray-50/60">
            <tr>
              <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                排名
              </th>
              <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                指标名称
              </th>
              <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                查询次数
              </th>
              <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                成功率
              </th>
              <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                平均延迟
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {items.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-5 py-10 text-center text-sm text-gray-400">
                  暂无数据
                </td>
              </tr>
            ) : (
              items.map((item, index) => {
                const rank = index + 1;
                const badgeColor = RANK_BADGE_COLORS[rank];

                return (
                  <tr key={item.metric_name} className="transition-colors hover:bg-gray-50/60">
                    {/* 排名 */}
                    <td className="whitespace-nowrap px-5 py-3">
                      {badgeColor ? (
                        <span className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${badgeColor}`}>
                          {rank}
                        </span>
                      ) : (
                        <span className="text-sm text-gray-500">{rank}</span>
                      )}
                    </td>

                    {/* 指标名称 */}
                    <td className="whitespace-nowrap px-5 py-3 text-sm font-medium text-gray-800">
                      {item.metric_name}
                    </td>

                    {/* 查询次数 */}
                    <td className="whitespace-nowrap px-5 py-3 text-right text-sm text-gray-700">
                      {item.query_count.toLocaleString('zh-CN')}
                    </td>

                    {/* 成功率 */}
                    <td className="whitespace-nowrap px-5 py-3 text-right">
                      <span className={`text-sm font-medium ${
                        item.success_rate >= 90 ? 'text-green-600' :
                        item.success_rate >= 70 ? 'text-yellow-600' :
                        'text-red-600'
                      }`}>
                        {item.success_rate.toFixed(1)}%
                      </span>
                    </td>

                    {/* 平均延迟 */}
                    <td className={`whitespace-nowrap px-5 py-3 text-right text-sm font-medium ${latencyColor(item.avg_latency_ms)}`}>
                      {item.avg_latency_ms}ms
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
