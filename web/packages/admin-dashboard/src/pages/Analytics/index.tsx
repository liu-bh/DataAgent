import { useEffect, useState, useCallback, useMemo } from 'react';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts/core';
import { PieChart, BarChart, LineChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { dashboardApi } from '@/api/dashboard';
import type { TrendDataPoint, TopMetricItem, QueryDistribution } from '@/types/dashboard';

echarts.use([
  PieChart,
  BarChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  CanvasRenderer,
]);

/** 查询类型分布中文映射 */
const TYPE_LABELS: Record<string, string> = {
  sql_query: 'SQL 查询',
  chitchat: '闲聊',
  out_of_scope: '超出范围',
};

const TYPE_COLORS: Record<string, string> = {
  sql_query: '#3B82F6',
  chitchat: '#F59E0B',
  out_of_scope: '#EF4444',
};

export default function AnalyticsPage() {
  const [trendData, setTrendData] = useState<TrendDataPoint[]>([]);
  const [topMetrics, setTopMetrics] = useState<TopMetricItem[]>([]);
  const [distribution, setDistribution] = useState<QueryDistribution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /** 加载分析数据 */
  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [trendRes, topMetricsRes, distRes] = await Promise.all([
        dashboardApi.trend(30),
        dashboardApi.topMetrics(10),
        dashboardApi.distribution(),
      ]);
      setTrendData(trendRes);
      setTopMetrics(topMetricsRes);
      setDistribution(distRes);
    } catch (err) {
      console.error('加载分析数据失败:', err);
      setError('加载数据失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  /** 汇总统计数据 */
  const summary = useMemo(() => {
    const totalQueries = trendData.reduce((sum, d) => sum + d.queries, 0);
    const avgAccuracy = trendData.length > 0
      ? trendData.reduce((sum, d) => sum + d.accuracy, 0) / trendData.length
      : 0;
    const totalErrors = trendData.reduce((sum, d) => sum + d.errors, 0);
    const avgDailyQueries = trendData.length > 0 ? Math.round(totalQueries / trendData.length) : 0;
    return { totalQueries, avgAccuracy, totalErrors, avgDailyQueries };
  }, [trendData]);

  /** 查询类型分布饼图配置 */
  const pieOption = useMemo(() => ({
    tooltip: {
      trigger: 'item' as const,
      backgroundColor: 'rgba(255, 255, 255, 0.96)',
      borderColor: '#E5E7EB',
      borderWidth: 1,
      textStyle: { color: '#374151', fontSize: 13 },
    },
    legend: {
      orient: 'horizontal' as const,
      bottom: 0,
      textStyle: { color: '#6B7280' },
    },
    color: distribution.map((d) => TYPE_COLORS[d.type] ?? '#9CA3AF'),
    series: [{
      type: 'pie',
      radius: ['40%', '65%'],
      center: ['50%', '45%'],
      label: {
        formatter: '{b}: {d}%',
        color: '#6B7280',
        fontSize: 12,
      },
      data: distribution.map((d) => ({
        name: TYPE_LABELS[d.type] ?? d.type,
        value: d.count,
      })),
    }],
  }), [distribution]);

  /** 用户查询排名柱状图配置 */
  const barOption = useMemo(() => ({
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: 'rgba(255, 255, 255, 0.96)',
      borderColor: '#E5E7EB',
      borderWidth: 1,
      textStyle: { color: '#374151', fontSize: 13 },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '8%',
      containLabel: true,
    },
    xAxis: {
      type: 'value' as const,
      axisLabel: { color: '#9CA3AF' },
      splitLine: { lineStyle: { color: '#F3F4F6' } },
    },
    yAxis: {
      type: 'category' as const,
      data: [...topMetrics].reverse().map((m) => m.metric_name),
      axisLabel: {
        color: '#6B7280',
        fontSize: 12,
        width: 120,
        overflow: 'truncate',
      },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#E5E7EB' } },
    },
    series: [{
      type: 'bar',
      data: [...topMetrics].reverse().map((m) => m.query_count),
      barWidth: 20,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#93C5FD' },
          { offset: 1, color: '#3B82F6' },
        ]),
        borderRadius: [0, 4, 4, 0],
      },
    }],
  }), [topMetrics]);

  /** DAU 趋势折线图配置 */
  const dauOption = useMemo(() => {
    // 用 queries 的日变化近似 DAU 趋势（真实场景下应使用独立的 DAU 数据）
    return {
      tooltip: {
        trigger: 'axis' as const,
        backgroundColor: 'rgba(255, 255, 255, 0.96)',
        borderColor: '#E5E7EB',
        borderWidth: 1,
        textStyle: { color: '#374151', fontSize: 13 },
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '12%',
        top: '10%',
        containLabel: true,
      },
      dataZoom: [
        { type: 'inside' as const, start: 0, end: 100 },
        { start: 0, end: 100, height: 20, bottom: 4 },
      ],
      xAxis: {
        type: 'category' as const,
        data: trendData.map((d) => d.date),
        axisLabel: {
          color: '#9CA3AF',
          formatter: (v: string) => v.slice(5),
        },
        axisLine: { lineStyle: { color: '#E5E7EB' } },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value' as const,
        axisLabel: { color: '#9CA3AF' },
        splitLine: { lineStyle: { color: '#F3F4F6' } },
      },
      series: [{
        type: 'line',
        data: trendData.map((d) => d.queries),
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { width: 2, color: '#8B5CF6' },
        itemStyle: { color: '#8B5CF6' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(139, 92, 246, 0.15)' },
            { offset: 1, color: 'rgba(139, 92, 246, 0.01)' },
          ]),
        },
      }],
    };
  }, [trendData]);

  /** 加载中状态 */
  if (loading) {
    return (
      <div className="space-y-6">
        {/* 统计面板骨架屏 */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="animate-pulse rounded-xl border border-gray-200 bg-white p-5">
              <div className="h-3 w-16 rounded bg-gray-200" />
              <div className="mt-2 h-7 w-24 rounded bg-gray-200" />
            </div>
          ))}
        </div>
        <div className="animate-pulse rounded-xl border border-gray-200 bg-white p-5">
          <div className="h-[300px] rounded bg-gray-100" />
        </div>
      </div>
    );
  }

  /** 错误状态 */
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-sm text-gray-500">{error}</p>
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
      {/* 统计面板 */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-gray-500">30 天总查询</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{summary.totalQueries.toLocaleString('zh-CN')}</p>
          <p className="mt-1 text-xs text-gray-400">日均 {summary.avgDailyQueries.toLocaleString('zh-CN')} 次</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-gray-500">平均准确率</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{summary.avgAccuracy.toFixed(1)}%</p>
          <p className="mt-1 text-xs text-gray-400">NL2SQL 生成质量</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-gray-500">总错误数</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{summary.totalErrors.toLocaleString('zh-CN')}</p>
          <p className="mt-1 text-xs text-gray-400">30 天累计</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-gray-500">热门指标数</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{topMetrics.length}</p>
          <p className="mt-1 text-xs text-gray-400">Top 10 排行</p>
        </div>
      </div>

      {/* 查询类型分布 + 用户查询排名 */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h3 className="mb-4 text-base font-semibold text-gray-800">查询类型分布</h3>
          <ReactEChartsCore
            echarts={echarts}
            option={pieOption}
            style={{ height: '320px', width: '100%' }}
            notMerge
          />
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h3 className="mb-4 text-base font-semibold text-gray-800">用户查询排名</h3>
          <ReactEChartsCore
            echarts={echarts}
            option={barOption}
            style={{ height: '320px', width: '100%' }}
            notMerge
          />
        </div>
      </div>

      {/* 每日活跃用户趋势 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <h3 className="mb-4 text-base font-semibold text-gray-800">每日查询趋势</h3>
        <ReactEChartsCore
          echarts={echarts}
          option={dauOption}
          style={{ height: '320px', width: '100%' }}
          notMerge
        />
      </div>
    </div>
  );
}
