import { create } from 'zustand';
import type { ChatMessage, SendMessageRequest } from '@/types/api';
import { apiClient } from '@/api/client';

interface ChatState {
  /** 当前会话的消息列表 */
  messages: ChatMessage[];
  /** 是否正在等待 AI 响应 */
  isLoading: boolean;
  /** 发送消息并获取 AI 回复 */
  sendMessage: (request: SendMessageRequest) => Promise<void>;
  /** 清空消息列表 */
  clearMessages: () => void;
  /** 加载历史消息 */
  loadMessages: (sessionId: string) => Promise<void>;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isLoading: false,

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
    }));

    try {
      const { data } = await apiClient.post<{
        data: ChatMessage;
        trace_id?: string;
      }>('/api/v1/chat/message', request);

      const assistantMessage: ChatMessage = data.data;

      set((state) => ({
        messages: [...state.messages, assistantMessage],
        isLoading: false,
      }));
    } catch {
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
      }));
    }
  },

  clearMessages: () => {
    set({ messages: [] });
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
}));
