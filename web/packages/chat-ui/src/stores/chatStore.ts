import { create } from 'zustand';
import type {
  ChatMessage,
  SendMessageRequest,
  QueryStatusType,
  ExecuteResponse,
  QueryHistoryItem,
  StarredQuery,
} from '@/types/api';
import { apiClient } from '@/api/client';
import {
  fetchQueryHistory as apiFetchQueryHistory,
  fetchStarredQueries as apiFetchStarredQueries,
  starQuery as apiStarQuery,
  unstarQuery as apiUnstarQuery,
} from '@/api/history';
import { useSSEStream } from '@/hooks/useSSEStream';

interface ChatState {
  /** 当前会话的消息列表 */
  messages: ChatMessage[];
  /** 是否正在等待 AI 响应 */
  isLoading: boolean;
  /** 是否正在通过 SSE 流式接收 */
  isStreaming: boolean;
  /** NL2SQL 查询处理状态 */
  queryStatus: QueryStatusType;
  /** 查询失败时的错误信息 */
  queryError: string;
  /** 查询历史列表 */
  queryHistory: QueryHistoryItem[];
  /** 收藏查询列表 */
  starredQueries: StarredQuery[];
  /** 多轮上下文消息（最近 20 条） */
  contextMessages: ChatMessage[];
  /** 发送消息并获取 AI 回复 */
  sendMessage: (request: SendMessageRequest) => Promise<void>;
  /** 通过 SSE 流式发送消息并接收阶段性响应 */
  sendStreamMessage: (request: SendMessageRequest) => void;
  /** 停止当前 SSE 流 */
  stopStream: () => void;
  /** 清空消息列表 */
  clearMessages: () => void;
  /** 加载历史消息 */
  loadMessages: (sessionId: string) => Promise<void>;
  /** 设置查询状态 */
  setQueryStatus: (status: QueryStatusType, error?: string) => void;
  /** 更新助手消息中的 SQL（用户编辑后） */
  updateAssistantSql: (messageId: string, editedSql: string) => void;
  /** 重试上次查询 */
  retryQuery: () => Promise<void>;
  /** 记录用户编辑的 SQL */
  editSql: (messageId: string, sql: string) => void;
  /** 触发 SQL 重执行 */
  reExecute: (sql: string, sessionId: string, tenantId: string) => Promise<void>;
  /** 提交反馈 */
  submitFeedback: (
    messageId: string,
    rating: 'thumbs_up' | 'thumbs_down',
    comment?: string,
  ) => Promise<void>;
  /** 获取查询历史 */
  fetchHistory: (sessionId?: string) => Promise<void>;
  /** 切换收藏状态 */
  toggleStar: (messageId: string) => Promise<void>;
  /** 获取收藏列表 */
  fetchStarred: () => Promise<void>;
  /** 一键复用收藏查询（将问题填入输入框） */
  reuseQuery: (question: string) => void;
  /** 更新上下文消息（保留最近 20 条） */
  updateContextMessages: () => void;
}

export const useChatStore = create<ChatState>((set, get) => {
  // SSE 流式 hook 实例
  const sse = useSSEStream({
    onStatus: (data) => {
      const status = data.status as string;
      if (status === 'thinking') {
        set({ queryStatus: 'analyzing_intent' as QueryStatusType });
      } else if (status === 'generating') {
        set({ queryStatus: 'generating_sql' as QueryStatusType });
      } else if (status === 'executing') {
        set({ queryStatus: 'executing' as QueryStatusType });
      }
    },
    onSql: (data) => {
      set((state) => {
        const msgs = [...state.messages];
        const lastMsg = msgs[msgs.length - 1];
        if (lastMsg && lastMsg.role === 'assistant') {
          msgs[msgs.length - 1] = {
            ...lastMsg,
            sql: data.sql as string,
            sql_dialect: data.dialect as string,
          };
        } else {
          msgs.push({
            id: `stream-assistant-${msgs.length}`,
            role: 'assistant',
            content: '',
            sql: data.sql as string,
            sql_dialect: data.dialect as string,
            created_at: new Date().toISOString(),
          });
        }
        return { messages: msgs, queryStatus: 'generating_sql' as QueryStatusType };
      });
    },
    onMessage: (data) => {
      set((state) => {
        const msgs = [...state.messages];
        const lastMsg = msgs[msgs.length - 1];
        if (lastMsg && lastMsg.role === 'assistant') {
          msgs[msgs.length - 1] = {
            ...lastMsg,
            content: lastMsg.content + (data.content as string),
          };
        } else {
          msgs.push({
            id: `stream-assistant-${Date.now()}`,
            role: 'assistant',
            content: data.content as string,
            created_at: new Date().toISOString(),
          });
        }
        return { messages: msgs };
      });
    },
    onChart: (data) => {
      set((state) => {
        const msgs = [...state.messages];
        const lastMsg = msgs[msgs.length - 1];
        if (lastMsg && lastMsg.role === 'assistant') {
          msgs[msgs.length - 1] = {
            ...lastMsg,
            chart_spec: data.spec as ChatMessage['chart_spec'],
          };
        }
        return { messages: msgs };
      });
    },
    onDone: () => {
      set({
        isLoading: false,
        isStreaming: false,
        queryStatus: 'done' as QueryStatusType,
      });
    },
    onError: (data) => {
      const errorMsg = (data.message as string) || 'SSE 流处理出错';
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: '抱歉，处理您的请求时出现了错误，请稍后重试。',
        created_at: new Date().toISOString(),
      };
      set((state) => ({
        messages: [...state.messages, errorMessage],
        isLoading: false,
        isStreaming: false,
        queryStatus: 'error' as QueryStatusType,
        queryError: errorMsg,
      }));
    },
  });

  return {
    messages: [],
    isLoading: false,
    isStreaming: false,
    queryStatus: 'idle' as QueryStatusType,
    queryError: '',
    queryHistory: [],
    starredQueries: [],
    contextMessages: [],

    sendStreamMessage: (request) => {
      // 先添加用户消息
      const userMessage: ChatMessage = {
        id: `temp-user-${Date.now()}`,
        role: 'user',
        content: request.content,
        created_at: new Date().toISOString(),
      };

      set((state) => ({
        messages: [...state.messages, userMessage],
        isLoading: true,
        isStreaming: true,
        queryStatus: 'analyzing_intent' as QueryStatusType,
        queryError: '',
      }));

      // 发起 SSE 流式请求
      sse.startStream('/api/v1/chat/stream', {
        session_id: request.session_id,
        content: request.content,
      });
    },

    stopStream: () => {
      sse.stopStream();
      set({ isLoading: false, isStreaming: false });
    },

    sendMessage: async (request) => {
      // 先添加用户消息
      const userMessage: ChatMessage = {
        id: `temp-user-${Date.now()}`,
        role: 'user',
        content: request.content,
        created_at: new Date().toISOString(),
      };

      set((state) => ({
        messages: [...state.messages, userMessage],
        isLoading: true,
        queryStatus: 'analyzing_intent' as QueryStatusType,
        queryError: '',
      }));

      try {
        // 模拟处理阶段（实际由 SSE 或后端状态驱动，这里做阶段切换）
        set({ queryStatus: 'generating_sql' as QueryStatusType });

        const { data } = await apiClient.post<{
          data: ChatMessage;
          trace_id?: string;
        }>('/api/v1/chat/message', request);

        set({ queryStatus: 'executing' as QueryStatusType });

        const assistantMessage: ChatMessage = data.data;

        set((state) => ({
          messages: [...state.messages, assistantMessage],
          isLoading: false,
          queryStatus: 'done' as QueryStatusType,
        }));
      } catch (err) {
        const errorMsg =
          err instanceof Error ? err.message : '请求失败，请稍后重试';

        // 出错时追加错误消息
        const errorMessage: ChatMessage = {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: '抱歉，处理您的请求时出现了错误，请稍后重试。',
          created_at: new Date().toISOString(),
        };
        set((state) => ({
          messages: [...state.messages, errorMessage],
          isLoading: false,
          queryStatus: 'error' as QueryStatusType,
          queryError: errorMsg,
        }));
      }
    },

    clearMessages: () => {
      set({
        messages: [],
        queryStatus: 'idle' as QueryStatusType,
        queryError: '',
      });
    },

    loadMessages: async (sessionId: string) => {
      set({ isLoading: true });
      try {
        const { data } = await apiClient.get<{ data: ChatMessage[] }>(
          `/api/v1/sessions/${sessionId}/messages`,
        );
        set({ messages: data.data, isLoading: false });
      } catch {
        set({ isLoading: false });
      }
    },

    setQueryStatus: (status, error = '') => {
      set({ queryStatus: status, queryError: error });
    },

    updateAssistantSql: (messageId: string, editedSql: string) => {
      set((state) => ({
        messages: state.messages.map((msg) =>
          msg.id === messageId
            ? { ...msg, edited_sql: editedSql }
            : msg,
        ),
      }));
    },

    retryQuery: async () => {
      const { messages } = get();
      // 找到最后一条用户消息进行重试
      const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user');
      if (!lastUserMsg) return;

      // 移除错误消息和对应的助手消息
      const lastUserIdx = messages.lastIndexOf(lastUserMsg);
      set((state) => ({
        messages: state.messages.slice(0, lastUserIdx),
      }));

      // 注意：需要 sessionId 才能重试，这里从路由获取
      // 实际调用由 Chat 页面处理
    },

    editSql: (messageId: string, sql: string) => {
      set((state) => ({
        messages: state.messages.map((msg) =>
          msg.id === messageId
            ? { ...msg, edited_sql: sql }
            : msg,
        ),
      }));
    },

    reExecute: async (sql: string, sessionId: string, tenantId: string) => {
      set({ isLoading: true, queryStatus: 'executing' as QueryStatusType, queryError: '' });
      try {
        const { data } = await apiClient.post<ExecuteResponse>(
          '/api/v1/chat/re-execute',
          { sql, session_id: sessionId, tenant_id: tenantId },
        );

        const reExecMessage: ChatMessage = {
          id: `msg-reexec-${Date.now()}`,
          role: 'assistant',
          content: data.explanation,
          sql,
          sql_explanation: data.explanation,
          total_rows: data.data?.length,
          has_more: false,
          data: data.data,
          created_at: new Date().toISOString(),
        };

        set((state) => ({
          messages: [...state.messages, reExecMessage],
          isLoading: false,
          queryStatus: 'done' as QueryStatusType,
        }));
      } catch (err) {
        const errorMsg =
          err instanceof Error ? err.message : '重执行失败，请稍后重试';
        set({
          isLoading: false,
          queryStatus: 'error' as QueryStatusType,
          queryError: errorMsg,
        });
      }
    },

    submitFeedback: async (
      messageId: string,
      rating: 'thumbs_up' | 'thumbs_down',
      comment?: string,
    ) => {
      try {
        await apiClient.post('/api/v1/chat/feedback', {
          message_id: messageId,
          rating,
          comment,
        });
      } catch {
        // 反馈提交失败静默处理，不影响用户体验
      }
    },

    fetchHistory: async (sessionId?: string) => {
      try {
        const data = await apiFetchQueryHistory({
          session_id: sessionId,
          page: 1,
          page_size: 50,
        });
        set({ queryHistory: data.items });
      } catch {
        // 查询历史加载失败静默处理
      }
    },

    toggleStar: async (messageId: string) => {
      const { queryHistory, starredQueries } = get();
      const isCurrentlyStarred =
        starredQueries.some((q) => q.id === messageId) ||
        queryHistory.some((h) => h.id === messageId && h.is_starred);

      // 乐观更新：立即更新本地状态
      set((state) => ({
        queryHistory: state.queryHistory.map((h) =>
          h.id === messageId ? { ...h, is_starred: !h.is_starred } : h,
        ),
        starredQueries: isCurrentlyStarred
          ? state.starredQueries.filter((q) => q.id !== messageId)
          : state.starredQueries,
      }));

      try {
        if (isCurrentlyStarred) {
          await apiUnstarQuery(messageId);
        } else {
          await apiStarQuery(messageId);
        }
      } catch {
        // 失败时回滚乐观更新
        set((state) => ({
          queryHistory: state.queryHistory.map((h) =>
            h.id === messageId ? { ...h, is_starred: !h.is_starred } : h,
          ),
        }));
      }
    },

    fetchStarred: async () => {
      try {
        const data = await apiFetchStarredQueries();
        set({ starredQueries: data });
      } catch {
        // 收藏列表加载失败静默处理
      }
    },

    reuseQuery: (_question: string) => {
      // 由 Chat 页面组件监听此 action，将问题填入输入框
      // 这里仅作为触发点，实际逻辑由使用方实现
    },

    updateContextMessages: () => {
      const { messages } = get();
      // 保留最近 20 条消息作为多轮上下文（约 10 轮对话）
      const contextSlice = messages.slice(-20);
      set({ contextMessages: contextSlice });
    },
  };
});
