import { useState } from 'react';
import type { DataSourceType, CreateDataSourceRequest } from '@/types/semantic';
import { dataSourceApi } from '@/api/dataSources';

/** 表单数据 */
interface FormData extends CreateDataSourceRequest {}

const DATA_SOURCE_TYPES: { value: DataSourceType; label: string }[] = [
  { value: 'mysql', label: 'MySQL' },
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'doris', label: 'Doris' },
  { value: 'starrocks', label: 'StarRocks' },
  { value: 'clickhouse', label: 'ClickHouse' },
];

/** 各类型默认端口 */
const DEFAULT_PORTS: Record<DataSourceType, number> = {
  mysql: 3306,
  postgresql: 5432,
  doris: 9030,
  starrocks: 9030,
  clickhouse: 8123,
  api: 443,
};

/** 表单初始值 */
const INITIAL_FORM: FormData = {
  name: '',
  type: 'mysql',
  host: '',
  port: 3306,
  database: '',
  username: '',
  password: '',
  pool_size: 10,
  freshness_level: 'daily',
};

/** 注册弹窗 Props */
interface RegisterModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

export default function RegisterModal({ onClose, onSuccess }: RegisterModalProps) {
  const [form, setForm] = useState<FormData>(INITIAL_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** 更新表单字段 */
  const updateField = <K extends keyof FormData>(key: K, value: FormData[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  /** 类型变更时自动设置默认端口 */
  const handleTypeChange = (type: DataSourceType) => {
    setForm((prev) => ({ ...prev, type, port: DEFAULT_PORTS[type] }));
  };

  /** 提交表单 */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // 基础校验
    if (!form.name.trim()) {
      setError('请输入数据源名称');
      return;
    }
    if (!form.host.trim()) {
      setError('请输入连接地址');
      return;
    }
    if (!form.database.trim()) {
      setError('请输入数据库名');
      return;
    }
    if (!form.username.trim()) {
      setError('请输入用户名');
      return;
    }
    if (!form.password.trim()) {
      setError('请输入密码');
      return;
    }

    setSubmitting(true);
    try {
      await dataSourceApi.create(form);
      onSuccess();
    } catch (err) {
      console.error('注册数据源失败:', err);
      setError('注册失败，请检查连接信息后重试');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 遮罩层 */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* 弹窗内容 */}
      <div className="relative w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        {/* 标题 */}
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">注册数据源</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
            {error}
          </div>
        )}

        {/* 表单 */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 名称 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              数据源名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => updateField('name', e.target.value)}
              placeholder="例如：生产订单库"
              className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
            />
          </div>

          {/* 类型 + 端口 */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                类型 <span className="text-red-500">*</span>
              </label>
              <select
                value={form.type}
                onChange={(e) => handleTypeChange(e.target.value as DataSourceType)}
                className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
              >
                {DATA_SOURCE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">端口</label>
              <input
                type="number"
                value={form.port}
                onChange={(e) => updateField('port', Number(e.target.value))}
                className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
              />
            </div>
          </div>

          {/* Host + Database */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                连接地址 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={form.host}
                onChange={(e) => updateField('host', e.target.value)}
                placeholder="例如：192.168.1.100"
                className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                数据库名 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={form.database}
                onChange={(e) => updateField('database', e.target.value)}
                placeholder="例如：order_db"
                className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
              />
            </div>
          </div>

          {/* 用户名 + 密码 */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                用户名 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={form.username}
                onChange={(e) => updateField('username', e.target.value)}
                placeholder="数据库用户名"
                className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                密码 <span className="text-red-500">*</span>
              </label>
              <input
                type="password"
                value={form.password}
                onChange={(e) => updateField('password', e.target.value)}
                placeholder="数据库密码"
                className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
              />
            </div>
          </div>

          {/* 连接池大小 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">连接池大小</label>
            <input
              type="number"
              value={form.pool_size}
              onChange={(e) => updateField('pool_size', Number(e.target.value))}
              min={1}
              max={100}
              className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
            />
          </div>

          {/* 新鲜度 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">数据新鲜度</label>
            <select
              value={form.freshness_level}
              onChange={(e) => updateField('freshness_level', e.target.value as FormData['freshness_level'])}
              className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
            >
              <option value="realtime">实时</option>
              <option value="hourly">每小时</option>
              <option value="daily">每天</option>
              <option value="custom">自定义</option>
            </select>
          </div>

          {/* 底部按钮 */}
          <div className="flex items-center justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:opacity-50"
            >
              {submitting && (
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              )}
              {submitting ? '注册中...' : '注册'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
