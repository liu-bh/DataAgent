import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import type {
  SemanticModel,
  Metric,
  Dimension,
  SourceTable,
  TableRelationship,
} from '@/types/semantic';
import { semanticModelApi } from '@/api/semanticModels';
import { metricApi } from '@/api/metrics';
import { dimensionApi } from '@/api/dimensions';
import { dataSourceApi } from '@/api/dataSources';
import ReactEChartsCore from 'echarts-for-react';
import * as echarts from 'echarts/core';
import { GraphChart } from 'echarts/charts';
import { TooltipComponent, LegendComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([GraphChart, TooltipComponent, LegendComponent, CanvasRenderer]);

export default function DetailPage() {
  const { id: semanticModelId } = useParams<{ id: string }>() as { id: string };
  const navigate = useNavigate();
  const [model, setModel] = useState<SemanticModel | null>(null);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [dimensions, setDimensions] = useState<Dimension[]>([]);
  const [tables, setTables] = useState<SourceTable[]>([]);
  const [relationships, setRelationships] = useState<TableRelationship[]>([]);
  const [activeTab, setActiveTab] = useState<'info' | 'metrics' | 'dimensions' | 'graph'>('info');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      try {
        const m = await semanticModelApi.get(semanticModelId);
        setModel(m);

        // 并行加载指标和维度
        const [metricsRes, dimensionsRes] = await Promise.all([
          metricApi.list({ semantic_model_id: semanticModelId, page: 1, page_size: 100 }),
          dimensionApi.list({ semantic_model_id: semanticModelId, page: 1, page_size: 100 }),
        ]);
        setMetrics(metricsRes.data);
        setDimensions(dimensionsRes.data);

        // 加载关联数据源的表
        const allTables: SourceTable[] = [];
        for (const dsId of m.data_source_ids) {
          try {
            const dsTables = await dataSourceApi.tables(dsId);
            allTables.push(...dsTables);
          } catch {
            // 忽略单个数据源加载失败
          }
        }
        setTables(allTables);

        // Mock 关系数据（实际应从 API 获取）
        setRelationships([
          {
            id: 'rel-1',
            tenant_id: m.tenant_id,
            semantic_model_id: semanticModelId,
            left_table_id: allTables[0]?.id ?? '',
            right_table_id: allTables[1]?.id ?? '',
            join_type: 'left',
            join_condition: 't1.user_id = t2.id',
            created_at: '',
          },
        ]);
      } catch (err) {
        console.error('加载语义模型详情失败:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [semanticModelId]);

  /** 表关系图配置 */
  const graphOption = {
    tooltip: {},
    legend: {
      data: ['表'],
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        symbol: 'roundRect',
        symbolSize: [80, 40],
        roam: true,
        label: {
          show: true,
          fontSize: 11,
        },
        force: {
          repulsion: 300,
          edgeLength: [100, 200],
        },
        data: tables.map((t) => ({
          name: t.table_name,
          itemStyle: { color: '#3b82f6' },
        })),
        links: relationships
          .filter((r) => r.left_table_id && r.right_table_id)
          .map((r) => {
            const left = tables.find((t) => t.id === r.left_table_id);
            const right = tables.find((t) => t.id === r.right_table_id);
            return {
              source: left?.table_name ?? '',
              target: right?.table_name ?? '',
              label: {
                show: true,
                formatter: r.join_type.toUpperCase(),
                fontSize: 10,
              },
              lineStyle: { curveness: 0.2 },
            };
          }),
      },
    ],
  };

  const tabs = [
    { key: 'info' as const, label: '基本信息' },
    { key: 'metrics' as const, label: `指标 (${metrics.length})` },
    { key: 'dimensions' as const, label: `维度 (${dimensions.length})` },
    { key: 'graph' as const, label: '表关系图' },
  ];

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <span className="text-gray-400">加载中...</span>
      </div>
    );
  }

  if (!model) {
    return (
      <div className="flex h-64 items-center justify-center">
        <span className="text-gray-400">语义模型不存在</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 返回按钮 */}
      <button
        onClick={() => navigate('/admin/semantic-models')}
        className="inline-flex items-center gap-1 text-sm text-gray-500 transition-colors hover:text-gray-700"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
        </svg>
        返回列表
      </button>

      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">{model.name}</h2>
          {model.description && <p className="mt-1 text-sm text-gray-500">{model.description}</p>}
        </div>
        <span className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1 text-sm font-medium text-gray-700">
          {model.domain}
        </span>
      </div>

      {/* Tab 切换 */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex gap-6">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`border-b-2 px-1 pb-3 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab 内容 */}
      <div className="min-h-[400px]">
        {/* 基本信息 */}
        {activeTab === 'info' && (
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <dl className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-sm text-gray-500">名称</dt>
                <dd className="mt-1 text-sm font-medium text-gray-900">{model.name}</dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">业务域</dt>
                <dd className="mt-1 text-sm font-medium text-gray-900">{model.domain}</dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">描述</dt>
                <dd className="mt-1 text-sm font-medium text-gray-900">{model.description ?? '-'}</dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">关联数据源</dt>
                <dd className="mt-1 text-sm font-medium text-gray-900">{model.data_source_ids.length} 个</dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">指标数量</dt>
                <dd className="mt-1 text-sm font-medium text-gray-900">{metrics.length}</dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">维度数量</dt>
                <dd className="mt-1 text-sm font-medium text-gray-900">{dimensions.length}</dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">已同步表</dt>
                <dd className="mt-1 text-sm font-medium text-gray-900">{tables.length} 张</dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">创建时间</dt>
                <dd className="mt-1 text-sm font-medium text-gray-900">
                  {new Date(model.created_at).toLocaleString()}
                </dd>
              </div>
            </dl>
          </div>
        )}

        {/* 指标列表 */}
        {activeTab === 'metrics' && (
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">名称</th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">计算表达式</th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">单位</th>
                  <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-500">版本</th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">标签</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {metrics.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-sm text-gray-400">暂无指标</td>
                  </tr>
                ) : (
                  metrics.map((m) => (
                    <tr key={m.id} className="hover:bg-gray-50">
                      <td className="whitespace-nowrap px-6 py-3 text-sm font-medium text-gray-900">{m.name}</td>
                      <td className="px-6 py-3">
                        <code className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-700">{m.calculation}</code>
                      </td>
                      <td className="whitespace-nowrap px-6 py-3 text-sm text-gray-600">{m.unit ?? '-'}</td>
                      <td className="whitespace-nowrap px-6 py-3 text-center text-sm text-gray-600">v{m.version}</td>
                      <td className="px-6 py-3">
                        <div className="flex flex-wrap gap-1">
                          {m.tags.map((tag) => (
                            <span key={tag} className="rounded-full bg-primary-50 px-2 py-0.5 text-xs text-primary-600">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* 维度列表 */}
        {activeTab === 'dimensions' && (
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">名称</th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">物理列</th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">同义词</th>
                  <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-500">类型</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {dimensions.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-6 py-8 text-center text-sm text-gray-400">暂无维度</td>
                  </tr>
                ) : (
                  dimensions.map((d) => (
                    <tr key={d.id} className="hover:bg-gray-50">
                      <td className="whitespace-nowrap px-6 py-3 text-sm font-medium text-gray-900">{d.name}</td>
                      <td className="px-6 py-3">
                        <code className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-700">{d.column_name}</code>
                      </td>
                      <td className="px-6 py-3">
                        <div className="flex flex-wrap gap-1">
                          {d.synonyms.map((s) => (
                            <span key={s} className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">{s}</span>
                          ))}
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-6 py-3 text-center">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${d.is_virtual ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-700'}`}>
                          {d.is_virtual ? '虚拟' : '物理'}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* 表关系图 */}
        {activeTab === 'graph' && (
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            {tables.length < 2 ? (
              <div className="flex h-64 items-center justify-center text-sm text-gray-400">
                至少需要 2 张表才能展示关系图
              </div>
            ) : (
              <ReactEChartsCore
                echarts={echarts}
                option={graphOption}
                style={{ height: '500px', width: '100%' }}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
