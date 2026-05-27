import { apiClient } from './client';
import type {
  DataSource,
  CreateDataSourceRequest,
  UpdateDataSourceRequest,
  DataSourceHealth,
  SourceTable,
  PaginatedResponse,
} from '@/types/semantic';

const BASE_URL = '/api/v1/data-sources';

/** 数据源 API */
export const dataSourceApi = {
  /** 获取数据源列表 */
  list: (page = 1, pageSize = 20) =>
    apiClient
      .get<PaginatedResponse<DataSource>>(BASE_URL, {
        params: { page, page_size: pageSize },
      })
      .then((res) => res.data),

  /** 获取数据源详情 */
  get: (id: string) =>
    apiClient
      .get<{ data: DataSource }>(`${BASE_URL}/${id}`)
      .then((res) => res.data.data),

  /** 注册数据源 */
  create: (data: CreateDataSourceRequest) =>
    apiClient
      .post<{ data: DataSource }>(BASE_URL, data)
      .then((res) => res.data.data),

  /** 更新数据源 */
  update: (id: string, data: UpdateDataSourceRequest) =>
    apiClient
      .put<{ data: DataSource }>(`${BASE_URL}/${id}`, data)
      .then((res) => res.data.data),

  /** 删除数据源 */
  delete: (id: string) =>
    apiClient.delete(`${BASE_URL}/${id}`).then((res) => res.data),

  /** 触发元数据同步 */
  sync: (id: string) =>
    apiClient
      .post<{ data: { task_id: string; message: string } }>(`${BASE_URL}/${id}/sync`)
      .then((res) => res.data.data),

  /** 获取数据源健康状态 */
  health: (id: string) =>
    apiClient
      .get<{ data: DataSourceHealth }>(`${BASE_URL}/${id}/health`)
      .then((res) => res.data.data),

  /** 获取已同步的表列表 */
  tables: (id: string) =>
    apiClient
      .get<{ data: SourceTable[] }>(`${BASE_URL}/${id}/tables`)
      .then((res) => res.data.data),
};
