import { useEffect, useState, useCallback } from 'react';
import type { Metric, SemanticModel } from '@/types/semantic';
import { metricApi } from '@/api/metrics';
import { semanticModelApi } from '@/api/semanticModels';
import CreateModal from './CreateModal';

export default function MetricsPage() {
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [models, setModels] = useState<SemanticModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingMetric, setEditingMetric] = useState<Metric | null>(null);
  const [search, setSearch] = useState('');
  const [filterModel, setFilterModel] = useState('');

  /** 加载指标列表 */
  const fetchMetrics = useCallback(async () => {
    setLoading(true);
    try {
      const params: { page: number; page_size: number; semantic_model_id?: string; search?: string } = {
        page: 1,
        page_size: 100,
      };
      if (filterModel) params.semantic_model_id = filterModel;
      if (search) params.search = search;

      const res = await metricApi.list(params);
      setMetrics(res.data);
    } catch (err) {
      console.error('加载指标失败:', err);
    } finally {
      setLoading(false);
    }
  }, [filterModel, search]);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  useEffect(() => {
    semanticModelApi.list(1, 100).then((res) => setModels(res.data)).catch(() => {});
  }, []);

  /** 删除指标 */
  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`确定要删除指标 "${name}" 吗？`)) return;
    try {
      await metricApi.delete(id);
      await fetchMetrics();
    } catch (err) {
      console.error('删除指标失败:', err);
      alert('删除失败，请稍后重试');
    }
  };

  return (
    <div className="space-y-4">
      {/* 操作栏 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* 搜索框 */}
          <input
            type="text"
            placeholder="搜索指标..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-9 w-56 rounded-lg border border-gray-300 px-3 text-sm placeholder:text-gray-400 focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
          />
          {/* 模型筛选 */}
          <select
            value={filterModel}
            onChange={(e) => setFilterModel(e.target.value)}
            className="h-9 rounded-lg border border-gray-300 px-3 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
          >
            <option value="">全部语义模型</option>
            {models.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
          <span className="text-sm text-gray-500">共 {metrics.length} 个指标</span>
        </div>
        <button
          onClick={() => setEditingMetric(null); setShowCreateModal(true)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          创建指标
        </button>
      </div>

      {/* 表格 */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">名称</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">计算表达式</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">单位</th>
              <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-500">版本</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">标签</th>
              <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center text-sm text-gray-400">加载中...</td>
              </tr>
            ) : metrics.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center text-sm text-gray-400">
                  暂无指标，点击上方按钮创建
                </td>
              </tr>
            ) : (
              metrics.map((metric) => (
                <tr key={metric.id} className="transition-colors hover:bg-gray-50">
                  <td className="whitespace-nowrap px-6 py-4">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{metric.name}</p>
                      {metric.description && (
                        <p className="mt-0.5 text-xs text-gray-400">{metric.description}</p>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <code className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
                      {metric.calculation}
                    </code>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-600">
                    {metric.unit ?? '-'}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-center">
                    <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                      v{metric.version}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-1">
                      {metric.tags.length === 0 ? (
                        <span className="text-xs text-gray-400">-</span>
                      ) : (
                        metric.tags.map((tag) => (
                          <span key={tag} className="rounded-full bg-primary-50 px-2 py-0.5 text-xs text-primary-600">
                            {tag}
                          </span>
                        ))
                      )}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => { setEditingMetric(metric); setShowCreateModal(true); }}
                        className="inline-flex items-center rounded-md border border-gray-300 px-2.5 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50"
                      >
                        编辑
                      </button>
                      <button
                        onClick={() => handleDelete(metric.id, metric.name)}
                        className="inline-flex items-center rounded-md border border-red-200 px-2.5 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50"
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* 创建/编辑弹窗 */}
      {showCreateModal && (
        <CreateModal
          metric={editingMetric}
          onClose={() => { setShowCreateModal(false); setEditingMetric(null); }}
          onSuccess={() => {
            setShowCreateModal(false);
            setEditingMetric(null);
            fetchMetrics();
          }}
        />
      )}
    </div>
  );
}
