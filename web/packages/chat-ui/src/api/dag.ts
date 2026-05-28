import { apiClient } from './client';
import type {
  DAGExecuteRequest,
  DAGExecuteResponse,
  DAGExecutionStatus,
} from '@/types/dag';

// ==================== DAG 执行 ====================

/**
 * 发起 DAG 执行
 * @param params - 执行参数（问题、方言、租户等）
 * @returns DAG 执行初始响应
 */
export async function executeDAG(
  params: DAGExecuteRequest,
): Promise<DAGExecuteResponse> {
  const { data } = await apiClient.post<DAGExecuteResponse>(
    '/api/v1/dag/execute',
    params,
  );
  return data;
}

/**
 * 查询 DAG 执行状态（用于轮询）
 * @param dagId - DAG 实例 ID
 * @returns DAG 执行状态（含各节点详情）
 */
export async function getDAGStatus(
  dagId: string,
): Promise<DAGExecutionStatus> {
  const { data } = await apiClient.get<DAGExecutionStatus>(
    `/api/v1/dag/${dagId}/status`,
  );
  return data;
}

/**
 * 获取 DAG 执行历史记录
 * @param limit - 返回条数上限，默认 20
 * @returns DAG 执行状态列表
 */
export async function getDAGHistory(
  limit: number = 20,
): Promise<DAGExecutionStatus[]> {
  const { data } = await apiClient.get<DAGExecutionStatus[]>(
    '/api/v1/dag/history',
    { params: { limit } },
  );
  return data;
}
