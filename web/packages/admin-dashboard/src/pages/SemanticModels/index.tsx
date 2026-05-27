import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import type { SemanticModel } from '@/types/semantic';
import { semanticModelApi } from '@/api/semanticModels';
import CreateModal from './CreateModal';

/** 业务域标签颜色 */
const DOMAIN_COLORS: Record<string, string> = {
  电商: 'bg-blue-100 text-blue-700',
  运营: 'bg-purple-100 text-purple-700',
  财务: 'bg-green-100 text-green-700',
  人力: 'bg-orange-100 text-orange-700',
  供应链: 'bg-cyan-100 text-cyan-700',
};

export default function SemanticModelsPage() {
  const [models, setModels] = useState<SemanticModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const navigate = useNavigate();

  /** 加载列表 */
  const fetchModels = useCallback(async () => {
    setLoading(true);
    try {
      const res = await semanticModelApi.list(1, 100);
      setModels(res.data);
    } catch (err) {
      console.error('加载语义模型失败:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  /** 删除语义模型 */
  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`确定要删除语义模型 "${name}" 吗？关联的指标和维度也会被删除。`)) return;
    try {
      await semanticModelApi.delete(id);
      await fetchModels();
    } catch (err) {
      console.error('删除语义模型失败:', err);
      alert('删除失败，请稍后重试');
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <span className="text-gray-400">加载中...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 操作栏 */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">共 {models.length} 个语义模型</p>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          创建语义模型
        </button>
      </div>

      {/* 表格 */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">名称</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">业务域</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">描述</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">关联数据源</th>
              <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-500">指标数</th>
              <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-500">维度数</th>
              <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {models.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-12 text-center text-sm text-gray-400">
                  暂无语义模型，点击上方按钮创建
                </td>
              </tr>
            ) : (
              models.map((model) => (
                <tr key={model.id} className="transition-colors hover:bg-gray-50">
                  <td className="whitespace-nowrap px-6 py-4">
                    <button
                      onClick={() => navigate(`/admin/semantic-models/${model.id}`)}
                      className="text-sm font-medium text-primary-600 hover:text-primary-800"
                    >
                      {model.name}
                    </button>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${DOMAIN_COLORS[model.domain] ?? 'bg-gray-100 text-gray-700'}`}>
                      {model.domain}
                    </span>
                  </td>
                  <td className="max-w-xs truncate px-6 py-4 text-sm text-gray-500">
                    {model.description ?? '-'}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-600">
                    {model.data_source_ids.length} 个
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-center text-sm text-gray-600">
                    {model.metrics_count ?? 0}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-center text-sm text-gray-600">
                    {model.dimensions_count ?? 0}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => navigate(`/admin/semantic-models/${model.id}`)}
                        className="inline-flex items-center rounded-md border border-gray-300 px-2.5 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50"
                      >
                        详情
                      </button>
                      <button
                        onClick={() => handleDelete(model.id, model.name)}
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

      {/* 创建弹窗 */}
      {showCreateModal && (
        <CreateModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false);
            fetchModels();
          }}
        />
      )}
    </div>
  );
}
