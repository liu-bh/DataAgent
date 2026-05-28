import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { UserSettings } from '@/types/settings';

interface SettingsState {
  /** 用户偏好设置 */
  settings: UserSettings;
  /** 更新设置（部分更新） */
  updateSettings: (partial: Partial<UserSettings>) => void;
  /** 重置为默认设置 */
  resetSettings: () => void;
}

const DEFAULT_SETTINGS: UserSettings = {
  theme: 'system',
  defaultDialect: 'mysql',
  defaultTenantId: '',
};

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      settings: { ...DEFAULT_SETTINGS },

      updateSettings: (partial: Partial<UserSettings>) => {
        set((state) => ({
          settings: { ...state.settings, ...partial },
        }));
      },

      resetSettings: () => {
        set({ settings: { ...DEFAULT_SETTINGS } });
      },
    }),
    {
      name: 'datapilot-settings',
    },
  ),
);
