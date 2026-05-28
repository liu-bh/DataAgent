import { create } from 'zustand';
import type {
  ChatMessage,
  SendMessageRequest,
  QueryStatusType,
  ExecuteResponse,
} from '@/types/api';
import { apiClient } from '@/api/client';

interface ChatState {
  /** 当前会话的消息列表 */
  messages: ChatMessage[];
  /** 是否正在等待 AI 响应 */
  isLoading: boolean;
  /** NL2SQL 查询处理状态 */
  queryStatus: QueryStatusType;
  /** 查询失败时的错误信息 */
  queryError: string;
  /** 发送消息并获取 AI 回复 */
  sendMessage: (request: SendMessageRequest) => Promise<void>;
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
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isLoading: false,
  queryStatus: 'idle' as QueryStatusType,
  queryError: '',

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
}));
