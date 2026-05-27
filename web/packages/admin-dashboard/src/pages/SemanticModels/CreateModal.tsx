import { useState } from 'react';
import type { CreateSemanticModelRequest } from '@/types/semantic';
import { semanticModelApi } from '@/api/semanticModels';
import { dataSourceApi } from '@/api/dataSources';
import type { DataSource } from '@/types/semantic';
import { useEffect } from 'react';

/** 表单初始值 */
const INITIAL_FORM: CreateSemanticModelRequest = {
  name: '',
  description: '',
  domain: '',
  data_source_ids: [],
};

/** 创建弹窗 Props */
interface CreateModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

const DOMAINS = ['电商', '运营', '财务', '人力', '供应链', '其他'];

export default function CreateModal({ onClose, onSuccess }: CreateModalProps) {
  const [form, setForm] = useState<CreateSemanticModelRequest>(INITIAL_FORM);
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    dataSourceApi.list(1, 100).then((res) => setDataSources(res.data)).catch(() => {});
  }, []);

  const updateField = <K extends keyof CreateSemanticModelRequest>(key: K, value: CreateSemanticModelRequest[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  /** 切换数据源选择 */
  const toggleDataSource = (id: string) => {
    setForm((prev) => ({
      ...prev,
      data_source_ids: prev.data_source_ids.includes(id)
        ? prev.data_source_ids.filter((dsId) => dsId !== id)
        : [...prev.data_source_ids, id],
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!form.name.trim()) {
      setError('请输入语义模型名称');
      return;
    }
    if (!form.domain) {
      setError('请选择业务域');
      return;
    }

    setSubmitting(true);
    try {
      await semanticModelApi.create(form);
      onSuccess();
    } catch (err) {
      console.error('创建语义模型失败:', err);
      setError('创建失败，请稍后重试');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      <div className="relative w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">创建语义模型</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 名称 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => updateField('name', e.target.value)}
              placeholder="例如：电商核心指标"
              className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
            />
          </div>

          {/* 业务域 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              业务域 <span className="text-red-500">*</span>
            </label>
            <select
              value={form.domain}
              onChange={(e) => updateField('domain', e.target.value)}
              className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
            >
              <option value="">请选择</option>
              {DOMAINS.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>

          {/* 描述 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">描述</label>
            <textarea
              value={form.description}
              onChange={(e) => updateField('description', e.target.value)}
              placeholder="语义模型的业务含义和用途"
              rows={3}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
            />
          </div>

          {/* 关联数据源 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">关联数据源</label>
            <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-gray-200 p-2">
              {dataSources.length === 0 ? (
                <p className="py-2 text-center text-xs text-gray-400">暂无可用数据源</p>
              ) : (
                dataSources.map((ds) => (
                  <label
                    key={ds.id}
                    className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-gray-50"
                  >
                    <input
                      type="checkbox"
                      checked={form.data_source_ids.includes(ds.id)}
                      onChange={() => toggleDataSource(ds.id)}
                      className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-400"
                    />
                    <span className="text-gray-700">{ds.name}</span>
                    <span className="text-xs text-gray-400">({ds.type})</span>
                  </label>
                ))
              )}
            </div>
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
              {submitting ? '创建中...' : '创建'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
