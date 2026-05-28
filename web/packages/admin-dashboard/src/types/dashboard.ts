// ==================== 业务指标大盘 ====================

/** 大盘概览指标 */
export interface MetricOverview {
  /** 日活用户数 */
  dau: number;
  /** DAU 同比增长率 % */
  dau_trend: number;
  /** 总查询次数 */
  total_queries: number;
  /** 查询次数同比增长率 % */
  queries_trend: number;
  /** NL2SQL 准确率 % */
  avg_accuracy: number;
  /** 准确率同比增长率 % */
  accuracy_trend: number;
  /** SQL 编辑率 %（用户手动修改 SQL 的比例） */
  edit_rate: number;
  /** 编辑率同比增长率 % */
  edit_rate_trend: number;
  /** 满意度 % */
  satisfaction_rate: number;
  /** 满意度同比增长率 % */
  satisfaction_trend: number;
}

/** 趋势数据点 */
export interface TrendDataPoint {
  /** 日期（YYYY-MM-DD） */
  date: string;
  /** 查询次数 */
  queries: number;
  /** 准确率 % */
  accuracy: number;
  /** 错误次数 */
  errors: number;
}

/** 热门指标排行项 */
export interface TopMetricItem {
  /** 指标名称 */
  metric_name: string;
  /** 查询次数 */
  query_count: number;
  /** 查询成功率 % */
  success_rate: number;
  /** 平均响应延迟 ms */
  avg_latency_ms: number;
}

/** 查询类型分布 */
export interface QueryDistribution {
  /** 查询类型：sql_query / chitchat / out_of_scope */
  type: string;
  /** 数量 */
  count: number;
  /** 占比 % */
  percentage: number;
}
