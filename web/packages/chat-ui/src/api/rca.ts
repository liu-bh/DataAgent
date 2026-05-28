import { apiClient } from './client';
import type {
  RCAAnalyzeRequest,
  RCAAnalyzeResponse,
  RCAReport,
} from '../types/rca';

/** RCA 历史记录条目 */
export interface RCAHistoryItem {
  analysis_id: string;
  question: string;
  metric_name: string;
  anomaly_detected: boolean;
  change_percent: number;
}

/** 发起 RCA 根因分析 */
export async function analyzeRCA(
  data: RCAAnalyzeRequest,
): Promise<RCAAnalyzeResponse> {
  const response = await apiClient.post<RCAAnalyzeResponse>(
    '/api/v1/rca/analyze',
    data,
  );
  return response.data;
}

/** 获取 RCA 分析结果 */
export async function getRCAResult(
  analysisId: string,
): Promise<RCAReport> {
  const response = await apiClient.get<RCAReport>(
    `/api/v1/rca/${analysisId}/result`,
  );
  return response.data;
}

/** 获取 RCA 分析历史记录 */
export async function getRCAHistory(): Promise<RCAHistoryItem[]> {
  const response = await apiClient.get<RCAHistoryItem[]>(
    '/api/v1/rca/history',
  );
  return response.data;
}
