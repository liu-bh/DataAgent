// ==================== DAG 执行进度类型定义 ====================

/** DAG 任务类型 */
export type TaskType = 'sql' | 'python' | 'search' | 'action' | 'llm';

/** DAG 任务状态 */
export type TaskStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'skipped'
  | 'cancelled';

/** DAG 单个节点的执行状态 */
export interface DAGNodeStatus {
  /** 节点 ID */
  node_id: string;
  /** 任务标签 */
  label: string;
  /** 任务类型 */
  task_type: TaskType;
  /** 当前状态 */
  status: TaskStatus;
  /** 执行耗时（毫秒） */
  execution_time_ms?: number;
  /** 错误信息 */
  error?: string;
  /** 拓扑层级（用于布局） */
  level: number;
  /** 依赖的节点 ID 列表 */
  dependencies: string[];
}

/** DAG 整体执行状态 */
export interface DAGExecutionStatus {
  /** DAG 实例 ID */
  dag_id: string;
  /** 整体状态 */
  status: TaskStatus;
  /** 所有节点的状态列表 */
  nodes: DAGNodeStatus[];
  /** 总耗时（毫秒） */
  total_time_ms: number;
  /** 当前执行到第几层 */
  current_level: number;
  /** 整体错误信息 */
  error?: string;
}

/** DAG 执行请求 */
export interface DAGExecuteRequest {
  /** 用户自然语言问题 */
  question: string;
  /** SQL 方言（可选） */
  dialect?: string;
  /** 租户 ID（可选） */
  tenant_id?: string;
  /** 会话 ID（可选） */
  session_id?: string;
}

/** DAG 执行响应（初始返回） */
export interface DAGExecuteResponse {
  /** DAG 实例 ID */
  dag_id: string;
  /** 整体状态 */
  status: TaskStatus;
  /** 各任务执行结果摘要 */
  task_results: Record<
    string,
    { status: TaskStatus; execution_time_ms: number }
  >;
  /** 总耗时（毫秒） */
  total_time_ms: number;
}
