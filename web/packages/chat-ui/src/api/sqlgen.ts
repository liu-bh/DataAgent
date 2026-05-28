import { apiClient } from '@/api/client';
import type {
  ExecuteRequest,
  ExecuteResponse,
  ReExecuteRequest,
  FeedbackRequest,
} from '@/types/api';

/**
 * 端到端执行：接收自然语言问题，直接返回 SQL + 结果
 */
export async function executeQuery(
  params: ExecuteRequest,
): Promise<ExecuteResponse> {
  const { data } = await apiClient.post<ExecuteResponse>(
    '/api/v1/chat/execute',
    params,
  );
  return data;
}

/**
 * 重执行 SQL：使用用户编辑后的 SQL 重新查询
 */
export async function reExecuteSql(
  params: ReExecuteRequest,
): Promise<ExecuteResponse> {
  const { data } = await apiClient.post<ExecuteResponse>(
    '/api/v1/chat/re-execute',
    params,
  );
  return data;
}

/**
 * 提交反馈：记录用户对查询结果的评分和评论
 */
export async function submitFeedback(
  params: FeedbackRequest,
): Promise<{ status: string }> {
  const { data } = await apiClient.post<{ status: string }>(
    '/api/v1/chat/feedback',
    params,
  );
  return data;
}
