import { apiClient } from './client';

export interface Session {
  id: string;
  title: string;
  message_count: number;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

/** 会话管理 API */
export const sessionApi = {
  /** 获取会话列表 */
  list: (limit = 50) =>
    apiClient
      .get<{ data: Session[] }>('/api/v1/sessions', { params: { limit } })
      .then((res) => res.data.data),

  /** 获取会话详情 */
  get: (id: string) =>
    apiClient
      .get<{ data: Session }>(`/api/v1/sessions/${id}`)
      .then((res) => res.data.data),

  /** 删除会话 */
  delete: (id: string) =>
    apiClient.delete(`/api/v1/sessions/${id}`).then((res) => res.data),

  /** 更新会话 */
  update: (id: string, data: Partial<Session>) =>
    apiClient
      .patch<{ data: Session }>(`/api/v1/sessions/${id}`, data)
      .then((res) => res.data.data),
};
