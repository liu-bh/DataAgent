import { apiClient } from './client';
import type {
  Dimension,
  CreateDimensionRequest,
  UpdateDimensionRequest,
  PaginatedResponse,
} from '@/types/semantic';

const BASE_URL = '/api/v1/dimensions';

/** 维度 API */
export const dimensionApi = {
  /** 获取维度列表 */
  list: (params?: { page?: number; page_size?: number; semantic_model_id?: string; search?: string }) =>
    apiClient
      .get<PaginatedResponse<Dimension>>(BASE_URL, { params })
      .then((res) => res.data),

  /** 获取维度详情 */
  get: (id: string) =>
    apiClient
      .get<{ data: Dimension }>(`${BASE_URL}/${id}`)
      .then((res) => res.data.data),

  /** 创建维度 */
  create: (data: CreateDimensionRequest) =>
    apiClient
      .post<{ data: Dimension }>(BASE_URL, data)
      .then((res) => res.data.data),

  /** 更新维度 */
  update: (id: string, data: UpdateDimensionRequest) =>
    apiClient
      .put<{ data: Dimension }>(`${BASE_URL}/${id}`, data)
      .then((res) => res.data.data),

  /** 删除维度 */
  delete: (id: string) =>
    apiClient.delete(`${BASE_URL}/${id}`).then((res) => res.data),
};
