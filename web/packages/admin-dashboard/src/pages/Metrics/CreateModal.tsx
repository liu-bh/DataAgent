import { useState, useEffect } from 'react';
import type { Metric, SemanticModel, CreateMetricRequest, UpdateMetricRequest } from '@/types/semantic';
import { metricApi } from '@/api/metrics';
import { semanticModelApi } from '@/api/semanticModels';

/** 表单数据 */
interface FormData {
  semantic_model_id: string;
  name: string;
  description: string;
  calculation: string;
  unit: string;
  tags: string;
}

/** 创建弹窗 Props */
interface CreateModalProps {
  metric?: Metric | null;
  onClose: () => void;
  onSuccess: () => void;
}

export default function CreateModal({ metric, onClose, onSuccess }: CreateModalProps) {
  const isEdit = !!metric;

  const [form, setForm] = useState<FormData>({
    semantic_model_id: '',
    name: '',
    description: '',
    calculation: '',
    unit: '',
    tags: '',
  });
  const [models, setModels] = useState<SemanticModel[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    semanticModelApi.list(1, 100).then((res) => setModels(res.data)).catch(() => {});
  }, []);

  // 编辑模式填充表单
  useEffect(() => {
    if (metric) {
      setForm({
        semantic_model_id: metric.semantic_model_id,
        name: metric.name,
        description: metric.description ?? '',
        calculation: metric.calculation,
        unit: metric.unit ?? '',
        tags: metric.tags.join(', '),
      });
    }
  }, [metric]);

  const updateField = <K extends keyof FormData>(key: K, value: FormData[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!form.name.trim()) { setError('请输入指标名称'); return; }
    if (!form.calculation.trim()) { setError('请输入计算表达式'); return; }
    if (!isEdit && !form.semantic_model_id) { setError('请选择语义模型'); return; }

    const tags = form.tags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);

    setSubmitting(true);
    try {
      if (isEdit && metric) {
        const data: UpdateMetricRequest = {
          name: form.name,
          description: form.description,
          calculation: form.calculation,
          unit: form.unit,
          tags,
        };
        await metricApi.update(metric.id, data);
      } else {
        const data: CreateMetricRequest = {
          semantic_model_id: form.semantic_model_id,
          name: form.name,
          description: form.description,
          calculation: form.calculation,
          unit: form.unit,
          tags,
        };
        await metricApi.create(data);
      }
      onSuccess();
    } catch (err) {
      console.error('保存指标失败:', err);
      setError(isEdit ? '更新失败，请稍后重试' : '创建失败，请稍后重试');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      <div className="relative w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            {isEdit ? `编辑指标 - ${metric!.name}` : '创建指标'}
          </h2>
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
          {/* 语义模型（创建时显示） */}
          {!isEdit && (
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                语义模型 <span className="text-red-500">*</span>
              </label>
              <select
                value={form.semantic_model_id}
                onChange={(e) => updateField('semantic_model_id', e.target.value)}
                className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
              >
                <option value="">请选择语义模型</option>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>{m.name} ({m.domain})</option>
                ))}
              </select>
            </div>
          )}

          {/* 名称 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              指标名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => updateField('name', e.target.value)}
              placeholder="例如：GMV、订单转化率"
              className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
            />
          </div>

          {/* 描述 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">描述</label>
            <textarea
              value={form.description}
              onChange={(e) => updateField('description', e.target.value)}
              placeholder="指标的业务含义"
              rows={2}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
            />
          </div>

          {/* 计算表达式 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              计算表达式 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.calculation}
              onChange={(e) => updateField('calculation', e.target.value)}
              placeholder="例如：SUM(payment_amount)"
              className="h-9 w-full rounded-lg border border-gray-300 px-3 font-mono text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
            />
          </div>

          {/* 单位 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">单位</label>
            <input
              type="text"
              value={form.unit}
              onChange={(e) => updateField('unit', e.target.value)}
              placeholder="例如：元、个、率"
              className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
            />
          </div>

          {/* 标签 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">标签</label>
            <input
              type="text"
              value={form.tags}
              onChange={(e) => updateField('tags', e.target.value)}
              placeholder="逗号分隔，例如：核心指标,营收"
              className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
            />
          </div>

          {/* 版本历史（编辑时展示） */}
          {isEdit && metric && (
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
              <p className="mb-1 text-xs font-medium text-gray-500">版本信息</p>
              <p className="text-sm text-gray-700">
                当前版本: <span className="font-medium">v{metric.version}</span>
                {metric.effective_time && (
                  <span className="ml-2 text-gray-400">
                    生效时间: {new Date(metric.effective_time).toLocaleString()}
                  </span>
                )}
              </p>
              <p className="mt-1 text-xs text-gray-400">更新后将创建新版本</p>
            </div>
          )}

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
              {submitting ? '保存中...' : isEdit ? '保存' : '创建'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
