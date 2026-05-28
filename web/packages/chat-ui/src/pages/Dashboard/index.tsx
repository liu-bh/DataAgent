import { useEffect, useState } from 'react';
import { useDashboardStore } from '@/stores/dashboardStore';
import DashboardLayoutView from '@/components/DashboardLayout';
import DashboardFilterBar from '@/components/DashboardFilter';

/**
 * Dashboard 主页面
 * 左侧面板列表 + 右侧仪表板详情
 */
export default function DashboardPage() {
  const {
    dashboards,
    activeDashboard,
    loading,
    error,
    fetchDashboards,
    createDashboard,
    selectDashboard,
    deleteDashboard,
    clearError,
  } = useDashboardStore();

  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState('');

  useEffect(() => {
    fetchDashboards();
  }, [fetchDashboards]);

  const handleCreate = async () => {
    if (!newTitle.trim()) return;
    await createDashboard(newTitle.trim());
    setNewTitle('');
    setShowCreate(false);
  };

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除该仪表板？')) return;
    await deleteDashboard(id);
  };

  if (loading && dashboards.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <div className="mb-2 h-8 w-8 animate-spin rounded-full border-2 border-gray-600 border-t-primary-500 mx-auto" />
          <p className="text-sm text-gray-400">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* 左侧面板列表 */}
      <aside className="w-64 flex-shrink-0 border-r border-gray-700 bg-gray-900">
        <div className="flex items-center justify-between border-b border-gray-700 px-4 py-3">
          <h2 className="text-sm font-medium text-gray-200">仪表板</h2>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="rounded-md p-1 text-gray-400 hover:bg-gray-800 hover:text-gray-200"
            title="新建仪表板"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </div>

        {/* 新建表单 */}
        {showCreate && (
          <div className="border-b border-gray-700 p-3">
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              placeholder="仪表板名称"
              className="mb-2 w-full rounded-md border border-gray-600 bg-gray-800 px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                disabled={!newTitle.trim()}
                className="flex-1 rounded-md bg-primary-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-700 disabled:opacity-50"
              >
                创建
              </button>
              <button
                onClick={() => { setShowCreate(false); setNewTitle(''); }}
                className="flex-1 rounded-md bg-gray-700 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-600"
              >
                取消
              </button>
            </div>
          </div>
        )}

        {/* 仪表板列表 */}
        <div className="overflow-y-auto p-2">
          {dashboards.length === 0 ? (
            <p className="px-2 py-4 text-center text-xs text-gray-500">
              暂无仪表板
            </p>
          ) : (
            dashboards.map((d) => (
              <div
                key={d.dashboard_id}
                onClick={() => selectDashboard(d.dashboard_id)}
                className={`group mb-1 flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm transition-colors ${
                  activeDashboard?.dashboard_id === d.dashboard_id
                    ? 'bg-primary-600/20 text-primary-300'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-gray-100'
                }`}
              >
                <span className="truncate">{d.title}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(d.dashboard_id);
                  }}
                  className="ml-1 hidden p-0.5 text-gray-500 hover:text-red-400 group-hover:block"
                  title="删除"
                >
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* 右侧仪表板内容 */}
      <main className="flex-1 overflow-y-auto p-6">
        {error && (
          <div className="mb-4 rounded-md border border-red-800 bg-red-900/30 px-4 py-2 text-sm text-red-300">
            {error}
            <button onClick={clearError} className="ml-2 text-red-400 hover:text-red-300">
              ×
            </button>
          </div>
        )}

        {activeDashboard ? (
          <div>
            <div className="mb-6">
              <h1 className="text-xl font-semibold text-gray-100">
                {activeDashboard.title}
              </h1>
              {activeDashboard.description && (
                <p className="mt-1 text-sm text-gray-400">
                  {activeDashboard.description}
                </p>
              )}
            </div>

            {/* 过滤器 */}
            <DashboardFilterBar
              filters={activeDashboard.filters}
            />

            {/* 面板网格 */}
            <div className="mt-4">
              <DashboardLayoutView dashboard={activeDashboard} />
            </div>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <svg
                className="mx-auto mb-3 h-16 w-16 text-gray-700"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={0.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"
                />
              </svg>
              <p className="text-sm text-gray-500">
                {dashboards.length > 0
                  ? '请从左侧选择一个仪表板'
                  : '创建第一个仪表板开始'}
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
