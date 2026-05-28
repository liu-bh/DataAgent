import { create } from 'zustand';
import type { DashboardLayout } from '../types/dashboard';
import * as dashboardApi from '../api/dashboard';

interface DashboardState {
  /** Dashboard 列表 */
  dashboards: DashboardLayout[];
  /** 当前激活的 Dashboard */
  activeDashboard: DashboardLayout | null;
  /** 加载状态 */
  loading: boolean;
  /** 错误信息 */
  error: string;
  /** 获取 Dashboard 列表 */
  fetchDashboards: () => Promise<void>;
  /** 创建 Dashboard */
  createDashboard: (
    title: string,
    description?: string,
    chart_specs?: unknown[],
  ) => Promise<void>;
  /** 选中并加载某个 Dashboard */
  selectDashboard: (id: string) => Promise<void>;
  /** 删除 Dashboard */
  deleteDashboard: (id: string) => Promise<void>;
  /** 清除错误信息 */
  clearError: () => void;
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  dashboards: [],
  activeDashboard: null,
  loading: false,
  error: '',

  fetchDashboards: async () => {
    set({ loading: true, error: '' });
    try {
      const dashboards = await dashboardApi.listDashboards();
      set({ dashboards, loading: false });
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : '获取 Dashboard 列表失败';
      set({ error: errorMsg, loading: false });
    }
  },

  createDashboard: async (title, description, chart_specs) => {
    set({ loading: true, error: '' });
    try {
      const newDashboard = await dashboardApi.createDashboard({
        title,
        description,
        chart_specs,
      });
      set((state) => ({
        dashboards: [newDashboard, ...state.dashboards],
        activeDashboard: newDashboard,
        loading: false,
      }));
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : '创建 Dashboard 失败';
      set({ error: errorMsg, loading: false });
    }
  },

  selectDashboard: async (id) => {
    set({ loading: true, error: '' });
    try {
      const dashboard = await dashboardApi.getDashboard(id);
      set({ activeDashboard: dashboard, loading: false });
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : '加载 Dashboard 失败';
      set({ error: errorMsg, loading: false });
    }
  },

  deleteDashboard: async (id) => {
    set({ loading: true, error: '' });
    try {
      await dashboardApi.deleteDashboard(id);
      const { activeDashboard } = get();
      set((state) => ({
        dashboards: state.dashboards.filter(
          (d) => d.dashboard_id !== id,
        ),
        // 如果删除的是当前激活的 Dashboard，则清空
        activeDashboard:
          activeDashboard?.dashboard_id === id ? null : activeDashboard,
        loading: false,
      }));
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : '删除 Dashboard 失败';
      set({ error: errorMsg, loading: false });
    }
  },

  clearError: () => {
    set({ error: '' });
  },
}));
