import { apiClient } from './client';
import type {
  Metric,
  CreateMetricRequest,
  UpdateMetricRequest,
  PaginatedResponse,
} from '@/types/semantic';

const BASE_URL = '/api/v1/metrics';

/** 指标 API */
export const metricApi = {
  /** 获取指标列表 */
  list: (params?: { page?: number; page_size?: number; semantic_model_id?: string; search?: string }) =>
    apiClient
      .get<PaginatedResponse<Metric>>(BASE_URL, { params })
      .then((res) => res.data),

  /** 获取指标详情 */
  get: (id: string) =>
    apiClient
      .get<{ data: Metric }>(`${BASE_URL}/${id}`)
      .then((res) => res.data.data),

  /** 创建指标 */
  create: (data: CreateMetricRequest) =>
    apiClient
      .post<{ data: Metric }>(BASE_URL, data)
      .then((res) => res.data.data),

  /** 更新指标（创建新版本） */
  update: (id: string, data: UpdateMetricRequest) =>
    apiClient
      .put<{ data: Metric }>(`${BASE_URL}/${id}`, data)
      .then((res) => res.data.data),

  /** 删除指标 */
  delete: (id: string) =>
    apiClient.delete(`${BASE_URL}/${id}`).then((res) => res.data),

  /** 获取指标关联的维度 */
  dimensions: (id: string) =>
    apiClient
      .get<{ data: string[] }>(`${BASE_URL}/${id}/dimensions`)
      .then((res) => res.data.data),
};
