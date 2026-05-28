import { create } from 'zustand';
import type { DAGExecutionStatus, DAGExecuteRequest } from '@/types/dag';
import { executeDAG as apiExecuteDAG, getDAGStatus } from '@/api/dag';

/** 轮询间隔（毫秒） */
const POLL_INTERVAL_MS = 1000;

/** 轮询最大次数（防止无限轮询） */
const POLL_MAX_ATTEMPTS = 120;

interface DAGState {
  /** 当前正在执行的 DAG */
  currentDag: DAGExecutionStatus | null;
  /** DAG 执行历史 */
  dagHistory: DAGExecutionStatus[];
  /** 是否正在加载 */
  isLoading: boolean;
  /** 错误信息 */
  error: string | null;
  /** 轮询定时器 ID */
  _pollTimerId: ReturnType<typeof setInterval> | null;
  /** 轮询次数计数 */
  _pollAttempts: number;
  /** 发起 DAG 执行并开始轮询状态 */
  executeDAG: (params: DAGExecuteRequest) => Promise<void>;
  /** 停止轮询 */
  _stopPolling: () => void;
  /** 获取 DAG 历史记录 */
  fetchHistory: (limit?: number) => Promise<void>;
  /** 清空当前 DAG 状态 */
  clearCurrent: () => void;
  /** 重置错误 */
  clearError: () => void;
}

export const useDagStore = create<DAGState>((set, get) => ({
  currentDag: null,
  dagHistory: [],
  isLoading: false,
  error: null,
  _pollTimerId: null,
  _pollAttempts: 0,

  executeDAG: async (params: DAGExecuteRequest) => {
    // 先停止已有的轮询
    get()._stopPolling();

    set({ isLoading: true, error: null, currentDag: null });

    try {
      const response = await apiExecuteDAG(params);

      // 如果立即完成，直接设置结果
      if (response.status === 'completed' || response.status === 'failed') {
        // 构建简化版的 DAGExecutionStatus
        const completedDag: DAGExecutionStatus = {
          dag_id: response.dag_id,
          status: response.status,
          nodes: Object.entries(response.task_results).map(
            ([nodeId, result], idx) => ({
              node_id: nodeId,
              label: nodeId,
              task_type: 'llm',
              status: result.status,
              execution_time_ms: result.execution_time_ms,
              level: idx,
              dependencies: [],
            }),
          ),
          total_time_ms: response.total_time_ms,
          current_level: -1,
        };

        set({
          currentDag: completedDag,
          isLoading: false,
        });
        return;
      }

      // 需要轮询：先设置初始状态
      const initialDag: DAGExecutionStatus = {
        dag_id: response.dag_id,
        status: 'running',
        nodes: Object.entries(response.task_results).map(
          ([nodeId, result], idx) => ({
            node_id: nodeId,
            label: nodeId,
            task_type: 'llm',
            status: result.status,
            execution_time_ms: result.execution_time_ms,
            level: idx,
            dependencies: [],
          }),
        ),
        total_time_ms: response.total_time_ms,
        current_level: 0,
      };

      set({
        currentDag: initialDag,
        isLoading: false,
        _pollAttempts: 0,
      });

      // 开始轮询
      const timerId = setInterval(async () => {
        const { _pollAttempts: attempts } = get();

        // 超过最大轮询次数，停止轮询
        if (attempts >= POLL_MAX_ATTEMPTS) {
          get()._stopPolling();
          set({ error: 'DAG 执行超时，请稍后重试' });
          return;
        }

        set({ _pollAttempts: attempts + 1 });

        try {
          const status = await getDAGStatus(response.dag_id);
          set({ currentDag: status });

          // 终态：停止轮询
          if (status.status === 'completed' || status.status === 'failed') {
            get()._stopPolling();
          }
        } catch {
          // 轮询出错不中断，继续尝试
        }
      }, POLL_INTERVAL_MS);

      set({ _pollTimerId: timerId });
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : 'DAG 执行失败，请稍后重试';
      set({ isLoading: false, error: errorMsg });
    }
  },

  _stopPolling: () => {
    const { _pollTimerId } = get();
    if (_pollTimerId !== null) {
      clearInterval(_pollTimerId);
      set({ _pollTimerId: null });
    }
  },

  fetchHistory: async (limit: number = 20) => {
    try {
      const { getDAGHistory: apiGetHistory } = await import('@/api/dag');
      const history = await apiGetHistory(limit);
      set({ dagHistory: history });
    } catch {
      // 历史加载失败静默处理
    }
  },

  clearCurrent: () => {
    get()._stopPolling();
    set({ currentDag: null, isLoading: false, error: null, _pollAttempts: 0 });
  },

  clearError: () => {
    set({ error: null });
  },
}));
