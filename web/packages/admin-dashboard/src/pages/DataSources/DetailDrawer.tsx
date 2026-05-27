import { useEffect, useState } from 'react';
import type { DataSource, DataSourceHealth, SourceTable } from '@/types/semantic';
import { dataSourceApi } from '@/api/dataSources';

/** 详情抽屉 Props */
interface DetailDrawerProps {
  dataSourceId: string;
  onClose: () => void;
}

export default function DetailDrawer({ dataSourceId, onClose }: DetailDrawerProps) {
  const [dataSource, setDataSource] = useState<DataSource | null>(null);
  const [health, setHealth] = useState<DataSourceHealth | null>(null);
  const [tables, setTables] = useState<SourceTable[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      try {
        const [ds, h, t] = await Promise.all([
          dataSourceApi.get(dataSourceId),
          dataSourceApi.health(dataSourceId).catch(() => null),
          dataSourceApi.tables(dataSourceId).catch(() => []),
        ]);
        setDataSource(ds);
        setHealth(h);
        setTables(t);
      } catch (err) {
        console.error('加载数据源详情失败:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [dataSourceId]);

  /** 健康状态颜色 */
  const healthColor = health
    ? { healthy: 'text-green-600', degraded: 'text-yellow-600', down: 'text-red-600' }[health.status]
    : 'text-gray-400';

  const healthLabel = health
    ? { healthy: '健康', degraded: '降级', down: '不可用' }[health.status]
    : '未知';

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* 遮罩层 */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* 抽屉内容 */}
      <div className="relative flex h-full w-[480px] flex-col bg-white shadow-xl">
        {/* 头部 */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">数据源详情</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 内容区域 */}
        <div className="flex-1 overflow-auto px-6 py-4">
          {loading ? (
            <div className="flex h-40 items-center justify-center">
              <span className="text-gray-400">加载中...</span>
            </div>
          ) : !dataSource ? (
            <div className="flex h-40 items-center justify-center">
              <span className="text-gray-400">数据源不存在</span>
            </div>
          ) : (
            <div className="space-y-6">
              {/* 基本信息 */}
              <section>
                <h3 className="mb-3 text-sm font-medium text-gray-900">基本信息</h3>
                <dl className="space-y-2 rounded-lg border border-gray-200 bg-gray-50 p-4">
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">名称</dt>
                    <dd className="font-medium text-gray-900">{dataSource.name}</dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">类型</dt>
                    <dd className="font-medium text-gray-900">{dataSource.type.toUpperCase()}</dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">状态</dt>
                    <dd className={`font-medium ${dataSource.status === 'active' ? 'text-green-600' : 'text-gray-400'}`}>
                      {dataSource.status === 'active' ? '已启用' : '已禁用'}
                    </dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">连接地址</dt>
                    <dd className="font-medium text-gray-900">{dataSource.host}:{dataSource.port}</dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">数据库</dt>
                    <dd className="font-medium text-gray-900">{dataSource.database}</dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">用户名</dt>
                    <dd className="font-medium text-gray-900">{dataSource.username}</dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">连接池大小</dt>
                    <dd className="font-medium text-gray-900">{dataSource.pool_size}</dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">数据新鲜度</dt>
                    <dd className="font-medium text-gray-900">{dataSource.freshness_level}</dd>
                  </div>
                </dl>
              </section>

              {/* 健康状态 */}
              {health && (
                <section>
                  <h3 className="mb-3 text-sm font-medium text-gray-900">健康状态</h3>
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                    <div className="grid grid-cols-3 gap-4 text-center">
                      <div>
                        <p className={`text-2xl font-bold ${healthColor}`}>{healthLabel}</p>
                        <p className="mt-1 text-xs text-gray-500">状态</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-gray-900">{health.pool_usage}%</p>
                        <p className="mt-1 text-xs text-gray-500">连接池使用率</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-gray-900">{health.avg_latency_ms}ms</p>
                        <p className="mt-1 text-xs text-gray-500">平均延迟</p>
                      </div>
                    </div>
                  </div>
                </section>
              )}

              {/* 已同步表列表 */}
              <section>
                <h3 className="mb-3 text-sm font-medium text-gray-900">
                  已同步表
                  <span className="ml-2 text-xs font-normal text-gray-400">({tables.length} 张)</span>
                </h3>
                {tables.length === 0 ? (
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-8 text-center text-sm text-gray-400">
                    尚未同步表结构，请点击列表页的"同步"按钮触发同步
                  </div>
                ) : (
                  <div className="space-y-2">
                    {tables.map((table) => (
                      <div
                        key={table.id}
                        className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium text-gray-900">{table.table_name}</p>
                            <p className="text-xs text-gray-400">{table.schema_name}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-xs text-gray-500">{table.row_count.toLocaleString()} 行</p>
                            {table.last_synced_at && (
                              <p className="text-xs text-gray-400">
                                同步于 {new Date(table.last_synced_at).toLocaleString()}
                              </p>
                            )}
                          </div>
                        </div>
                        {table.description && (
                          <p className="mt-1 text-xs text-gray-500">{table.description}</p>
                        )}
                        {/* 列信息 */}
                        <div className="mt-2 flex flex-wrap gap-1">
                          {table.columns.map((col, idx) => (
                            <span
                              key={col.name}
                              className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs ${
                                col.is_primary_key
                                  ? 'bg-yellow-100 text-yellow-700'
                                  : 'bg-gray-100 text-gray-600'
                              }`}
                            >
                              {col.name}
                              <span className="ml-1 text-gray-400">{col.type}</span>
                              {col.is_primary_key && <span className="ml-1 text-yellow-500">PK</span>}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
