// ==================== RCA（根因分析）类型定义 ====================

/** 异常检测结果 */
export interface AnomalyResult {
  metric_name: string;
  current_value: number;
  baseline_value: number;
  change_percent: number;
  is_anomaly: boolean;
  anomaly_type: 'drop' | 'spike' | 'trend_change' | 'none';
  confidence: number;
  direction: 'up' | 'down' | 'neutral';
}

/** 维度值详情 */
export interface DimensionValue {
  value: string;
  current: number;
  baseline: number;
  change: number;
  change_percent: number;
  contribution: number;
  contribution_percent: number;
}

/** 维度下钻结果 */
export interface DrillDownResult {
  dimension_name: string;
  values: DimensionValue[];
  top_contributors: DimensionValue[];
}

/** 归因分析结果 */
export interface AttributionResult {
  total_change: number;
  total_change_percent: number;
  dimensions: Array<{
    dimension: string;
    contribution: number;
    contribution_percent: number;
  }>;
  key_drivers: string[];
}

/** RCA 完整分析报告 */
export interface RCAReport {
  analysis_id: string;
  question: string;
  anomaly: AnomalyResult;
  drill_downs: DrillDownResult[];
  attribution: AttributionResult;
  summary: string;
  confidence: number;
  execution_time_ms: number;
}

/** RCA 分析请求 */
export interface RCAAnalyzeRequest {
  question: string;
  metric_name: string;
  current_data: Record<string, unknown>;
  baseline_data: Record<string, unknown>;
  dimensions?: Array<Record<string, unknown>>;
}

/** RCA 分析响应 */
export interface RCAAnalyzeResponse {
  analysis_id: string;
  report: RCAReport;
  execution_time_ms: number;
}
