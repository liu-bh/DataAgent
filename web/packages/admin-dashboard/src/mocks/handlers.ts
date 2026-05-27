import { http, HttpResponse } from 'msw';
import type {
  DataSource,
  DataSourceHealth,
  SourceTable,
  SemanticModel,
  Metric,
  Dimension,
  SearchResponse,
} from '@/types/semantic';

// ==================== Mock 数据 ====================

const MOCK_DATA_SOURCES: DataSource[] = [
  {
    id: 'ds-001',
    tenant_id: 'tenant-001',
    name: '生产订单库',
    type: 'mysql',
    host: '192.168.1.100',
    port: 3306,
    database: 'order_db',
    username: 'readonly',
    pool_size: 10,
    freshness_level: 'hourly',
    status: 'active',
    last_health_check: '2026-05-27T14:00:00+08:00',
    created_at: '2026-01-15T10:00:00+08:00',
    updated_at: '2026-05-27T14:00:00+08:00',
  },
  {
    id: 'ds-002',
    tenant_id: 'tenant-001',
    name: '用户行为库',
    type: 'postgresql',
    host: '192.168.1.101',
    port: 5432,
    database: 'user_analytics',
    username: 'analyst',
    pool_size: 20,
    freshness_level: 'realtime',
    status: 'active',
    last_health_check: '2026-05-27T14:05:00+08:00',
    created_at: '2026-02-01T09:00:00+08:00',
    updated_at: '2026-05-27T14:05:00+08:00',
  },
  {
    id: 'ds-003',
    tenant_id: 'tenant-001',
    name: '物流数据仓库',
    type: 'clickhouse',
    host: '192.168.1.102',
    port: 8123,
    database: 'logistics_dw',
    username: 'dw_reader',
    pool_size: 5,
    freshness_level: 'daily',
    status: 'active',
    last_health_check: '2026-05-27T13:50:00+08:00',
    created_at: '2026-03-10T08:00:00+08:00',
    updated_at: '2026-05-27T13:50:00+08:00',
  },
];

const MOCK_HEALTH: Record<string, DataSourceHealth> = {
  'ds-001': {
    id: 'health-001',
    datasource_id: 'ds-001',
    pool_usage: 45.5,
    avg_latency_ms: 12,
    status: 'healthy',
    last_heartbeat: '2026-05-27T14:30:00+08:00',
  },
  'ds-002': {
    id: 'health-002',
    datasource_id: 'ds-002',
    pool_usage: 78.2,
    avg_latency_ms: 85,
    status: 'degraded',
    last_heartbeat: '2026-05-27T14:30:00+08:00',
  },
  'ds-003': {
    id: 'health-003',
    datasource_id: 'ds-003',
    pool_usage: 10.0,
    avg_latency_ms: 5,
    status: 'healthy',
    last_heartbeat: '2026-05-27T14:30:00+08:00',
  },
};

const MOCK_TABLES: Record<string, SourceTable[]> = {
  'ds-001': [
    {
      id: 'st-001',
      tenant_id: 'tenant-001',
      data_source_id: 'ds-001',
      schema_name: 'order_db',
      table_name: 'orders',
      columns: [
        { name: 'id', type: 'BIGINT', is_primary_key: true },
        { name: 'user_id', type: 'BIGINT', is_primary_key: false },
        { name: 'amount', type: 'DECIMAL(12,2)', is_primary_key: false },
        { name: 'status', type: 'VARCHAR(20)', is_primary_key: false },
        { name: 'order_date', type: 'DATETIME', is_primary_key: false },
      ],
      row_count: 1500000,
      description: '订单主表',
      last_synced_at: '2026-05-27T12:00:00+08:00',
      created_at: '2026-05-27T12:00:00+08:00',
    },
    {
      id: 'st-002',
      tenant_id: 'tenant-001',
      data_source_id: 'ds-001',
      schema_name: 'order_db',
      table_name: 'order_items',
      columns: [
        { name: 'id', type: 'BIGINT', is_primary_key: true },
        { name: 'order_id', type: 'BIGINT', is_primary_key: false },
        { name: 'product_id', type: 'BIGINT', is_primary_key: false },
        { name: 'quantity', type: 'INT', is_primary_key: false },
        { name: 'unit_price', type: 'DECIMAL(10,2)', is_primary_key: false },
      ],
      row_count: 4500000,
      description: '订单明细表',
      last_synced_at: '2026-05-27T12:00:00+08:00',
      created_at: '2026-05-27T12:00:00+08:00',
    },
    {
      id: 'st-003',
      tenant_id: 'tenant-001',
      data_source_id: 'ds-001',
      schema_name: 'order_db',
      table_name: 'products',
      columns: [
        { name: 'id', type: 'BIGINT', is_primary_key: true },
        { name: 'name', type: 'VARCHAR(200)', is_primary_key: false },
        { name: 'category', type: 'VARCHAR(50)', is_primary_key: false },
        { name: 'price', type: 'DECIMAL(10,2)', is_primary_key: false },
      ],
      row_count: 50000,
      description: '商品表',
      last_synced_at: '2026-05-27T12:00:00+08:00',
      created_at: '2026-05-27T12:00:00+08:00',
    },
  ],
  'ds-002': [
    {
      id: 'st-004',
      tenant_id: 'tenant-001',
      data_source_id: 'ds-002',
      schema_name: 'public',
      table_name: 'users',
      columns: [
        { name: 'id', type: 'BIGINT', is_primary_key: true },
        { name: 'username', type: 'VARCHAR(50)', is_primary_key: false },
        { name: 'region', type: 'VARCHAR(50)', is_primary_key: false },
        { name: 'created_at', type: 'TIMESTAMPTZ', is_primary_key: false },
      ],
      row_count: 500000,
      description: '用户表',
      last_synced_at: '2026-05-27T14:00:00+08:00',
      created_at: '2026-05-27T14:00:00+08:00',
    },
  ],
};

const MOCK_SEMANTIC_MODELS: SemanticModel[] = [
  {
    id: 'sm-001',
    tenant_id: 'tenant-001',
    name: '电商核心指标',
    description: '包含电商业务的核心营收、订单、转化等指标',
    domain: '电商',
    data_source_ids: ['ds-001', 'ds-002'],
    metrics_count: 6,
    dimensions_count: 4,
    tables_count: 4,
    created_at: '2026-04-01T10:00:00+08:00',
    updated_at: '2026-05-27T10:00:00+08:00',
  },
  {
    id: 'sm-002',
    tenant_id: 'tenant-001',
    name: '用户增长分析',
    description: '用户注册、活跃、留存等增长相关指标',
    domain: '运营',
    data_source_ids: ['ds-002'],
    metrics_count: 4,
    dimensions_count: 3,
    tables_count: 1,
    created_at: '2026-04-15T09:00:00+08:00',
    updated_at: '2026-05-20T09:00:00+08:00',
  },
  {
    id: 'sm-003',
    tenant_id: 'tenant-001',
    name: '物流效率监控',
    description: '物流配送时效、成本、履约率等指标',
    domain: '供应链',
    data_source_ids: ['ds-003'],
    metrics_count: 3,
    dimensions_count: 2,
    tables_count: 2,
    created_at: '2026-05-01T08:00:00+08:00',
    updated_at: '2026-05-25T08:00:00+08:00',
  },
];

const MOCK_METRICS: Metric[] = [
  {
    id: 'm-001',
    tenant_id: 'tenant-001',
    semantic_model_id: 'sm-001',
    name: 'GMV',
    description: '商品交易总额（未扣除退款）',
    calculation: 'SUM(order_items.quantity * order_items.unit_price)',
    unit: '元',
    version: 3,
    effective_time: '2026-05-01T00:00:00+08:00',
    tags: ['核心指标', '营收'],
    created_at: '2026-04-01T10:00:00+08:00',
    updated_at: '2026-05-01T10:00:00+08:00',
  },
  {
    id: 'm-002',
    tenant_id: 'tenant-001',
    semantic_model_id: 'sm-001',
    name: '订单量',
    description: '订单总数',
    calculation: 'COUNT(DISTINCT orders.id)',
    unit: '个',
    version: 1,
    effective_time: '2026-04-01T00:00:00+08:00',
    tags: ['核心指标'],
    created_at: '2026-04-01T10:00:00+08:00',
    updated_at: '2026-04-01T10:00:00+08:00',
  },
  {
    id: 'm-003',
    tenant_id: 'tenant-001',
    semantic_model_id: 'sm-001',
    name: '客单价',
    description: '平均每个订单的金额',
    calculation: 'SUM(orders.amount) / COUNT(DISTINCT orders.id)',
    unit: '元',
    version: 2,
    effective_time: '2026-04-15T00:00:00+08:00',
    parent_metric_id: 'm-001',
    tags: ['营收'],
    created_at: '2026-04-05T10:00:00+08:00',
    updated_at: '2026-04-15T10:00:00+08:00',
  },
  {
    id: 'm-004',
    tenant_id: 'tenant-001',
    semantic_model_id: 'sm-001',
    name: '订单转化率',
    description: '下单用户占访客的比例',
    calculation: 'COUNT(DISTINCT orders.user_id) / COUNT(DISTINCT users.id) * 100',
    unit: '%',
    version: 1,
    effective_time: '2026-04-10T00:00:00+08:00',
    tags: ['运营'],
    created_at: '2026-04-10T10:00:00+08:00',
    updated_at: '2026-04-10T10:00:00+08:00',
  },
  {
    id: 'm-005',
    tenant_id: 'tenant-001',
    semantic_model_id: 'sm-002',
    name: '日活用户数',
    description: '当日活跃用户数',
    calculation: 'COUNT(DISTINCT users.id)',
    unit: '人',
    version: 1,
    effective_time: '2026-04-15T00:00:00+08:00',
    tags: ['核心指标', '增长'],
    created_at: '2026-04-15T10:00:00+08:00',
    updated_at: '2026-04-15T10:00:00+08:00',
  },
  {
    id: 'm-006',
    tenant_id: 'tenant-001',
    semantic_model_id: 'sm-002',
    name: '7日留存率',
    description: '注册后第 7 天仍活跃的用户比例',
    calculation: 'COUNT(retained_users) / COUNT(new_users) * 100',
    unit: '%',
    version: 1,
    effective_time: '2026-05-01T00:00:00+08:00',
    tags: ['增长', '留存'],
    created_at: '2026-05-01T10:00:00+08:00',
    updated_at: '2026-05-01T10:00:00+08:00',
  },
];

const MOCK_DIMENSIONS: Dimension[] = [
  {
    id: 'd-001',
    tenant_id: 'tenant-001',
    semantic_model_id: 'sm-001',
    name: '地区',
    column_name: 'users.region',
    table_id: 'st-004',
    synonyms: ['区域', '大区', '省份', 'province'],
    hierarchy: { level: 'province', children: ['city', 'district'] },
    is_virtual: false,
    created_at: '2026-04-01T10:00:00+08:00',
    updated_at: '2026-04-01T10:00:00+08:00',
  },
  {
    id: 'd-002',
    tenant_id: 'tenant-001',
    semantic_model_id: 'sm-001',
    name: '订单时间',
    column_name: 'orders.order_date',
    table_id: 'st-001',
    synonyms: ['下单时间', '日期', 'date'],
    is_virtual: false,
    created_at: '2026-04-01T10:00:00+08:00',
    updated_at: '2026-04-01T10:00:00+08:00',
  },
  {
    id: 'd-003',
    tenant_id: 'tenant-001',
    semantic_model_id: 'sm-001',
    name: '商品类别',
    column_name: 'products.category',
    table_id: 'st-003',
    synonyms: ['品类', '分类', 'category'],
    is_virtual: false,
    created_at: '2026-04-02T10:00:00+08:00',
    updated_at: '2026-04-02T10:00:00+08:00',
  },
  {
    id: 'd-004',
    tenant_id: 'tenant-001',
    semantic_model_id: 'sm-001',
    name: '订单状态',
    column_name: 'orders.status',
    table_id: 'st-001',
    synonyms: ['状态', 'status'],
    is_virtual: false,
    created_at: '2026-04-02T10:00:00+08:00',
    updated_at: '2026-04-02T10:00:00+08:00',
  },
  {
    id: 'd-005',
    tenant_id: 'tenant-001',
    semantic_model_id: 'sm-002',
    name: '年龄段',
    column_name: 'computed',
    table_id: 'st-004',
    synonyms: ['年龄', '年龄组'],
    is_virtual: true,
    virtual_expression: "CASE WHEN age < 18 THEN '未成年' WHEN age < 30 THEN '青年' WHEN age < 50 THEN '中年' ELSE '老年' END",
    created_at: '2026-04-15T10:00:00+08:00',
    updated_at: '2026-04-15T10:00:00+08:00',
  },
  {
    id: 'd-006',
    tenant_id: 'tenant-001',
    semantic_model_id: 'sm-002',
    name: '注册渠道',
    column_name: 'users.channel',
    table_id: 'st-004',
    synonyms: ['来源', '渠道', 'source'],
    is_virtual: false,
    created_at: '2026-04-16T10:00:00+08:00',
    updated_at: '2026-04-16T10:00:00+08:00',
  },
];

// ==================== Handlers ====================

export const handlers = [
  // -------------------- 数据源 CRUD --------------------

  http.get('/api/v1/data-sources', () => {
    return HttpResponse.json({
      data: MOCK_DATA_SOURCES,
      pagination: { page: 1, page_size: 20, total: MOCK_DATA_SOURCES.length, total_pages: 1 },
    });
  }),

  http.get('/api/v1/data-sources/:id', ({ params }) => {
    const ds = MOCK_DATA_SOURCES.find((d) => d.id === params.id);
    if (!ds) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: '数据源不存在' } },
        { status: 404 },
      );
    }
    return HttpResponse.json({ data: ds });
  }),

  http.post('/api/v1/data-sources', async ({ request }) => {
    const body = (await request.json()) as Partial<DataSource>;
    const newDs: DataSource = {
      id: `ds-${Date.now()}`,
      tenant_id: 'tenant-001',
      name: body.name ?? '',
      type: body.type ?? 'mysql',
      host: body.host ?? '',
      port: body.port ?? 3306,
      database: body.database ?? '',
      username: body.username ?? '',
      pool_size: body.pool_size ?? 10,
      freshness_level: body.freshness_level ?? 'daily',
      status: 'active',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    return HttpResponse.json({ data: newDs }, { status: 201 });
  }),

  http.put('/api/v1/data-sources/:id', ({ params }) => {
    const ds = MOCK_DATA_SOURCES.find((d) => d.id === params.id);
    if (!ds) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: '数据源不存在' } },
        { status: 404 },
      );
    }
    return HttpResponse.json({ data: { ...ds, updated_at: new Date().toISOString() } });
  }),

  http.delete('/api/v1/data-sources/:id', () => {
    return HttpResponse.json({ data: { message: '已删除' } });
  }),

  // -------------------- 数据源 Sync / Health / Tables --------------------

  http.post('/api/v1/data-sources/:id/sync', ({ params }) => {
    return HttpResponse.json(
      {
        data: {
          task_id: `task-${Date.now()}`,
          message: `数据源 ${params.id} 的元数据同步任务已触发`,
        },
      },
      { delay: 500 },
    );
  }),

  http.get('/api/v1/data-sources/:id/health', ({ params }) => {
    const health = MOCK_HEALTH[params.id as string];
    if (!health) {
      return HttpResponse.json({
        data: {
          id: `health-${Date.now()}`,
          datasource_id: params.id,
          pool_usage: 0,
          avg_latency_ms: 0,
          status: 'down',
          last_heartbeat: new Date().toISOString(),
        },
      });
    }
    return HttpResponse.json({ data: health });
  }),

  http.get('/api/v1/data-sources/:id/tables', ({ params }) => {
    const tables = MOCK_TABLES[params.id as string] ?? [];
    return HttpResponse.json({ data: tables });
  }),

  // -------------------- 语义模型 CRUD --------------------

  http.get('/api/v1/semantic-models', () => {
    return HttpResponse.json({
      data: MOCK_SEMANTIC_MODELS,
      pagination: { page: 1, page_size: 20, total: MOCK_SEMANTIC_MODELS.length, total_pages: 1 },
    });
  }),

  http.get('/api/v1/semantic-models/:id', ({ params }) => {
    const model = MOCK_SEMANTIC_MODELS.find((m) => m.id === params.id);
    if (!model) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: '语义模型不存在' } },
        { status: 404 },
      );
    }
    return HttpResponse.json({ data: model });
  }),

  http.post('/api/v1/semantic-models', async ({ request }) => {
    const body = (await request.json()) as Partial<SemanticModel>;
    const newModel: SemanticModel = {
      id: `sm-${Date.now()}`,
      tenant_id: 'tenant-001',
      name: body.name ?? '',
      description: body.description,
      domain: body.domain ?? '',
      data_source_ids: body.data_source_ids ?? [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    return HttpResponse.json({ data: newModel }, { status: 201 });
  }),

  http.put('/api/v1/semantic-models/:id', ({ params }) => {
    const model = MOCK_SEMANTIC_MODELS.find((m) => m.id === params.id);
    if (!model) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: '语义模型不存在' } },
        { status: 404 },
      );
    }
    return HttpResponse.json({ data: { ...model, updated_at: new Date().toISOString() } });
  }),

  http.delete('/api/v1/semantic-models/:id', () => {
    return HttpResponse.json({ data: { message: '已删除' } });
  }),

  // -------------------- 指标 CRUD --------------------

  http.get('/api/v1/metrics', ({ request }) => {
    const url = new URL(request.url);
    const modelId = url.searchParams.get('semantic_model_id');
    const search = url.searchParams.get('search');

    let filtered = [...MOCK_METRICS];
    if (modelId) {
      filtered = filtered.filter((m) => m.semantic_model_id === modelId);
    }
    if (search) {
      const q = search.toLowerCase();
      filtered = filtered.filter(
        (m) => m.name.toLowerCase().includes(q) || m.description?.toLowerCase().includes(q),
      );
    }

    return HttpResponse.json({
      data: filtered,
      pagination: { page: 1, page_size: 20, total: filtered.length, total_pages: 1 },
    });
  }),

  http.get('/api/v1/metrics/:id', ({ params }) => {
    const metric = MOCK_METRICS.find((m) => m.id === params.id);
    if (!metric) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: '指标不存在' } },
        { status: 404 },
      );
    }
    return HttpResponse.json({ data: metric });
  }),

  http.post('/api/v1/metrics', async ({ request }) => {
    const body = (await request.json()) as Partial<Metric>;
    const newMetric: Metric = {
      id: `m-${Date.now()}`,
      tenant_id: 'tenant-001',
      semantic_model_id: body.semantic_model_id ?? '',
      name: body.name ?? '',
      description: body.description,
      calculation: body.calculation ?? '',
      unit: body.unit,
      version: 1,
      tags: body.tags ?? [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    return HttpResponse.json({ data: newMetric }, { status: 201 });
  }),

  http.put('/api/v1/metrics/:id', ({ params }) => {
    const metric = MOCK_METRICS.find((m) => m.id === params.id);
    if (!metric) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: '指标不存在' } },
        { status: 404 },
      );
    }
    return HttpResponse.json({
      data: {
        ...metric,
        version: metric.version + 1,
        effective_time: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    });
  }),

  http.delete('/api/v1/metrics/:id', () => {
    return HttpResponse.json({ data: { message: '已删除' } });
  }),

  http.get('/api/v1/metrics/:id/dimensions', ({ params }) => {
    const metric = MOCK_METRICS.find((m) => m.id === params.id);
    if (!metric) {
      return HttpResponse.json({ data: [] });
    }
    const linked = MOCK_DIMENSIONS.filter((d) => d.semantic_model_id === metric.semantic_model_id);
    return HttpResponse.json({ data: linked.map((d) => d.id) });
  }),

  // -------------------- 维度 CRUD --------------------

  http.get('/api/v1/dimensions', ({ request }) => {
    const url = new URL(request.url);
    const modelId = url.searchParams.get('semantic_model_id');
    const search = url.searchParams.get('search');

    let filtered = [...MOCK_DIMENSIONS];
    if (modelId) {
      filtered = filtered.filter((d) => d.semantic_model_id === modelId);
    }
    if (search) {
      const q = search.toLowerCase();
      filtered = filtered.filter(
        (d) => d.name.toLowerCase().includes(q) || d.synonyms.some((s) => s.toLowerCase().includes(q)),
      );
    }

    return HttpResponse.json({
      data: filtered,
      pagination: { page: 1, page_size: 20, total: filtered.length, total_pages: 1 },
    });
  }),

  http.get('/api/v1/dimensions/:id', ({ params }) => {
    const dim = MOCK_DIMENSIONS.find((d) => d.id === params.id);
    if (!dim) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: '维度不存在' } },
        { status: 404 },
      );
    }
    return HttpResponse.json({ data: dim });
  }),

  http.post('/api/v1/dimensions', async ({ request }) => {
    const body = (await request.json()) as Partial<Dimension>;
    const newDim: Dimension = {
      id: `d-${Date.now()}`,
      tenant_id: 'tenant-001',
      semantic_model_id: body.semantic_model_id ?? '',
      name: body.name ?? '',
      column_name: body.column_name ?? '',
      table_id: body.table_id ?? '',
      synonyms: body.synonyms ?? [],
      hierarchy: body.hierarchy,
      is_virtual: body.is_virtual ?? false,
      virtual_expression: body.virtual_expression,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    return HttpResponse.json({ data: newDim }, { status: 201 });
  }),

  http.put('/api/v1/dimensions/:id', ({ params }) => {
    const dim = MOCK_DIMENSIONS.find((d) => d.id === params.id);
    if (!dim) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: '维度不存在' } },
        { status: 404 },
      );
    }
    return HttpResponse.json({ data: { ...dim, updated_at: new Date().toISOString() } });
  }),

  http.delete('/api/v1/dimensions/:id', () => {
    return HttpResponse.json({ data: { message: '已删除' } });
  }),

  // -------------------- 搜索 API --------------------

  http.get('/api/v1/search', ({ request }) => {
    const url = new URL(request.url);
    const q = url.searchParams.get('q') ?? '';

    if (!q) {
      return HttpResponse.json({ data: [], total: 0 });
    }

    const lowerQ = q.toLowerCase();
    const results = [
      ...MOCK_METRICS
        .filter((m) => m.name.toLowerCase().includes(lowerQ) || m.description?.toLowerCase().includes(lowerQ))
        .map((m) => ({
          type: 'metric' as const,
          id: m.id,
          name: m.name,
          description: m.description,
          score: 0.95,
        })),
      ...MOCK_DIMENSIONS
        .filter(
          (d) => d.name.toLowerCase().includes(lowerQ) || d.synonyms.some((s) => s.toLowerCase().includes(lowerQ)),
        )
        .map((d) => ({
          type: 'dimension' as const,
          id: d.id,
          name: d.name,
          description: undefined,
          score: 0.88,
        })),
      ...MOCK_SEMANTIC_MODELS
        .filter((m) => m.name.toLowerCase().includes(lowerQ))
        .map((m) => ({
          type: 'semantic_model' as const,
          id: m.id,
          name: m.name,
          description: m.description,
          score: 0.75,
        })),
    ];

    const searchResponse: SearchResponse = {
      data: results.slice(0, 10),
      total: results.length,
    };

    return HttpResponse.json(searchResponse);
  }),
];
