import { apiClient } from './client';

export interface User {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  tenant_id: string;
  created_at: string;
}

/** 用户管理 API */
export const userApi = {
  /** 获取用户列表 */
  list: () =>
    apiClient
      .get<{ data: User[] }>('/api/v1/auth/users')
      .then((res) => res.data.data),

  /** 获取用户详情 */
  get: (id: string) =>
    apiClient
      .get<{ data: User }>(`/api/v1/auth/users/${id}`)
      .then((res) => res.data.data),

  /** 更新用户 */
  update: (id: string, data: Partial<User>) =>
    apiClient
      .patch<{ data: User }>(`/api/v1/auth/users/${id}`, data)
      .then((res) => res.data.data),
};
