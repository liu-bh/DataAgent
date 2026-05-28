import { create } from 'zustand';
import type { User, LoginRequest } from '@/types/api';
import { apiClient } from '@/api/client';

interface AuthState {
  /** JWT access token */
  token: string | null;
  /** 当前登录用户 */
  user: User | null;
  /** 是否正在加载 */
  isLoading: boolean;
  /** 新手引导是否已完成 */
  onboardingCompleted: boolean;
  /** 登录 */
  login: (request: LoginRequest) => Promise<void>;
  /** 登出 */
  logout: () => void;
  /** 获取当前用户信息 */
  fetchMe: () => Promise<void>;
  /** 设置新手引导完成状态 */
  setOnboardingCompleted: (completed: boolean) => void;
  /** 从 localStorage 读取新手引导状态 */
  checkOnboarding: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('datapilot_token'),
  user: null,
  isLoading: false,
  onboardingCompleted: localStorage.getItem('datapilot_onboarding_completed') === 'true',

  login: async (request) => {
    set({ isLoading: true });
    try {
      const { data } = await apiClient.post<{
        data: { access_token: string; refresh_token: string };
      }>('/api/v1/auth/login', request);
      const token = data.data.access_token;
      localStorage.setItem('datapilot_token', token);
      set({ token, isLoading: false });
    } catch {
      set({ isLoading: false });
      throw new Error('登录失败，请检查用户名和密码');
    }
  },

  logout: () => {
    const token = useAuthStore.getState().token;
    if (token) {
      // 尝试通知后端吊销 token，但不等待
      apiClient.post('/api/v1/auth/logout').catch(() => {});
    }
    localStorage.removeItem('datapilot_token');
    set({ token: null, user: null });
  },

  fetchMe: async () => {
    set({ isLoading: true });
    try {
      const { data } = await apiClient.get<{ data: User }>('/api/v1/auth/me');
      set({ user: data.data, isLoading: false });
    } catch {
      set({ isLoading: false });
      // Token 无效，清除登录状态
      localStorage.removeItem('datapilot_token');
      set({ token: null, user: null });
    }
  },

  setOnboardingCompleted: (completed: boolean) => {
    if (completed) {
      localStorage.setItem('datapilot_onboarding_completed', 'true');
    } else {
      localStorage.removeItem('datapilot_onboarding_completed');
    }
    set({ onboardingCompleted: completed });
  },

  checkOnboarding: () => {
    const completed = localStorage.getItem('datapilot_onboarding_completed') === 'true';
    set({ onboardingCompleted: completed });
  },
}));
