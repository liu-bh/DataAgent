// ==================== 通用 ====================

/** 统一错误响应格式 */
export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    detail?: string;
  };
  trace_id?: string;
}

/** 游标分页结果（大结果集） */
export interface CursorPageResult<T> {
  data: T[];
  cursor: string | null;
  total_rows: number;
  has_more: boolean;
}

// ==================== 认证 ====================

export interface User {
  id: string;
  username: string;
  display_name: string;
  role: 'admin' | 'analyst' | 'viewer';
  tenant_id: string;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  data: {
    access_token: string;
    refresh_token: string;
    token_type: string;
    expires_in: number;
  };
}

// ==================== 会话 ====================

export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  is_archived: boolean;
}

export interface CreateSessionRequest {
  title?: string;
}

export interface UpdateSessionRequest {
  title?: string;
  is_archived?: boolean;
}

// ==================== 聊天消息 ====================

export interface ChartSpec {
  chartType: 'bar' | 'line' | 'pie' | 'table' | 'scatter';
  xAxis?: string;
  yAxis?: string;
  series?: unknown[];
  [key: string]: unknown;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  /** 生成的 SQL */
  sql?: string;
  /** SQL 方言 */
  sql_dialect?: string;
  /** SQL 自然语言解释 */
  sql_explanation?: string;
  /** 图表配置 */
  chart_spec?: ChartSpec;
  /** 数据新鲜度提示 */
  freshness_note?: string;
  /** 数据截止时间 ISO 8601 */
  data_cutoff?: string;
  /** 查询结果总行数 */
  total_rows?: number;
  /** 是否有更多数据 */
  has_more?: boolean;
  /** 游标分页 token */
  cursor?: string;
  /** 查询结果数据（前 N 行） */
  data?: Record<string, unknown>[];
  /** SQL 解析错误信息 */
  sql_error?: string;
  /** 用户编辑后的 SQL（对比原 SQL 使用） */
  edited_sql?: string;
  created_at: string;
}

/** NL2SQL 查询处理状态 */
export type QueryStatusType =
  | 'idle'
  | 'analyzing_intent'
  | 'generating_sql'
  | 'executing'
  | 'done'
  | 'error';

export interface SendMessageRequest {
  session_id: string;
  content: string;
}

export interface ChatMessageResponse {
  data: ChatMessage;
  trace_id?: string;
}

export interface ExecuteSqlRequest {
  session_id: string;
  original_sql: string;
  edited_sql: string;
  datasource_id?: string;
}

// ==================== SSE 事件类型 ====================

export type SSEEventType =
  | 'status'
  | 'message'
  | 'sql'
  | 'chart'
  | 'done'
  | 'error';

export interface SSEStatusEvent {
  type: 'thinking' | 'executing' | 'generating';
}

export interface SSEMessageEvent {
  type: 'text';
  content: string;
}

export interface SSESqlEvent {
  type: 'sql';
  sql: string;
  dialect: string;
}

export interface SSEChartEvent {
  type: 'chart';
  spec: ChartSpec;
}

export interface SSEDoneEvent {
  type: 'done';
  message_id: string;
}

export interface SSEErrorEvent {
  type: 'error';
  code: string;
  message: string;
}
