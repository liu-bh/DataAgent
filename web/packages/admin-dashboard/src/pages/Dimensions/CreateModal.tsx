import { useState, useEffect } from 'react';
import type { Dimension, SemanticModel, SourceTable, CreateDimensionRequest, UpdateDimensionRequest } from '@/types/semantic';
import { dimensionApi } from '@/api/dimensions';
import { semanticModelApi } from '@/api/semanticModels';
import { dataSourceApi } from '@/api/dataSources';

/** 表单数据 */
interface FormData {
  semantic_model_id: string;
  name: string;
  column_name: string;
  table_id: string;
  synonyms: string;
  is_virtual: boolean;
  virtual_expression: string;
}

/** 创建弹窗 Props */
interface CreateModalProps {
  dimension?: Dimension | null;
  onClose: () => void;
  onSuccess: () => void;
}

export default function CreateModal({ dimension, onClose, onSuccess }: CreateModalProps) {
  const isEdit = !!dimension;

  const [form, setForm] = useState<FormData>({
    semantic_model_id: '',
    name: '',
    column_name: '',
    table_id: '',
    synonyms: '',
    is_virtual: false,
    virtual_expression: '',
  });
  const [models, setModels] = useState<SemanticModel[]>([]);
  const [tables, setTables] = useState<SourceTable[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    semanticModelApi.list(1, 100).then((res) => setModels(res.data)).catch(() => {});
  }, []);

  // 编辑模式填充表单
  useEffect(() => {
    if (dimension) {
      setForm({
        semantic_model_id: dimension.semantic_model_id,
        name: dimension.name,
        column_name: dimension.column_name,
        table_id: dimension.table_id,
        synonyms: dimension.synonyms.join(', '),
        is_virtual: dimension.is_virtual,
        virtual_expression: dimension.virtual_expression ?? '',
      });
    }
  }, [dimension]);

  /** 语义模型变更时加载对应的表 */
  const handleModelChange = async (modelId: string) => {
    setForm((prev) => ({ ...prev, semantic_model_id: modelId, table_id: '' }));
    if (!modelId) {
      setTables([]);
      return;
    }
    try {
      const model = models.find((m) => m.id === modelId);
      if (!model) return;

      const allTables: SourceTable[] = [];
      for (const dsId of model.data_source_ids) {
        try {
          const dsTables = await dataSourceApi.tables(dsId);
          allTables.push(...dsTables);
        } catch {
          // 忽略单个数据源加载失败
        }
      }
      setTables(allTables);
    } catch {
      setTables([]);
    }
  };

  /** Tag input: 输入同义词后按回车添加 */
  const [inputValue, setInputValue] = useState('');

  const handleSynonymKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const value = inputValue.trim();
      if (value && !form.synonyms.includes(value)) {
        const newSynonyms = form.synonyms ? `${form.synonyms}, ${value}` : value;
        setForm((prev) => ({ ...prev, synonyms: newSynonyms }));
      }
      setInputValue('');
    }
  };

  /** 移除同义词 */
  const removeSynonym = (synonym: string) => {
    const list = form.synonyms.split(',').map((s) => s.trim()).filter(Boolean);
    const filtered = list.filter((s) => s !== synonym);
    setForm((prev) => ({ ...prev, synonyms: filtered.join(', ') }));
  };

  const updateField = <K extends keyof FormData>(key: K, value: FormData[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!form.name.trim()) { setError('请输入维度名称'); return; }
    if (!form.column_name.trim()) { setError('请输入物理列名'); return; }
    if (!isEdit && !form.semantic_model_id) { setError('请选择语义模型'); return; }
    if (form.is_virtual && !form.virtual_expression.trim()) { setError('虚拟维度需要填写表达式'); return; }

    const synonyms = form.synonyms
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    setSubmitting(true);
    try {
      if (isEdit && dimension) {
        const data: UpdateDimensionRequest = {
          name: form.name,
          column_name: form.column_name,
          table_id: form.table_id,
          synonyms,
          is_virtual: form.is_virtual,
          virtual_expression: form.virtual_expression || undefined,
        };
        await dimensionApi.update(dimension.id, data);
      } else {
        const data: CreateDimensionRequest = {
          semantic_model_id: form.semantic_model_id,
          name: form.name,
          column_name: form.column_name,
          table_id: form.table_id,
          synonyms,
          is_virtual: form.is_virtual,
          virtual_expression: form.virtual_expression || undefined,
        };
        await dimensionApi.create(data);
      }
      onSuccess();
    } catch (err) {
      console.error('保存维度失败:', err);
      setError(isEdit ? '更新失败，请稍后重试' : '创建失败，请稍后重试');
    } finally {
      setSubmitting(false);
    }
  };

  // 当前同义词列表
  const currentSynonyms = form.synonyms.split(',').map((s) => s.trim()).filter(Boolean);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      <div className="relative w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            {isEdit ? `编辑维度 - ${dimension!.name}` : '创建维度'}
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
          {/* 语义模型 */}
          {!isEdit && (
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                语义模型 <span className="text-red-500">*</span>
              </label>
              <select
                value={form.semantic_model_id}
                onChange={(e) => handleModelChange(e.target.value)}
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
              维度名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => updateField('name', e.target.value)}
              placeholder="例如：地区、时间"
              className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
            />
          </div>

          {/* 物理列 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              物理列 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.column_name}
              onChange={(e) => updateField('column_name', e.target.value)}
              placeholder="例如：orders.region"
              className="h-9 w-full rounded-lg border border-gray-300 px-3 font-mono text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
            />
          </div>

          {/* 所属表（创建时显示） */}
          {!isEdit && (
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">所属表</label>
              <select
                value={form.table_id}
                onChange={(e) => updateField('table_id', e.target.value)}
                disabled={!form.semantic_model_id}
                className="h-9 w-full rounded-lg border border-gray-300 px-3 text-sm disabled:bg-gray-100 disabled:text-gray-400 focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
              >
                <option value="">请先选择语义模型</option>
                {tables.map((t) => (
                  <option key={t.id} value={t.id}>{t.schema_name}.{t.table_name}</option>
                ))}
              </select>
            </div>
          )}

          {/* 同义词管理 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">同义词</label>
            <div className="flex flex-wrap gap-1.5 rounded-lg border border-gray-300 p-2">
              {currentSynonyms.map((synonym) => (
                <span
                  key={synonym}
                  className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-1 text-xs text-gray-700"
                >
                  {synonym}
                  <button
                    type="button"
                    onClick={() => removeSynonym(synonym)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </span>
              ))}
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleSynonymKeyDown}
                placeholder={currentSynonyms.length === 0 ? '输入后按回车添加' : ''}
                className="min-w-[80px] flex-1 border-0 bg-transparent text-xs placeholder:text-gray-400 focus:outline-none"
              />
            </div>
            <p className="mt-1 text-xs text-gray-400">输入同义词后按回车添加</p>
          </div>

          {/* 虚拟维度 */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
              <input
                type="checkbox"
                checked={form.is_virtual}
                onChange={(e) => updateField('is_virtual', e.target.checked)}
                className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-400"
              />
              虚拟维度（CASE WHEN 计算）
            </label>
            {form.is_virtual && (
              <textarea
                value={form.virtual_expression}
                onChange={(e) => updateField('virtual_expression', e.target.value)}
                placeholder="例如：CASE WHEN age < 18 THEN '未成年' WHEN age < 60 THEN '成年' ELSE '老年' END"
                rows={3}
                className="mt-2 w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
              />
            )}
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
              {submitting ? '保存中...' : isEdit ? '保存' : '创建'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
