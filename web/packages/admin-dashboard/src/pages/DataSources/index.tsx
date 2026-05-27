import { useEffect, useState, useCallback } from 'react';
import type { DataSource, DataSourceHealth } from '@/types/semantic';
import { dataSourceApi } from '@/api/dataSources';
import RegisterModal from './RegisterModal';
import DetailDrawer from './DetailDrawer';

/** 健康状态指示灯 */
function HealthIndicator({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    healthy: 'bg-green-500',
    degraded: 'bg-yellow-500',
    down: 'bg-red-500',
    unknown: 'bg-gray-300',
  };
  const labelMap: Record<string, string> = {
    healthy: '健康',
    degraded: '降级',
    down: '不可用',
    unknown: '未知',
  };
  const color = colorMap[status] ?? colorMap['unknown'];
  const label = labelMap[status] ?? labelMap['unknown'];

  return (
    <span className="flex items-center gap-2">
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${color}`} />
      <span className="text-sm text-gray-600">{label}</span>
    </span>
  );
}

/** 数据源类型标签 */
function TypeBadge({ type }: { type: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700">
      {type.toUpperCase()}
    </span>
  );
}

export default function DataSourcesPage() {
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [healthMap, setHealthMap] = useState<Record<string, DataSourceHealth>>({});
  const [syncingId, setSyncingId] = useState<string | null>(null);

  /** 加载数据源列表 */
  const fetchDataSources = useCallback(async () => {
    setLoading(true);
    try {
      const res = await dataSourceApi.list(1, 100);
      setDataSources(res.data);
    } catch (err) {
      console.error('加载数据源失败:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  /** 加载所有数据源健康状态 */
  const fetchHealth = useCallback(async () => {
    try {
      const healthResults = await Promise.allSettled(
        dataSources.map((ds) => dataSourceApi.health(ds.id)),
      );
      const map: Record<string, DataSourceHealth> = {};
      healthResults.forEach((result, index) => {
        if (result.status === 'fulfilled') {
          map[dataSources[index]!.id] = result.value;
        }
      });
      setHealthMap(map);
    } catch {
      // 健康状态加载失败不影响主流程
    }
  }, [dataSources]);

  useEffect(() => {
    fetchDataSources();
  }, [fetchDataSources]);

  useEffect(() => {
    if (dataSources.length > 0) {
      fetchHealth();
    }
  }, [fetchHealth]);

  /** 触发同步 */
  const handleSync = async (id: string) => {
    setSyncingId(id);
    try {
      const result = await dataSourceApi.sync(id);
      alert(`同步任务已触发: ${result.message}`);
      // 同步后重新加载数据
      await fetchDataSources();
    } catch (err) {
      console.error('触发同步失败:', err);
      alert('触发同步失败，请稍后重试');
    } finally {
      setSyncingId(null);
    }
  };

  /** 删除数据源 */
  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`确定要删除数据源 "${name}" 吗？此操作不可撤销。`)) return;
    try {
      await dataSourceApi.delete(id);
      await fetchDataSources();
    } catch (err) {
      console.error('删除数据源失败:', err);
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
        <p className="text-sm text-gray-500">共 {dataSources.length} 个数据源</p>
        <button
          onClick={() => setShowRegisterModal(true)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          注册数据源
        </button>
      </div>

      {/* 数据源表格 */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">名称</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">类型</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">状态</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">健康</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">数据库</th>
              <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {dataSources.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center text-sm text-gray-400">
                  暂无数据源，点击上方按钮注册
                </td>
              </tr>
            ) : (
              dataSources.map((ds) => (
                <tr key={ds.id} className="transition-colors hover:bg-gray-50">
                  <td className="whitespace-nowrap px-6 py-4">
                    <button
                      onClick={() => setDetailId(ds.id)}
                      className="text-sm font-medium text-primary-600 hover:text-primary-800"
                    >
                      {ds.name}
                    </button>
                    <p className="mt-0.5 text-xs text-gray-400">{ds.host}:{ds.port}</p>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <TypeBadge type={ds.type} />
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <span className={`text-sm ${ds.status === 'active' ? 'text-green-600' : 'text-gray-400'}`}>
                      {ds.status === 'active' ? '已启用' : '已禁用'}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <HealthIndicator status={healthMap[ds.id]?.status ?? 'unknown'} />
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-600">
                    {ds.database}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleSync(ds.id)}
                        disabled={syncingId === ds.id}
                        className="inline-flex items-center gap-1 rounded-md border border-gray-300 px-2.5 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-50"
                      >
                        {syncingId === ds.id ? (
                          <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                        ) : (
                          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
                          </svg>
                        )}
                        同步
                      </button>
                      <button
                        onClick={() => setDetailId(ds.id)}
                        className="inline-flex items-center rounded-md border border-gray-300 px-2.5 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50"
                      >
                        详情
                      </button>
                      <button
                        onClick={() => handleDelete(ds.id, ds.name)}
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

      {/* 注册弹窗 */}
      {showRegisterModal && (
        <RegisterModal
          onClose={() => setShowRegisterModal(false)}
          onSuccess={() => {
            setShowRegisterModal(false);
            fetchDataSources();
          }}
        />
      )}

      {/* 详情抽屉 */}
      {detailId && (
        <DetailDrawer
          dataSourceId={detailId}
          onClose={() => setDetailId(null)}
        />
      )}
    </div>
  );
}
