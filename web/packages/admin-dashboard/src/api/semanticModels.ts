import { apiClient } from './client';
import type {
  SemanticModel,
  CreateSemanticModelRequest,
  UpdateSemanticModelRequest,
  PaginatedResponse,
} from '@/types/semantic';

const BASE_URL = '/api/v1/semantic-models';

/** 语义模型 API */
export const semanticModelApi = {
  /** 获取语义模型列表 */
  list: (page = 1, pageSize = 20) =>
    apiClient
      .get<PaginatedResponse<SemanticModel>>(BASE_URL, {
        params: { page, page_size: pageSize },
      })
      .then((res) => res.data),

  /** 获取语义模型详情 */
  get: (id: string) =>
    apiClient
      .get<{ data: SemanticModel }>(`${BASE_URL}/${id}`)
      .then((res) => res.data.data),

  /** 创建语义模型 */
  create: (data: CreateSemanticModelRequest) =>
    apiClient
      .post<{ data: SemanticModel }>(BASE_URL, data)
      .then((res) => res.data.data),

  /** 更新语义模型 */
  update: (id: string, data: UpdateSemanticModelRequest) =>
    apiClient
      .put<{ data: SemanticModel }>(`${BASE_URL}/${id}`, data)
      .then((res) => res.data.data),

  /** 删除语义模型 */
  delete: (id: string) =>
    apiClient.delete(`${BASE_URL}/${id}`).then((res) => res.data),
};
