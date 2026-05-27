import { useEffect, useState, useCallback } from 'react';
import type { Dimension, SemanticModel } from '@/types/semantic';
import { dimensionApi } from '@/api/dimensions';
import { semanticModelApi } from '@/api/semanticModels';
import CreateModal from './CreateModal';

export default function DimensionsPage() {
  const [dimensions, setDimensions] = useState<Dimension[]>([]);
  const [models, setModels] = useState<SemanticModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingDimension, setEditingDimension] = useState<Dimension | null>(null);
  const [search, setSearch] = useState('');
  const [filterModel, setFilterModel] = useState('');

  /** 加载维度列表 */
  const fetchDimensions = useCallback(async () => {
    setLoading(true);
    try {
      const params: { page: number; page_size: number; semantic_model_id?: string; search?: string } = {
        page: 1,
        page_size: 100,
      };
      if (filterModel) params.semantic_model_id = filterModel;
      if (search) params.search = search;

      const res = await dimensionApi.list(params);
      setDimensions(res.data);
    } catch (err) {
      console.error('加载维度失败:', err);
    } finally {
      setLoading(false);
    }
  }, [filterModel, search]);

  useEffect(() => {
    fetchDimensions();
  }, [fetchDimensions]);

  useEffect(() => {
    semanticModelApi.list(1, 100).then((res) => setModels(res.data)).catch(() => {});
  }, []);

  /** 删除维度 */
  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`确定要删除维度 "${name}" 吗？`)) return;
    try {
      await dimensionApi.delete(id);
      await fetchDimensions();
    } catch (err) {
      console.error('删除维度失败:', err);
      alert('删除失败，请稍后重试');
    }
  };

  return (
    <div className="space-y-4">
      {/* 操作栏 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="搜索维度..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-9 w-56 rounded-lg border border-gray-300 px-3 text-sm placeholder:text-gray-400 focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
          />
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
          <span className="text-sm text-gray-500">共 {dimensions.length} 个维度</span>
        </div>
        <button
          onClick={() => { setEditingDimension(null); setShowCreateModal(true); }}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          创建维度
        </button>
      </div>

      {/* 表格 */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">名称</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">物理列</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">同义词</th>
              <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-500">类型</th>
              <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-sm text-gray-400">加载中...</td>
              </tr>
            ) : dimensions.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-sm text-gray-400">
                  暂无维度，点击上方按钮创建
                </td>
              </tr>
            ) : (
              dimensions.map((dim) => (
                <tr key={dim.id} className="transition-colors hover:bg-gray-50">
                  <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-gray-900">
                    {dim.name}
                  </td>
                  <td className="px-6 py-4">
                    <code className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
                      {dim.column_name}
                    </code>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-1">
                      {dim.synonyms.length === 0 ? (
                        <span className="text-xs text-gray-400">-</span>
                      ) : (
                        dim.synonyms.map((s) => (
                          <span key={s} className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                            {s}
                          </span>
                        ))
                      )}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-center">
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      dim.is_virtual
                        ? 'bg-purple-100 text-purple-700'
                        : 'bg-gray-100 text-gray-700'
                    }`}>
                      {dim.is_virtual ? '虚拟' : '物理'}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => { setEditingDimension(dim); setShowCreateModal(true); }}
                        className="inline-flex items-center rounded-md border border-gray-300 px-2.5 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50"
                      >
                        编辑
                      </button>
                      <button
                        onClick={() => handleDelete(dim.id, dim.name)}
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
          dimension={editingDimension}
          onClose={() => { setShowCreateModal(false); setEditingDimension(null); }}
          onSuccess={() => {
            setShowCreateModal(false);
            setEditingDimension(null);
            fetchDimensions();
          }}
        />
      )}
    </div>
  );
}
