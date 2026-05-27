import { create } from 'zustand';
import type { Session, CreateSessionRequest, UpdateSessionRequest } from '@/types/api';
import { apiClient } from '@/api/client';

interface SessionState {
  /** 会话列表 */
  sessions: Session[];
  /** 当前选中的会话 ID */
  activeSessionId: string | null;
  /** 是否正在加载 */
  isLoading: boolean;
  /** 加载会话列表 */
  fetchSessions: () => Promise<void>;
  /** 创建新会话 */
  createSession: (request?: CreateSessionRequest) => Promise<Session>;
  /** 更新会话 */
  updateSession: (id: string, request: UpdateSessionRequest) => Promise<void>;
  /** 删除会话 */
  deleteSession: (id: string) => Promise<void>;
  /** 设置活跃会话 */
  setActiveSession: (id: string | null) => void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessions: [],
  activeSessionId: null,
  isLoading: false,

  fetchSessions: async () => {
    set({ isLoading: true });
    try {
      const { data } = await apiClient.get<{ data: Session[] }>(
        '/api/v1/sessions',
      );
      set({ sessions: data.data, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },

  createSession: async (request) => {
    const { data } = await apiClient.post<{ data: Session }>(
      '/api/v1/sessions',
      request ?? {},
    );
    const newSession = data.data;
    set((state) => ({
      sessions: [newSession, ...state.sessions],
      activeSessionId: newSession.id,
    }));
    return newSession;
  },

  updateSession: async (id, request) => {
    await apiClient.patch(`/api/v1/sessions/${id}`, request);
    // 更新本地列表
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === id ? { ...s, ...request, updated_at: new Date().toISOString() } : s,
      ),
    }));
  },

  deleteSession: async (id) => {
    await apiClient.delete(`/api/v1/sessions/${id}`);
    const { activeSessionId } = get();
    set((state) => ({
      sessions: state.sessions.filter((s) => s.id !== id),
      activeSessionId: activeSessionId === id ? null : activeSessionId,
    }));
  },

  setActiveSession: (id) => {
    set({ activeSessionId: id });
  },
}));
