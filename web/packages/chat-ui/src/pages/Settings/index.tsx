import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSettingsStore } from '@/stores/settingsStore';
import Button from '@/components/Button';
import type { UserSettings } from '@/types/settings';

export default function Settings() {
  const navigate = useNavigate();
  const { settings, updateSettings, resetSettings } = useSettingsStore();

  const [form, setForm] = useState<UserSettings>({ ...settings });
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    updateSettings(form);
    setSaved(true);
    // 3 秒后隐藏提示
    setTimeout(() => setSaved(false), 3000);
  };

  const handleReset = () => {
    const defaults: UserSettings = {
      theme: 'system',
      defaultDialect: 'mysql',
      defaultTenantId: '',
    };
    resetSettings();
    setForm({ ...defaults });
    setSaved(false);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-2xl px-4 py-12">
        {/* 返回按钮 + 标题 */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <button
              onClick={() => navigate(-1)}
              className="mb-3 flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
            >
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M15 19l-7-7 7-7"
                />
              </svg>
              返回
            </button>
            <h1 className="text-2xl font-bold text-gray-900">设置</h1>
            <p className="mt-1 text-sm text-gray-500">
              管理您的 DataPilot 偏好设置
            </p>
          </div>
        </div>

        {/* 保存成功提示 */}
        {saved && (
          <div className="mb-4 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700">
            设置已保存
          </div>
        )}

        {/* 设置卡片区域 */}
        <div className="space-y-6">
          {/* 外观设置 */}
          <div className="rounded-2xl border border-gray-200 bg-white p-6">
            <h2 className="text-base font-semibold text-gray-900 mb-1">
              外观设置
            </h2>
            <p className="text-sm text-gray-500 mb-4">
              选择界面主题偏好
            </p>

            <div className="flex flex-wrap gap-3">
              {([
                { value: 'light', label: '亮色' },
                { value: 'dark', label: '暗色' },
                { value: 'system', label: '跟随系统' },
              ] as const).map((opt) => (
                <label
                  key={opt.value}
                  className={`flex cursor-pointer items-center gap-2 rounded-lg border px-4 py-2.5 text-sm transition-colors ${
                    form.theme === opt.value
                      ? 'border-primary-500 bg-primary-50 text-primary-700'
                      : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
                  }`}
                >
                  <input
                    type="radio"
                    name="theme"
                    value={opt.value}
                    checked={form.theme === opt.value}
                    onChange={() =>
                      setForm((prev) => ({ ...prev, theme: opt.value }))
                    }
                    className="sr-only"
                  />
                  {opt.value === 'light' && (
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                    </svg>
                  )}
                  {opt.value === 'dark' && (
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                    </svg>
                  )}
                  {opt.value === 'system' && (
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                  )}
                  {opt.label}
                </label>
              ))}
            </div>
          </div>

          {/* SQL 方言 */}
          <div className="rounded-2xl border border-gray-200 bg-white p-6">
            <h2 className="text-base font-semibold text-gray-900 mb-1">
              SQL 方言
            </h2>
            <p className="text-sm text-gray-500 mb-4">
              设置默认的 SQL 生成方言
            </p>

            <select
              value={form.defaultDialect}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  defaultDialect: e.target.value as UserSettings['defaultDialect'],
                }))
              }
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 transition-colors focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
            >
              <option value="mysql">MySQL</option>
              <option value="postgresql">PostgreSQL</option>
              <option value="clickhouse">ClickHouse</option>
            </select>
          </div>

          {/* 租户配置 */}
          <div className="rounded-2xl border border-gray-200 bg-white p-6">
            <h2 className="text-base font-semibold text-gray-900 mb-1">
              租户配置
            </h2>
            <p className="text-sm text-gray-500 mb-4">
              设置默认租户 ID，用于多租户查询隔离
            </p>

            <input
              type="text"
              value={form.defaultTenantId}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  defaultTenantId: e.target.value,
                }))
              }
              placeholder="请输入默认租户 ID"
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder-gray-400 transition-colors focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
            />
          </div>
        </div>

        {/* 操作按钮 */}
        <div className="mt-8 flex items-center justify-end gap-3">
          <Button variant="ghost" onClick={handleReset}>
            恢复默认
          </Button>
          <Button variant="primary" onClick={handleSave}>
            保存设置
          </Button>
        </div>
      </div>
    </div>
  );
}
