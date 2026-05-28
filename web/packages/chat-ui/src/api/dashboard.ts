import { apiClient } from './client';
import type {
  DashboardLayout,
  ChartRecommendRequest,
  ChartRecommendResponse,
} from '../types/dashboard';

/** 创建 Dashboard */
export async function createDashboard(data: {
  title: string;
  description?: string;
  chart_specs?: unknown[];
}): Promise<DashboardLayout> {
  const response = await apiClient.post<DashboardLayout>(
    '/api/v1/dashboard/create',
    data,
  );
  return response.data;
}

/** 获取 Dashboard 列表 */
export async function listDashboards(): Promise<DashboardLayout[]> {
  const response = await apiClient.get<DashboardLayout[]>(
    '/api/v1/dashboard/list',
  );
  return response.data;
}

/** 获取单个 Dashboard */
export async function getDashboard(id: string): Promise<DashboardLayout> {
  const response = await apiClient.get<DashboardLayout>(
    `/api/v1/dashboard/${id}`,
  );
  return response.data;
}

/** 删除 Dashboard */
export async function deleteDashboard(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/dashboard/${id}`);
}

/** 图表类型推荐 */
export async function recommendChart(
  data: ChartRecommendRequest,
): Promise<ChartRecommendResponse> {
  const response = await apiClient.post<ChartRecommendResponse>(
    '/api/v1/chart/recommend',
    data,
  );
  return response.data;
}
