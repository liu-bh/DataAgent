import { apiClient } from './client';
import type { HistoryResponse, StarredQuery } from '@/types/api';

// ==================== 查询历史 ====================

/**
 * 获取查询历史列表
 * @param params - 查询参数，可选 session_id、page、page_size
 * @returns 分页查询历史结果
 */
export async function fetchQueryHistory(params: {
  session_id?: string;
  page?: number;
  page_size?: number;
}): Promise<HistoryResponse> {
  const { data } = await apiClient.get<HistoryResponse>(
    '/api/v1/query/history',
    { params },
  );
  return data;
}

/**
 * 清空查询历史
 * @param session_id - 可选，指定会话 ID 则只清空该会话的历史
 */
export async function clearHistory(session_id?: string): Promise<void> {
  await apiClient.delete('/api/v1/query/history', {
    params: session_id ? { session_id } : undefined,
  });
}

// ==================== 收藏 ====================

/**
 * 获取收藏查询列表
 * @returns 收藏查询列表
 */
export async function fetchStarredQueries(): Promise<StarredQuery[]> {
  const { data } = await apiClient.get<{ data: StarredQuery[] }>(
    '/api/v1/query/starred',
  );
  return data.data;
}

/**
 * 收藏一条查询
 * @param message_id - 消息 ID
 */
export async function starQuery(message_id: string): Promise<void> {
  await apiClient.post(`/api/v1/query/star/${message_id}`);
}

/**
 * 取消收藏一条查询
 * @param message_id - 消息 ID
 */
export async function unstarQuery(message_id: string): Promise<void> {
  await apiClient.delete(`/api/v1/query/star/${message_id}`);
}
