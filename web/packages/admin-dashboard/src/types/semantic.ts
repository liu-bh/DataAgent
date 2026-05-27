// ==================== 分页 ====================

/** 标准分页响应 */
export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

// ==================== 数据源 ====================

/** 数据源类型 */
export type DataSourceType = 'mysql' | 'postgresql' | 'doris' | 'starrocks' | 'clickhouse' | 'api';

/** 数据源状态 */
export type DataSourceStatus = 'active' | 'disabled';

/** 数据新鲜度级别 */
export type FreshnessLevel = 'realtime' | 'hourly' | 'daily' | 'custom';

/** 数据源 */
export interface DataSource {
  id: string;
  tenant_id: string;
  name: string;
  type: DataSourceType;
  host: string;
  port: number;
  database: string;
  username: string;
  password?: string;
  pool_size: number;
  freshness_level: FreshnessLevel;
  freshness_cron?: string;
  status: DataSourceStatus;
  last_health_check?: string;
  created_at: string;
  updated_at: string;
}

/** 注册数据源请求 */
export interface CreateDataSourceRequest {
  name: string;
  type: DataSourceType;
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
  pool_size?: number;
  freshness_level?: FreshnessLevel;
  freshness_cron?: string;
}

/** 更新数据源请求 */
export interface UpdateDataSourceRequest {
  name?: string;
  host?: string;
  port?: number;
  database?: string;
  username?: string;
  password?: string;
  pool_size?: number;
  freshness_level?: FreshnessLevel;
  freshness_cron?: string;
  status?: DataSourceStatus;
}

/** 数据源健康状态 */
export type HealthStatus = 'healthy' | 'degraded' | 'down';

/** 数据源健康检查结果 */
export interface DataSourceHealth {
  id: string;
  datasource_id: string;
  pool_usage: number;
  avg_latency_ms: number;
  status: HealthStatus;
  last_heartbeat: string;
}

// ==================== 已同步表 ====================

/** 列定义 */
export interface ColumnDefinition {
  name: string;
  type: string;
  description?: string;
  is_primary_key: boolean;
}

/** 已同步的源表 */
export interface SourceTable {
  id: string;
  tenant_id: string;
  data_source_id: string;
  schema_name: string;
  table_name: string;
  columns: ColumnDefinition[];
  row_count: number;
  description?: string;
  last_synced_at?: string;
  created_at: string;
}

// ==================== 语义模型 ====================

/** 语义模型 */
export interface SemanticModel {
  id: string;
  tenant_id: string;
  name: string;
  description?: string;
  domain: string;
  data_source_ids: string[];
  metrics_count?: number;
  dimensions_count?: number;
  tables_count?: number;
  created_at: string;
  updated_at: string;
}

/** 创建语义模型请求 */
export interface CreateSemanticModelRequest {
  name: string;
  description?: string;
  domain: string;
  data_source_ids: string[];
}

/** 更新语义模型请求 */
export interface UpdateSemanticModelRequest {
  name?: string;
  description?: string;
  domain?: string;
  data_source_ids?: string[];
}

// ==================== 表关系 ====================

/** JOIN 类型 */
export type JoinType = 'inner' | 'left' | 'right' | 'full';

/** 表关系 */
export interface TableRelationship {
  id: string;
  tenant_id: string;
  semantic_model_id: string;
  left_table_id: string;
  right_table_id: string;
  join_type: JoinType;
  join_condition: string;
  created_at: string;
}

// ==================== 指标 ====================

/** 指标 */
export interface Metric {
  id: string;
  tenant_id: string;
  semantic_model_id: string;
  name: string;
  description?: string;
  calculation: string;
  unit?: string;
  version: number;
  effective_time?: string;
  parent_metric_id?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

/** 创建指标请求 */
export interface CreateMetricRequest {
  semantic_model_id: string;
  name: string;
  description?: string;
  calculation: string;
  unit?: string;
  tags?: string[];
}

/** 更新指标请求 */
export interface UpdateMetricRequest {
  name?: string;
  description?: string;
  calculation?: string;
  unit?: string;
  tags?: string[];
}

// ==================== 维度 ====================

/** 维度层级 */
export interface DimensionHierarchy {
  level: string;
  children: string[];
}

/** 维度 */
export interface Dimension {
  id: string;
  tenant_id: string;
  semantic_model_id: string;
  name: string;
  column_name: string;
  table_id: string;
  synonyms: string[];
  hierarchy?: DimensionHierarchy;
  is_virtual: boolean;
  virtual_expression?: string;
  created_at: string;
  updated_at: string;
}

/** 创建维度请求 */
export interface CreateDimensionRequest {
  semantic_model_id: string;
  name: string;
  column_name: string;
  table_id: string;
  synonyms?: string[];
  hierarchy?: DimensionHierarchy;
  is_virtual?: boolean;
  virtual_expression?: string;
}

/** 更新维度请求 */
export interface UpdateDimensionRequest {
  name?: string;
  column_name?: string;
  table_id?: string;
  synonyms?: string[];
  hierarchy?: DimensionHierarchy;
  is_virtual?: boolean;
  virtual_expression?: string;
}

// ==================== 搜索 ====================

/** 搜索结果项 */
export interface SearchResultItem {
  type: 'metric' | 'dimension' | 'semantic_model';
  id: string;
  name: string;
  description?: string;
  score: number;
}

/** 搜索响应 */
export interface SearchResponse {
  data: SearchResultItem[];
  total: number;
}
