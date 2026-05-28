import { http, HttpResponse } from 'msw';
import type {
  LoginResponse,
  User,
  Session,
  ChatMessage,
} from '@/types/api';

// ==================== Mock 数据 ====================

const MOCK_USER: User = {
  id: 'user-001',
  username: 'admin',
  display_name: '管理员',
  role: 'admin',
  tenant_id: 'tenant-001',
  created_at: '2026-01-01T00:00:00+08:00',
};

const MOCK_SESSIONS: Session[] = [
  {
    id: 'session-001',
    title: '上月营收分析',
    created_at: '2026-05-20T10:00:00+08:00',
    updated_at: '2026-05-27T14:30:00+08:00',
    message_count: 12,
    is_archived: false,
  },
  {
    id: 'session-002',
    title: '用户增长趋势',
    created_at: '2026-05-25T09:00:00+08:00',
    updated_at: '2026-05-27T11:00:00+08:00',
    message_count: 8,
    is_archived: false,
  },
  {
    id: 'session-003',
    title: '产品库存查询',
    created_at: '2026-05-15T14:00:00+08:00',
    updated_at: '2026-05-20T16:00:00+08:00',
    message_count: 5,
    is_archived: true,
  },
];

const MOCK_MESSAGES: Record<string, ChatMessage[]> = {
  'session-001': [
    {
      id: 'msg-001',
      role: 'user',
      content: '上个月的总营收是多少？',
      created_at: '2026-05-27T14:30:00+08:00',
    },
    {
      id: 'msg-002',
      role: 'assistant',
      content:
        '根据查询结果，上个月（2026年4月）的总营收为 1,234,567 元，同比增长 12.5%。',
      sql: 'SELECT SUM(amount) AS total_revenue FROM orders WHERE order_date >= \'2026-04-01\' AND order_date < \'2026-05-01\'',
      sql_dialect: 'mysql',
      sql_explanation:
        '从 orders 表中汇总 2026 年 4 月所有订单的 amount 字段，得到总营收。',
      chart_spec: {
        chartType: 'bar',
        xAxis: 'month',
        yAxis: 'revenue',
      },
      freshness_note: '数据截至 2026-05-25 23:59',
      data_cutoff: '2026-05-25T23:59:00+08:00',
      total_rows: 15000,
      has_more: false,
      created_at: '2026-05-27T14:30:05+08:00',
    },
  ],
  'session-002': [
    {
      id: 'msg-003',
      role: 'user',
      content: '最近 7 天的新增用户数趋势',
      created_at: '2026-05-27T11:00:00+08:00',
    },
    {
      id: 'msg-004',
      role: 'assistant',
      content:
        '最近 7 天新增用户总计 2,340 人，日均新增 334 人。周末注册量明显高于工作日。',
      sql: "SELECT DATE(created_at) AS date, COUNT(*) AS new_users FROM users WHERE created_at >= CURRENT_DATE - INTERVAL 7 DAY GROUP BY DATE(created_at) ORDER BY date",
      sql_dialect: 'mysql',
      sql_explanation:
        '从 users 表中统计最近 7 天每天的新增用户数，按日期分组并排序。',
      chart_spec: {
        chartType: 'line',
        xAxis: 'date',
        yAxis: 'new_users',
      },
      freshness_note: '数据截至 2026-05-27 00:00',
      total_rows: 7,
      has_more: false,
      created_at: '2026-05-27T11:00:05+08:00',
    },
  ],
};

// ==================== Handlers ====================

export const handlers = [
  // -------------------- 认证 --------------------

  http.post('/api/v1/auth/login', async ({ request }) => {
    const body = (await request.json()) as { username: string; password: string };

    // Mock: 任意用户名密码均可登录
    const loginResponse: LoginResponse = {
      data: {
        access_token: 'mock-access-token-' + Date.now(),
        refresh_token: 'mock-refresh-token-' + Date.now(),
        token_type: 'bearer',
        expires_in: 3600,
      },
    };

    return HttpResponse.json(loginResponse);
  }),

  http.post('/api/v1/auth/refresh', () => {
    return HttpResponse.json({
      data: {
        access_token: 'mock-refreshed-token-' + Date.now(),
        refresh_token: 'mock-refresh-token-' + Date.now(),
        token_type: 'bearer',
        expires_in: 3600,
      },
    });
  }),

  http.post('/api/v1/auth/logout', () => {
    return HttpResponse.json({ data: { message: '已登出' } });
  }),

  http.get('/api/v1/auth/me', () => {
    return HttpResponse.json({ data: MOCK_USER });
  }),

  // -------------------- 会话 --------------------

  http.get('/api/v1/sessions', () => {
    return HttpResponse.json({ data: MOCK_SESSIONS });
  }),

  http.post('/api/v1/sessions', async ({ request }) => {
    const body = (await request.json()) as { title?: string } | null;
    const newSession: Session = {
      id: `session-${Date.now()}`,
      title: body?.title ?? '新的对话',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      message_count: 0,
      is_archived: false,
    };
    return HttpResponse.json({ data: newSession });
  }),

  http.get('/api/v1/sessions/:id', ({ params }) => {
    const session = MOCK_SESSIONS.find((s) => s.id === params.id);
    if (!session) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: '会话不存在' } },
        { status: 404 },
      );
    }
    return HttpResponse.json({ data: session });
  }),

  http.patch('/api/v1/sessions/:id', ({ params, request }) => {
    const session = MOCK_SESSIONS.find((s) => s.id === params.id);
    if (!session) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: '会话不存在' } },
        { status: 404 },
      );
    }
    return HttpResponse.json({
      data: {
        ...session,
        updated_at: new Date().toISOString(),
      },
    });
  }),

  http.delete('/api/v1/sessions/:id', () => {
    return HttpResponse.json({ data: { message: '已删除' } });
  }),

  // -------------------- 聊天 --------------------

  http.get('/api/v1/sessions/:id/messages', ({ params }) => {
    const messages = MOCK_MESSAGES[params.id as string] ?? [];
    return HttpResponse.json({ data: messages });
  }),

  http.post('/api/v1/chat/message', async ({ request }) => {
    const body = (await request.json()) as { content: string };
    const userContent = body.content.toLowerCase();

    // 判断是否为数据查询意图（简单关键词匹配）
    const isDataQuery =
      /营收|销售额|订单|用户|增长|趋势|统计|多少|哪个|排行|排名|总计|合计|平均|地区|分类|产品|库存|数量|金额|上月|本周|最近|top/.test(
        userContent,
      );

    let aiResponse: ChatMessage;

    if (isDataQuery) {
      // 数据查询意图：返回完整的 SQL + 数据结果
      aiResponse = {
        id: `msg-ai-${Date.now()}`,
        role: 'assistant',
        content:
          '根据查询结果，上个月各地区的销售额如下：华东地区以 456,789 元位居第一，华南地区紧随其后。总体同比增长 12.5%，表现良好。',
        sql: "SELECT u.region, SUM(o.amount) AS revenue, COUNT(DISTINCT o.id) AS order_count FROM orders o LEFT JOIN users u ON o.user_id = u.id WHERE o.created_at >= '2026-04-01' AND o.created_at < '2026-05-01' GROUP BY u.region ORDER BY revenue DESC LIMIT 100",
        sql_dialect: 'mysql',
        sql_explanation:
          '这个查询统计了上个月（2026年4月）各地区的销售额和订单数。通过 orders 表和 users 表联表查询，按地区分组并按销售额降序排列。',
        chart_spec: {
          chartType: 'bar',
          xAxis: 'region',
          yAxis: 'revenue',
        },
        freshness_note: '数据截至 2026-05-25 23:59',
        data_cutoff: '2026-05-25T23:59:00+08:00',
        total_rows: 8,
        has_more: false,
        data: [
          { region: '华东', revenue: 456789.0, order_count: 1234 },
          { region: '华南', revenue: 389012.5, order_count: 987 },
          { region: '华北', revenue: 312456.8, order_count: 856 },
          { region: '华中', revenue: 234567.3, order_count: 678 },
          { region: '西南', revenue: 178901.2, order_count: 456 },
        ],
        created_at: new Date().toISOString(),
      };
    } else {
      // 闲聊意图：仅返回文本，不返回 SQL
      aiResponse = {
        id: `msg-ai-${Date.now()}`,
        role: 'assistant',
        content: `您好！我是 DataPilot 数据助手，可以帮助您查询和分析业务数据。\n\n您可以尝试问我：\n- "上月各地区销售额是多少？"\n- "最近 7 天的新增用户数趋势"\n- "哪个产品类别的订单量最多？"\n\n请告诉我您想了解什么数据。`,
        created_at: new Date().toISOString(),
      };
    }

    return HttpResponse.json(
      {
        data: aiResponse,
        trace_id: `mock-trace-${Date.now()}`,
      },
      // 模拟 LLM 思考延迟 1-2 秒
      { delay: 1500 },
    );
  }),

  http.post('/api/v1/chat/execute-sql', async ({ request }) => {
    const body = (await request.json()) as { edited_sql: string };

    const aiResponse: ChatMessage = {
      id: `msg-execute-${Date.now()}`,
      role: 'assistant',
      content: `已执行您编辑的 SQL：\n\`\`\`sql\n${body.edited_sql}\n\`\`\`\n\n查询完成，返回 Mock 结果。`,
      sql: body.edited_sql,
      sql_dialect: 'mysql',
      sql_explanation: '用户编辑后重新执行的 SQL。',
      total_rows: 50,
      has_more: false,
      created_at: new Date().toISOString(),
    };

    return HttpResponse.json(
      {
        data: aiResponse,
        trace_id: `mock-trace-${Date.now()}`,
      },
      { delay: 500 },
    );
  }),

  // -------------------- 语义层 API Mock（供 Admin Dashboard 使用） --------------------

  // 数据源
  http.get('/api/v1/data-sources', () => {
    return HttpResponse.json({
      data: [
        { id: 'ds-001', tenant_id: 'tenant-001', name: '生产订单库', type: 'mysql', host: '192.168.1.100', port: 3306, database: 'order_db', username: 'readonly', pool_size: 10, freshness_level: 'hourly', status: 'active', last_health_check: '2026-05-27T14:00:00+08:00', created_at: '2026-01-15T10:00:00+08:00', updated_at: '2026-05-27T14:00:00+08:00' },
        { id: 'ds-002', tenant_id: 'tenant-001', name: '用户行为库', type: 'postgresql', host: '192.168.1.101', port: 5432, database: 'user_analytics', username: 'analyst', pool_size: 20, freshness_level: 'realtime', status: 'active', last_health_check: '2026-05-27T14:05:00+08:00', created_at: '2026-02-01T09:00:00+08:00', updated_at: '2026-05-27T14:05:00+08:00' },
        { id: 'ds-003', tenant_id: 'tenant-001', name: '物流数据仓库', type: 'clickhouse', host: '192.168.1.102', port: 8123, database: 'logistics_dw', username: 'dw_reader', pool_size: 5, freshness_level: 'daily', status: 'active', last_health_check: '2026-05-27T13:50:00+08:00', created_at: '2026-03-10T08:00:00+08:00', updated_at: '2026-05-27T13:50:00+08:00' },
      ],
      pagination: { page: 1, page_size: 20, total: 3, total_pages: 1 },
    });
  }),

  http.get('/api/v1/data-sources/:id', ({ params }) => {
    const dsMap: Record<string, unknown> = {
      'ds-001': { id: 'ds-001', tenant_id: 'tenant-001', name: '生产订单库', type: 'mysql', host: '192.168.1.100', port: 3306, database: 'order_db', username: 'readonly', pool_size: 10, freshness_level: 'hourly', status: 'active' },
      'ds-002': { id: 'ds-002', tenant_id: 'tenant-001', name: '用户行为库', type: 'postgresql', host: '192.168.1.101', port: 5432, database: 'user_analytics', username: 'analyst', pool_size: 20, freshness_level: 'realtime', status: 'active' },
      'ds-003': { id: 'ds-003', tenant_id: 'tenant-001', name: '物流数据仓库', type: 'clickhouse', host: '192.168.1.102', port: 8123, database: 'logistics_dw', username: 'dw_reader', pool_size: 5, freshness_level: 'daily', status: 'active' },
    };
    const ds = dsMap[params.id as string];
    if (!ds) return HttpResponse.json({ error: { code: 'NOT_FOUND', message: '数据源不存在' } }, { status: 404 });
    return HttpResponse.json({ data: ds });
  }),

  http.post('/api/v1/data-sources', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ data: { id: `ds-${Date.now()}`, tenant_id: 'tenant-001', ...body, status: 'active', created_at: new Date().toISOString(), updated_at: new Date().toISOString() } }, { status: 201 });
  }),

  http.put('/api/v1/data-sources/:id', () => {
    return HttpResponse.json({ data: { message: '已更新' } });
  }),

  http.delete('/api/v1/data-sources/:id', () => {
    return HttpResponse.json({ data: { message: '已删除' } });
  }),

  http.post('/api/v1/data-sources/:id/sync', ({ params }) => {
    return HttpResponse.json({ data: { task_id: `task-${Date.now()}`, message: `数据源 ${params.id} 同步已触发` } }, { delay: 500 });
  }),

  http.get('/api/v1/data-sources/:id/health', ({ params }) => {
    const healthMap: Record<string, unknown> = {
      'ds-001': { id: 'h-001', datasource_id: 'ds-001', pool_usage: 45.5, avg_latency_ms: 12, status: 'healthy', last_heartbeat: '2026-05-27T14:30:00+08:00' },
      'ds-002': { id: 'h-002', datasource_id: 'ds-002', pool_usage: 78.2, avg_latency_ms: 85, status: 'degraded', last_heartbeat: '2026-05-27T14:30:00+08:00' },
      'ds-003': { id: 'h-003', datasource_id: 'ds-003', pool_usage: 10.0, avg_latency_ms: 5, status: 'healthy', last_heartbeat: '2026-05-27T14:30:00+08:00' },
    };
    return HttpResponse.json({ data: healthMap[params.id as string] ?? { id: 'h-x', datasource_id: params.id, pool_usage: 0, avg_latency_ms: 0, status: 'down', last_heartbeat: new Date().toISOString() } });
  }),

  http.get('/api/v1/data-sources/:id/tables', ({ params }) => {
    const tablesMap: Record<string, unknown[]> = {
      'ds-001': [
        { id: 'st-001', tenant_id: 'tenant-001', data_source_id: 'ds-001', schema_name: 'order_db', table_name: 'orders', columns: [{ name: 'id', type: 'BIGINT', is_primary_key: true }, { name: 'user_id', type: 'BIGINT', is_primary_key: false }, { name: 'amount', type: 'DECIMAL(12,2)', is_primary_key: false }], row_count: 1500000, description: '订单主表', last_synced_at: '2026-05-27T12:00:00+08:00' },
        { id: 'st-002', tenant_id: 'tenant-001', data_source_id: 'ds-001', schema_name: 'order_db', table_name: 'order_items', columns: [{ name: 'id', type: 'BIGINT', is_primary_key: true }, { name: 'order_id', type: 'BIGINT', is_primary_key: false }], row_count: 4500000, description: '订单明细表', last_synced_at: '2026-05-27T12:00:00+08:00' },
      ],
      'ds-002': [
        { id: 'st-004', tenant_id: 'tenant-001', data_source_id: 'ds-002', schema_name: 'public', table_name: 'users', columns: [{ name: 'id', type: 'BIGINT', is_primary_key: true }, { name: 'region', type: 'VARCHAR(50)', is_primary_key: false }], row_count: 500000, description: '用户表', last_synced_at: '2026-05-27T14:00:00+08:00' },
      ],
    };
    return HttpResponse.json({ data: tablesMap[params.id as string] ?? [] });
  }),

  // 语义模型
  http.get('/api/v1/semantic-models', () => {
    return HttpResponse.json({
      data: [
        { id: 'sm-001', tenant_id: 'tenant-001', name: '电商核心指标', description: '电商核心营收、订单等指标', domain: '电商', data_source_ids: ['ds-001', 'ds-002'], metrics_count: 6, dimensions_count: 4, created_at: '2026-04-01T10:00:00+08:00', updated_at: '2026-05-27T10:00:00+08:00' },
        { id: 'sm-002', tenant_id: 'tenant-001', name: '用户增长分析', description: '用户注册、活跃、留存等指标', domain: '运营', data_source_ids: ['ds-002'], metrics_count: 4, dimensions_count: 3, created_at: '2026-04-15T09:00:00+08:00', updated_at: '2026-05-20T09:00:00+08:00' },
        { id: 'sm-003', tenant_id: 'tenant-001', name: '物流效率监控', description: '物流配送时效、成本等指标', domain: '供应链', data_source_ids: ['ds-003'], metrics_count: 3, dimensions_count: 2, created_at: '2026-05-01T08:00:00+08:00', updated_at: '2026-05-25T08:00:00+08:00' },
      ],
      pagination: { page: 1, page_size: 20, total: 3, total_pages: 1 },
    });
  }),

  http.get('/api/v1/semantic-models/:id', ({ params }) => {
    const modelMap: Record<string, unknown> = {
      'sm-001': { id: 'sm-001', tenant_id: 'tenant-001', name: '电商核心指标', description: '电商核心营收、订单等指标', domain: '电商', data_source_ids: ['ds-001', 'ds-002'] },
      'sm-002': { id: 'sm-002', tenant_id: 'tenant-001', name: '用户增长分析', description: '用户注册、活跃、留存等指标', domain: '运营', data_source_ids: ['ds-002'] },
      'sm-003': { id: 'sm-003', tenant_id: 'tenant-001', name: '物流效率监控', description: '物流配送时效、成本等指标', domain: '供应链', data_source_ids: ['ds-003'] },
    };
    const model = modelMap[params.id as string];
    if (!model) return HttpResponse.json({ error: { code: 'NOT_FOUND', message: '语义模型不存在' } }, { status: 404 });
    return HttpResponse.json({ data: model });
  }),

  http.post('/api/v1/semantic-models', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ data: { id: `sm-${Date.now()}`, tenant_id: 'tenant-001', ...body, created_at: new Date().toISOString(), updated_at: new Date().toISOString() } }, { status: 201 });
  }),

  http.put('/api/v1/semantic-models/:id', () => {
    return HttpResponse.json({ data: { message: '已更新' } });
  }),

  http.delete('/api/v1/semantic-models/:id', () => {
    return HttpResponse.json({ data: { message: '已删除' } });
  }),

  // 指标
  http.get('/api/v1/metrics', ({ request }) => {
    const url = new URL(request.url);
    const modelId = url.searchParams.get('semantic_model_id');
    const allMetrics = [
      { id: 'm-001', tenant_id: 'tenant-001', semantic_model_id: 'sm-001', name: 'GMV', description: '商品交易总额', calculation: 'SUM(amount)', unit: '元', version: 3, tags: ['核心指标', '营收'], created_at: '2026-04-01T10:00:00+08:00', updated_at: '2026-05-01T10:00:00+08:00' },
      { id: 'm-002', tenant_id: 'tenant-001', semantic_model_id: 'sm-001', name: '订单量', description: '订单总数', calculation: 'COUNT(DISTINCT id)', unit: '个', version: 1, tags: ['核心指标'], created_at: '2026-04-01T10:00:00+08:00', updated_at: '2026-04-01T10:00:00+08:00' },
      { id: 'm-003', tenant_id: 'tenant-001', semantic_model_id: 'sm-001', name: '客单价', description: '平均每个订单的金额', calculation: 'SUM(amount) / COUNT(DISTINCT id)', unit: '元', version: 2, tags: ['营收'], created_at: '2026-04-05T10:00:00+08:00', updated_at: '2026-04-15T10:00:00+08:00' },
      { id: 'm-004', tenant_id: 'tenant-001', semantic_model_id: 'sm-001', name: '订单转化率', description: '下单用户占访客比例', calculation: 'COUNT(DISTINCT user_id) / COUNT(DISTINCT visitor_id) * 100', unit: '%', version: 1, tags: ['运营'], created_at: '2026-04-10T10:00:00+08:00', updated_at: '2026-04-10T10:00:00+08:00' },
      { id: 'm-005', tenant_id: 'tenant-001', semantic_model_id: 'sm-002', name: '日活用户数', description: '当日活跃用户', calculation: 'COUNT(DISTINCT id)', unit: '人', version: 1, tags: ['核心指标', '增长'], created_at: '2026-04-15T10:00:00+08:00', updated_at: '2026-04-15T10:00:00+08:00' },
      { id: 'm-006', tenant_id: 'tenant-001', semantic_model_id: 'sm-002', name: '7日留存率', description: '注册后第7天仍活跃比例', calculation: 'COUNT(retained) / COUNT(new) * 100', unit: '%', version: 1, tags: ['增长'], created_at: '2026-05-01T10:00:00+08:00', updated_at: '2026-05-01T10:00:00+08:00' },
    ];
    let filtered = allMetrics;
    if (modelId) filtered = filtered.filter((m) => m.semantic_model_id === modelId);
    return HttpResponse.json({ data: filtered, pagination: { page: 1, page_size: 20, total: filtered.length, total_pages: 1 } });
  }),

  http.post('/api/v1/metrics', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ data: { id: `m-${Date.now()}`, tenant_id: 'tenant-001', version: 1, ...body, created_at: new Date().toISOString(), updated_at: new Date().toISOString() } }, { status: 201 });
  }),

  http.put('/api/v1/metrics/:id', () => {
    return HttpResponse.json({ data: { message: '已更新（新版本）' } });
  }),

  http.delete('/api/v1/metrics/:id', () => {
    return HttpResponse.json({ data: { message: '已删除' } });
  }),

  http.get('/api/v1/metrics/:id/dimensions', () => {
    return HttpResponse.json({ data: ['d-001', 'd-002'] });
  }),

  // 维度
  http.get('/api/v1/dimensions', ({ request }) => {
    const url = new URL(request.url);
    const modelId = url.searchParams.get('semantic_model_id');
    const allDimensions = [
      { id: 'd-001', tenant_id: 'tenant-001', semantic_model_id: 'sm-001', name: '地区', column_name: 'users.region', table_id: 'st-004', synonyms: ['区域', '大区', '省份'], is_virtual: false, created_at: '2026-04-01T10:00:00+08:00', updated_at: '2026-04-01T10:00:00+08:00' },
      { id: 'd-002', tenant_id: 'tenant-001', semantic_model_id: 'sm-001', name: '订单时间', column_name: 'orders.order_date', table_id: 'st-001', synonyms: ['日期', 'date'], is_virtual: false, created_at: '2026-04-01T10:00:00+08:00', updated_at: '2026-04-01T10:00:00+08:00' },
      { id: 'd-003', tenant_id: 'tenant-001', semantic_model_id: 'sm-001', name: '商品类别', column_name: 'products.category', table_id: 'st-003', synonyms: ['品类', '分类'], is_virtual: false, created_at: '2026-04-02T10:00:00+08:00', updated_at: '2026-04-02T10:00:00+08:00' },
      { id: 'd-004', tenant_id: 'tenant-001', semantic_model_id: 'sm-001', name: '订单状态', column_name: 'orders.status', table_id: 'st-001', synonyms: ['状态'], is_virtual: false, created_at: '2026-04-02T10:00:00+08:00', updated_at: '2026-04-02T10:00:00+08:00' },
      { id: 'd-005', tenant_id: 'tenant-001', semantic_model_id: 'sm-002', name: '年龄段', column_name: 'computed', table_id: 'st-004', synonyms: ['年龄', '年龄组'], is_virtual: true, virtual_expression: "CASE WHEN age < 18 THEN '未成年' WHEN age < 30 THEN '青年' WHEN age < 50 THEN '中年' ELSE '老年' END", created_at: '2026-04-15T10:00:00+08:00', updated_at: '2026-04-15T10:00:00+08:00' },
      { id: 'd-006', tenant_id: 'tenant-001', semantic_model_id: 'sm-002', name: '注册渠道', column_name: 'users.channel', table_id: 'st-004', synonyms: ['来源', '渠道'], is_virtual: false, created_at: '2026-04-16T10:00:00+08:00', updated_at: '2026-04-16T10:00:00+08:00' },
    ];
    let filtered = allDimensions;
    if (modelId) filtered = filtered.filter((d) => d.semantic_model_id === modelId);
    return HttpResponse.json({ data: filtered, pagination: { page: 1, page_size: 20, total: filtered.length, total_pages: 1 } });
  }),

  http.post('/api/v1/dimensions', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ data: { id: `d-${Date.now()}`, tenant_id: 'tenant-001', ...body, created_at: new Date().toISOString(), updated_at: new Date().toISOString() } }, { status: 201 });
  }),

  http.put('/api/v1/dimensions/:id', () => {
    return HttpResponse.json({ data: { message: '已更新' } });
  }),

  http.delete('/api/v1/dimensions/:id', () => {
    return HttpResponse.json({ data: { message: '已删除' } });
  }),

  // 搜索
  http.get('/api/v1/search', ({ request }) => {
    const url = new URL(request.url);
    const q = (url.searchParams.get('q') ?? '').toLowerCase();
    if (!q) return HttpResponse.json({ data: [], total: 0 });
    const results = [
      { type: 'metric', id: 'm-001', name: 'GMV', description: '商品交易总额', score: 0.95 },
      { type: 'dimension', id: 'd-001', name: '地区', score: 0.88 },
    ].filter((r) => r.name.toLowerCase().includes(q));
    return HttpResponse.json({ data: results, total: results.length });
  }),
];
