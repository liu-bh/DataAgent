import { useMemo } from 'react';
import type {
  DAGExecutionStatus,
  DAGNodeStatus,
  TaskType,
} from '@/types/dag';

interface DAGProgressProps {
  /** DAG 执行状态 */
  dag: DAGExecutionStatus;
  /** 最大高度（默认 auto） */
  maxHeight?: string;
}

// ==================== 常量映射 ====================

/** 节点 ID 到中文标签的映射 */
const NODE_LABELS: Record<string, string> = {
  intent_route: '意图路由',
  intent_parse: '意图解析',
  schema_link: 'Schema Linking',
  prompt_build: 'Prompt 组装',
  sql_generate: 'SQL 生成',
  sql_validate: 'SQL 验证',
  sql_correct: 'SQL 纠错',
  sql_explain: 'SQL 解释',
};

/** 任务类型到颜色/图标配置的映射 */
const TASK_TYPE_CONFIG: Record<
  TaskType,
  { color: string; bgColor: string; label: string }
> = {
  sql: {
    color: 'text-blue-500',
    bgColor: 'bg-blue-50',
    label: 'SQL',
  },
  llm: {
    color: 'text-purple-500',
    bgColor: 'bg-purple-50',
    label: 'LLM',
  },
  python: {
    color: 'text-green-500',
    bgColor: 'bg-green-50',
    label: 'PY',
  },
  search: {
    color: 'text-amber-500',
    bgColor: 'bg-amber-50',
    label: '搜索',
  },
  action: {
    color: 'text-cyan-500',
    bgColor: 'bg-cyan-50',
    label: 'ACT',
  },
};

/** 状态到样式配置的映射 */
const STATUS_STYLES: Record<
  TaskStatus,
  { dotColor: string; bgColor: string; borderColor: string }
> = {
  pending: {
    dotColor: 'bg-gray-300',
    bgColor: 'bg-gray-50',
    borderColor: 'border-gray-200',
  },
  running: {
    dotColor: 'bg-blue-500',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
  },
  completed: {
    dotColor: 'bg-green-500',
    bgColor: 'bg-green-50',
    borderColor: 'border-green-200',
  },
  failed: {
    dotColor: 'bg-red-500',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
  },
  skipped: {
    dotColor: 'bg-gray-300',
    bgColor: 'bg-gray-50',
    borderColor: 'border-gray-200',
  },
  cancelled: {
    dotColor: 'bg-gray-400',
    bgColor: 'bg-gray-50',
    borderColor: 'border-gray-200',
  },
};

// ==================== 子组件 ====================

/** 任务类型图标 */
function TaskTypeIcon({ type }: { type: TaskType }) {
  const config = TASK_TYPE_CONFIG[type] ?? TASK_TYPE_CONFIG.llm;

  // 不同类型使用不同 SVG 图标
  const iconMap: Record<TaskType, JSX.Element> = {
    sql: (
      <svg
        className={`h-4 w-4 ${config.color}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M4 7v10c0 2 1 3 3 3h10c2 0 3-1 3-3V7c0-2-1-3-3-3H7C5 4 4 5 4 7z"
        />
        <path
          strokeLinecap="round"
          d="M9 9h6M9 13h4"
        />
      </svg>
    ),
    llm: (
      <svg
        className={`h-4 w-4 ${config.color}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
        />
      </svg>
    ),
    python: (
      <svg
        className={`h-4 w-4 ${config.color}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
        />
      </svg>
    ),
    search: (
      <svg
        className={`h-4 w-4 ${config.color}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>
    ),
    action: (
      <svg
        className={`h-4 w-4 ${config.color}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M13 10V3L4 14h7v7l9-11h-7z"
        />
      </svg>
    ),
  };

  return (
    <div
      className={`flex h-7 w-7 items-center justify-center rounded-md ${config.bgColor}`}
    >
      {iconMap[type]}
    </div>
  );
}

/** 状态图标 */
function StatusIcon({ status }: { status: TaskStatus }) {
  switch (status) {
    case 'pending':
    case 'skipped':
      return (
        <div className="h-2.5 w-2.5 rounded-full bg-gray-300" />
      );

    case 'running':
      return (
        <div className="relative flex items-center justify-center">
          <div className="absolute h-5 w-5 animate-ping rounded-full bg-blue-400 opacity-20" />
          <svg
            className="relative h-5 w-5 animate-spin text-blue-500"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        </div>
      );

    case 'completed':
      return (
        <svg
          className="h-5 w-5 text-green-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M5 13l4 4L19 7"
          />
        </svg>
      );

    case 'failed':
      return (
        <svg
          className="h-5 w-5 text-red-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      );

    case 'cancelled':
      return (
        <svg
          className="h-5 w-5 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
          />
        </svg>
      );
  }
}

/** 单个 DAG 节点卡片 */
function DAGNodeCard({ node }: { node: DAGNodeStatus }) {
  const styles = STATUS_STYLES[node.status];
  const taskConfig = TASK_TYPE_CONFIG[node.task_type] ?? TASK_TYPE_CONFIG.llm;
  const label = NODE_LABELS[node.node_id] ?? node.label;

  const isFailed = node.status === 'failed';

  return (
    <div
      className={`relative flex items-center gap-2.5 rounded-lg border px-3 py-2 transition-all duration-300 ${styles.bgColor} ${styles.borderColor} ${
        isFailed ? 'ring-1 ring-red-300' : ''
      }`}
    >
      {/* 左侧：任务类型图标 */}
      <TaskTypeIcon type={node.task_type} />

      {/* 中间：任务标签 + 错误信息 */}
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="text-xs font-medium text-gray-700 truncate">
          {label}
        </span>
        {isFailed && node.error && (
          <span className="text-[10px] text-red-500 truncate" title={node.error}>
            {node.error}
          </span>
        )}
      </div>

      {/* 右侧：状态图标 + 耗时 */}
      <div className="flex items-center gap-2 shrink-0 ml-auto">
        {/* 执行耗时（仅 completed 或 failed 时显示） */}
        {node.execution_time_ms !== undefined &&
          (node.status === 'completed' || node.status === 'failed') && (
            <span className="text-[10px] text-gray-400 tabular-nums">
              {node.execution_time_ms < 1000
                ? `${node.execution_time_ms}ms`
                : `${(node.execution_time_ms / 1000).toFixed(1)}s`}
            </span>
          )}
        <StatusIcon status={node.status} />
      </div>
    </div>
  );
}

// ==================== 主组件 ====================

export default function DAGProgress({ dag, maxHeight }: DAGProgressProps) {
  /** 按拓扑层级分组节点 */
  const levels = useMemo(() => {
    const levelMap = new Map<number, DAGNodeStatus[]>();

    for (const node of dag.nodes) {
      const existing = levelMap.get(node.level) ?? [];
      existing.push(node);
      levelMap.set(node.level, existing);
    }

    // 按 level 排序
    const sortedLevels: DAGNodeStatus[][] = [];
    const sortedKeys = Array.from(levelMap.keys()).sort((a, b) => a - b);
    for (const key of sortedKeys) {
      sortedLevels.push(levelMap.get(key)!);
    }

    return sortedLevels;
  }, [dag.nodes]);

  /** 格式化总耗时 */
  const formattedTotalTime = useMemo(() => {
    const ms = dag.total_time_ms;
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}min`;
  }, [dag.total_time_ms]);

  /** 判断 DAG 是否处于运行中 */
  const isRunning = dag.status === 'running';

  /** 判断 DAG 是否处于失败状态 */
  const isFailed = dag.status === 'failed';

  return (
    <div
      className="animate-fade-in rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
      style={maxHeight ? { maxHeight, overflowY: 'auto' } : undefined}
    >
      {/* 标题栏：DAG 进度标题 + 总耗时 */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isRunning && (
            <svg
              className="h-4 w-4 animate-spin text-primary-500"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          )}
          {isFailed && (
            <svg
              className="h-4 w-4 text-red-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
              />
            </svg>
          )}
          {!isRunning && !isFailed && (
            <svg
              className="h-4 w-4 text-green-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M5 13l4 4L19 7"
              />
            </svg>
          )}
          <span className="text-sm font-medium text-gray-700">
            执行流程
          </span>
          {isRunning && (
            <span className="text-xs text-blue-500">
              (第 {dag.current_level} 层)
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-400 tabular-nums">
            {formattedTotalTime}
          </span>
        </div>
      </div>

      {/* 节点层级列表 */}
      <div className="space-y-0">
        {levels.map((levelNodes, levelIdx) => {
          const isLastLevel = levelIdx === levels.length - 1;
          const isActive = levelNodes.some((n) => n.status === 'running');

          return (
            <div key={`level-${levelIdx}`}>
              {/* 层级内的节点：同一层级水平排列 */}
              <div className="flex flex-wrap items-start gap-2">
                {levelNodes.map((node) => (
                  <div
                    key={node.node_id}
                    className={`transition-all duration-300 ${
                      isActive ? 'animate-fade-in' : ''
                    }`}
                  >
                    <DAGNodeCard node={node} />
                  </div>
                ))}
              </div>

              {/* 层级连接线 */}
              {!isLastLevel && (
                <div className="flex justify-center py-1">
                  <div className="w-px h-3 bg-gray-200" />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 底部整体错误提示 */}
      {isFailed && dag.error && (
        <div className="mt-3 rounded-md bg-red-50 px-3 py-2 border border-red-200">
          <p className="text-xs text-red-600">{dag.error}</p>
        </div>
      )}

      {/* 进度统计摘要 */}
      {!isFailed && (
        <div className="mt-3 flex items-center justify-between border-t border-gray-100 pt-2">
          <div className="flex items-center gap-3 text-[10px] text-gray-400">
            <span>
              {dag.nodes.filter((n) => n.status === 'completed').length} /{' '}
              {dag.nodes.length} 已完成
            </span>
            <span>
              {dag.nodes.filter((n) => n.status === 'running').length} 执行中
            </span>
          </div>
          {isRunning && (
            <div className="h-1.5 w-24 overflow-hidden rounded-full bg-gray-100">
              <div
                className="h-full rounded-full bg-blue-500 transition-all duration-500"
                style={{
                  width: `${
                    (dag.nodes.filter((n) => n.status === 'completed').length /
                      dag.nodes.length) *
                    100
                  }%`,
                }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
