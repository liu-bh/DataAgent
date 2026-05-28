import { apiClient } from './client';
import type {
  SandboxExecuteRequest,
  SandboxExecuteResponse,
  SandboxResult,
  SandboxInfo,
} from '@/types/sandbox';

/**
 * 执行 Python 代码（沙箱环境）
 * @param params - 执行参数（代码 + 可选配置）
 * @returns 沙箱执行结果
 */
export async function executePythonCode(
  params: SandboxExecuteRequest,
): Promise<SandboxResult> {
  const { data } = await apiClient.post<SandboxExecuteResponse>(
    '/api/v1/sandbox/execute',
    params,
  );
  return data.result;
}

/**
 * 获取沙箱运行信息
 * @returns 沙箱环境信息（Python 版本、已安装包、并发数等）
 */
export async function getSandboxInfo(): Promise<SandboxInfo> {
  const { data } = await apiClient.get<SandboxInfo>('/api/v1/sandbox/info');
  return data;
}

/**
 * 沙箱健康检查
 * @returns 沙箱是否可用
 */
export async function checkSandboxHealth(): Promise<boolean> {
  const { data } = await apiClient.get<{ available: boolean }>(
    '/api/v1/sandbox/health',
  );
  return data.available;
}
