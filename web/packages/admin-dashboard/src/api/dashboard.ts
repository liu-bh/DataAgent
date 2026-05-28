import { apiClient } from './client';
import type { MetricOverview, TrendDataPoint, TopMetricItem, QueryDistribution } from '@/types/dashboard';

const BASE_URL = '/api/v1/admin/dashboard';

/** 大盘 API */
export const dashboardApi = {
  /** 获取大盘概览指标 */
  overview: (): Promise<MetricOverview> =>
    apiClient
      .get<{ data: MetricOverview }>(`${BASE_URL}/overview`)
      .then((res) => res.data.data),

  /** 获取趋势数据（最近 N 天） */
  trend: (days: number = 30): Promise<TrendDataPoint[]> =>
    apiClient
      .get<{ data: TrendDataPoint[] }>(`${BASE_URL}/trend`, { params: { days } })
      .then((res) => res.data.data),

  /** 获取热门指标排行 */
  topMetrics: (limit: number = 10): Promise<TopMetricItem[]> =>
    apiClient
      .get<{ data: TopMetricItem[] }>(`${BASE_URL}/top-metrics`, { params: { limit } })
      .then((res) => res.data.data),

  /** 获取查询类型分布 */
  distribution: (): Promise<QueryDistribution[]> =>
    apiClient
      .get<{ data: QueryDistribution[] }>(`${BASE_URL}/distribution`)
      .then((res) => res.data.data),
};
