import { useEffect, useState, useCallback } from 'react';
import MetricCard from '@/components/MetricCard';
import TrendChart from '@/components/TrendChart';
import TopMetrics from '@/components/TopMetrics';
import QueryDistributionChart from '@/components/QueryDistribution';
import { dashboardApi } from '@/api/dashboard';
import type { MetricOverview, TrendDataPoint, TopMetricItem, QueryDistribution } from '@/types/dashboard';

export default function DashboardPage() {
  const [overview, setOverview] = useState<MetricOverview | null>(null);
  const [trendData, setTrendData] = useState<TrendDataPoint[]>([]);
  const [topMetrics, setTopMetrics] = useState<TopMetricItem[]>([]);
  const [distribution, setDistribution] = useState<QueryDistribution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /** 加载所有大盘数据 */
  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [overviewRes, trendRes, topMetricsRes, distRes] = await Promise.all([
        dashboardApi.overview(),
        dashboardApi.trend(30),
        dashboardApi.topMetrics(10),
        dashboardApi.distribution(),
      ]);
      setOverview(overviewRes);
      setTrendData(trendRes);
      setTopMetrics(topMetricsRes);
      setDistribution(distRes);
    } catch (err) {
      console.error('加载大盘数据失败:', err);
      setError('加载数据失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  /** 加载中状态 */
  if (loading) {
    return (
      <div className="space-y-6">
        {/* 指标卡片骨架屏 */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="animate-pulse rounded-xl border border-gray-200 bg-white p-5">
              <div className="h-4 w-20 rounded bg-gray-200" />
              <div className="mt-3 h-8 w-32 rounded bg-gray-200" />
              <div className="mt-2 h-3 w-16 rounded bg-gray-100" />
            </div>
          ))}
        </div>
        {/* 图表骨架屏 */}
        <div className="animate-pulse rounded-xl border border-gray-200 bg-white p-5">
          <div className="h-4 w-24 rounded bg-gray-200" />
          <div className="mt-4 h-[340px] rounded bg-gray-100" />
        </div>
      </div>
    );
  }

  /** 错误状态 */
  if (error || !overview) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <svg className="mb-4 h-12 w-12 text-gray-300" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
        </svg>
        <p className="text-sm text-gray-500">{error ?? '暂无数据'}</p>
        <button
          onClick={loadAll}
          className="mt-4 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
        >
          重新加载
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 顶部：4 个核心指标卡片 */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="日活用户"
          value={overview.dau}
          unit="人"
          trend={overview.dau_trend}
          icon="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"
        />
        <MetricCard
          title="查询频次"
          value={overview.total_queries}
          unit="次"
          trend={overview.queries_trend}
          icon="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5M9 11.25v1.5M12 9v3.75m3-6v6"
        />
        <MetricCard
          title="NL2SQL 准确率"
          value={overview.avg_accuracy}
          unit="%"
          trend={overview.accuracy_trend}
          icon="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
        />
        <MetricCard
          title="用户满意度"
          value={overview.satisfaction_rate}
          unit="%"
          trend={overview.satisfaction_trend}
          icon="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z"
        />
      </div>

      {/* 中间：趋势图表 */}
      <TrendChart data={trendData} height="380px" />

      {/* 下方：热门指标排行 + 查询类型分布 */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <TopMetrics metrics={topMetrics} maxItems={10} />
        </div>
        <div className="lg:col-span-1">
          <QueryDistributionChart data={distribution} height="380px" />
        </div>
      </div>
    </div>
  );
}
