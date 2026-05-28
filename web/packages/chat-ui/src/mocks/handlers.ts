import { http, HttpResponse } from 'msw';
import type {
  LoginResponse,
  User,
  Session,
  ChatMessage,
  QueryHistoryItem,
  StarredQuery,
} from '@/types/api';
import type { DAGExecutionStatus } from '@/types/dag';

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

const MOCK_QUERY_HISTORY: QueryHistoryItem[] = [
  {
    id: 'msg-002',
    session_id: 'session-001',
    question: '上个月的总营收是多少？',
    sql: "SELECT SUM(amount) AS total_revenue FROM orders WHERE order_date >= '2026-04-01' AND order_date < '2026-05-01'",
    result_summary: '总营收为 1,234,567 元，同比增长 12.5%',
    created_at: '2026-05-27T14:30:00+08:00',
    is_starred: true,
  },
  {
    id: 'msg-004',
    session_id: 'session-002',
    question: '最近 7 天的新增用户数趋势',
    sql: "SELECT DATE(created_at) AS date, COUNT(*) AS new_users FROM users WHERE created_at >= CURRENT_DATE - INTERVAL 7 DAY GROUP BY DATE(created_at) ORDER BY date",
    result_summary: '最近 7 天新增用户总计 2,340 人，日均新增 334 人',
    created_at: '2026-05-27T11:00:00+08:00',
    is_starred: false,
  },
  {
    id: 'msg-005',
    session_id: 'session-001',
    question: '哪个产品类别的订单量最多？',
    sql: 'SELECT p.category, COUNT(*) AS order_count FROM orders o JOIN products p ON o.product_id = p.id GROUP BY p.category ORDER BY order_count DESC LIMIT 10',
    result_summary: '电子产品类别订单量最多，共计 5,678 单',
    created_at: '2026-05-26T16:20:00+08:00',
    is_starred: false,
  },
  {
    id: 'msg-006',
    session_id: 'session-002',
    question: '本月各地区的销售排名',
    sql: "SELECT u.region, SUM(o.amount) AS revenue FROM orders o LEFT JOIN users u ON o.user_id = u.id WHERE o.created_at >= '2026-05-01' GROUP BY u.region ORDER BY revenue DESC",
    result_summary: '华东地区以 456,789 元位居第一',
    created_at: '2026-05-25T09:30:00+08:00',
    is_starred: true,
  },
];

const MOCK_STARRED_QUERIES: StarredQuery[] = [
  {
    id: 'msg-002',
    question: '上个月的总营收是多少？',
    sql: "SELECT SUM(amount) AS total_revenue FROM orders WHERE order_date >= '2026-04-01' AND order_date < '2026-05-01'",
    starred_at: '2026-05-27T15:00:00+08:00',
    session_id: 'session-001',
  },
  {
    id: 'msg-006',
    question: '本月各地区的销售排名',
    sql: "SELECT u.region, SUM(o.amount) AS revenue FROM orders o LEFT JOIN users u ON o.user_id = u.id WHERE o.created_at >= '2026-05-01' GROUP BY u.region ORDER BY revenue DESC",
    starred_at: '2026-05-26T10:00:00+08:00',
    session_id: 'session-002',
  },
];

// ==================== Handlers ====================

/** 模拟轮询进度的计数器（按 dagId 记录轮询次数） */
const _dagPollCounters: Record<string, number> = {};

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
      // 时间趋势类查询 -> 折线图数据（date 列 + 数值列）
      if (/趋势|每天|每日|周|月/.test(userContent)) {
        aiResponse = {
          id: `msg-ai-${Date.now()}`,
          role: 'assistant',
          content: '最近 7 天的用户注册趋势和营收走势如下，整体呈上升趋势。日均新增 378 人，日均营收约 183,693 元。',
          sql: "SELECT DATE(created_at) AS date, COUNT(*) AS new_users, SUM(amount) AS revenue FROM orders WHERE created_at >= '2026-05-01' GROUP BY DATE(created_at) ORDER BY date",
          sql_dialect: 'mysql',
          sql_explanation: '统计最近 7 天每天的新增用户数和营收总额，按日期分组并排序。',
          chart_spec: { chartType: 'line', xAxis: 'date', yAxis: 'revenue' },
          freshness_note: '数据截至 2026-05-27 23:59',
          data_cutoff: '2026-05-27T23:59:00+08:00',
          total_rows: 7,
          has_more: false,
          data: [
            { date: '2026-05-21', new_users: 280, revenue: 152340.0 },
            { date: '2026-05-22', new_users: 310, revenue: 167890.0 },
            { date: '2026-05-23', new_users: 295, revenue: 148920.0 },
            { date: '2026-05-24', new_users: 420, revenue: 215600.0 },
            { date: '2026-05-25', new_users: 385, revenue: 198400.0 },
            { date: '2026-05-26', new_users: 450, revenue: 234500.0 },
            { date: '2026-05-27', new_users: 510, revenue: 267800.0 },
          ],
          created_at: new Date().toISOString(),
        };
      } else if (/占比|比例|分布|分类/.test(userContent)) {
        // 少维度查询 -> 饼图数据（单维度 + 单数值列）
        aiResponse = {
          id: `msg-ai-${Date.now()}`,
          role: 'assistant',
          content: '各产品类别的订单量分布如下：电子产品占比最高（38.7%），其次是服装鞋帽（27.5%）。',
          sql: "SELECT category, COUNT(*) AS order_count FROM orders WHERE created_at >= '2026-04-01' GROUP BY category ORDER BY order_count DESC",
          sql_dialect: 'mysql',
          sql_explanation: '统计各产品类别的订单数量，按订单量降序排列。',
          chart_spec: { chartType: 'pie', xAxis: 'category', yAxis: 'order_count' },
          freshness_note: '数据截至 2026-05-25 23:59',
          data_cutoff: '2026-05-25T23:59:00+08:00',
          total_rows: 5,
          has_more: false,
          data: [
            { category: '电子产品', order_count: 4520 },
            { category: '服装鞋帽', order_count: 3210 },
            { category: '食品饮料', order_count: 2780 },
            { category: '家居用品', order_count: 1950 },
            { category: '美妆个护', order_count: 1640 },
          ],
          created_at: new Date().toISOString(),
        };
      } else {
        // 默认地区类查询 -> 柱状图数据（维度列 + 多数值列）
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
      }
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

  // -------------------- 端到端执行 / 重执行 / 反馈 --------------------

  http.post('/api/v1/chat/execute', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const question = String(body.question ?? '').toLowerCase();

    // 判断是否为数据查询意图
    const isDataQuery =
      /营收|销售额|订单|用户|增长|趋势|统计|多少|哪个|排行|排名|总计|合计|平均|地区|分类|产品|库存|数量|金额|上月|本周|最近|top/.test(
        question,
      );

    if (isDataQuery) {
      // 时间趋势类查询 -> 折线图数据（date 列 + 数值列）
      if (/趋势|每天|每日|周|月/.test(question)) {
        const trendResponse = {
          sql: "SELECT DATE(created_at) AS date, COUNT(*) AS new_users, SUM(amount) AS revenue FROM orders WHERE created_at >= '2026-05-01' GROUP BY DATE(created_at) ORDER BY date",
          explanation: '最近 7 天的用户注册趋势和营收走势如下，整体呈上升趋势。',
          confidence: 0.94,
          columns: ['date', 'new_users', 'revenue'],
          data: [
            { date: '2026-05-21', new_users: 280, revenue: 152340.0 },
            { date: '2026-05-22', new_users: 310, revenue: 167890.0 },
            { date: '2026-05-23', new_users: 295, revenue: 148920.0 },
            { date: '2026-05-24', new_users: 420, revenue: 215600.0 },
            { date: '2026-05-25', new_users: 385, revenue: 198400.0 },
            { date: '2026-05-26', new_users: 450, revenue: 234500.0 },
            { date: '2026-05-27', new_users: 510, revenue: 267800.0 },
          ],
        };
        return HttpResponse.json(trendResponse, { delay: 1500 });
      }

      // 少维度查询 -> 饼图数据（单维度 + 单数值列，<=8 行）
      if (/占比|比例|分布|分类/.test(question)) {
        const pieResponse = {
          sql: "SELECT category, COUNT(*) AS order_count FROM orders WHERE created_at >= '2026-04-01' GROUP BY category ORDER BY order_count DESC",
          explanation: '各产品类别的订单量分布如下：电子产品占比最高。',
          confidence: 0.91,
          columns: ['category', 'order_count'],
          data: [
            { category: '电子产品', order_count: 4520 },
            { category: '服装鞋帽', order_count: 3210 },
            { category: '食品饮料', order_count: 2780 },
            { category: '家居用品', order_count: 1950 },
            { category: '美妆个护', order_count: 1640 },
          ],
        };
        return HttpResponse.json(pieResponse, { delay: 1500 });
      }

      // 默认地区类查询 -> 柱状图数据（维度列 + 多数值列）
      const executeResponse = {
        sql: "SELECT u.region, SUM(o.amount) AS revenue, COUNT(DISTINCT o.id) AS order_count FROM orders o LEFT JOIN users u ON o.user_id = u.id WHERE o.created_at >= '2026-04-01' AND o.created_at < '2026-05-01' GROUP BY u.region ORDER BY revenue DESC LIMIT 100",
        explanation:
          '根据查询结果，上个月各地区的销售额如下：华东地区以 456,789 元位居第一，华南地区紧随其后。总体同比增长 12.5%，表现良好。',
        confidence: 0.92,
        columns: ['region', 'revenue', 'order_count'],
        data: [
          { region: '华东', revenue: 456789.0, order_count: 1234 },
          { region: '华南', revenue: 389012.5, order_count: 987 },
          { region: '华北', revenue: 312456.8, order_count: 856 },
          { region: '华中', revenue: 234567.3, order_count: 678 },
          { region: '西南', revenue: 178901.2, order_count: 456 },
        ],
      };
      return HttpResponse.json(executeResponse, { delay: 1500 });
    }

    // 非查询意图
    const executeResponse = {
      sql: '',
      explanation:
        '您好！我是 DataPilot 数据助手，可以帮助您查询和分析业务数据。您可以尝试问我关于营收、订单、用户等方面的问题。',
      confidence: 0.95,
      data: [],
      columns: [],
    };
    return HttpResponse.json(executeResponse, { delay: 1000 });
  }),

  http.post('/api/v1/chat/re-execute', async ({ request }) => {
    const body = (await request.json()) as { sql: string };
    const reExecuteResponse = {
      sql: body.sql,
      explanation: `已执行您编辑的 SQL，查询成功。`,
      confidence: 1.0,
      columns: ['region', 'revenue', 'order_count'],
      data: [
        { region: '华东', revenue: 460000.0, order_count: 1250 },
        { region: '华南', revenue: 391000.0, order_count: 990 },
        { region: '华北', revenue: 315000.0, order_count: 860 },
        { region: '华中', revenue: 236000.0, order_count: 680 },
        { region: '西南', revenue: 180000.0, order_count: 460 },
      ],
    };
    return HttpResponse.json(reExecuteResponse, { delay: 800 });
  }),

  http.post('/api/v1/chat/feedback', async () => {
    return HttpResponse.json({ status: 'ok' }, { delay: 200 });
  }),

  // -------------------- 查询历史 & 收藏 --------------------

  /** 获取查询历史 */
  http.get('/api/v1/query/history', ({ request }) => {
    const url = new URL(request.url);
    const sessionId = url.searchParams.get('session_id');

    let items = [...MOCK_QUERY_HISTORY];
    if (sessionId) {
      items = items.filter((h) => h.session_id === sessionId);
    }

    return HttpResponse.json({
      items,
      total: items.length,
      page: 1,
      page_size: 50,
    });
  }),

  /** 清空查询历史 */
  http.delete('/api/v1/query/history', () => {
    return HttpResponse.json({ status: 'ok' }, { delay: 300 });
  }),

  /** 获取收藏查询列表 */
  http.get('/api/v1/query/starred', () => {
    return HttpResponse.json({ data: MOCK_STARRED_QUERIES });
  }),

  /** 收藏查询 */
  http.post('/api/v1/query/star/:message_id', ({ params }) => {
    const messageId = params.message_id;
    // 更新历史中的收藏状态
    const item = MOCK_QUERY_HISTORY.find((h) => h.id === messageId);
    if (item) {
      item.is_starred = true;
    }
    // 如果不在收藏列表中，添加进去
    if (!MOCK_STARRED_QUERIES.find((q) => q.id === messageId) && item) {
      MOCK_STARRED_QUERIES.unshift({
        id: item.id,
        question: item.question,
        sql: item.sql,
        starred_at: new Date().toISOString(),
        session_id: item.session_id,
      });
    }
    return HttpResponse.json({ status: 'ok' }, { delay: 200 });
  }),

  /** 取消收藏查询 */
  http.delete('/api/v1/query/star/:message_id', ({ params }) => {
    const messageId = params.message_id;
    // 更新历史中的收藏状态
    const item = MOCK_QUERY_HISTORY.find((h) => h.id === messageId);
    if (item) {
      item.is_starred = false;
    }
    // 从收藏列表中移除
    const idx = MOCK_STARRED_QUERIES.findIndex((q) => q.id === messageId);
    if (idx !== -1) {
      MOCK_STARRED_QUERIES.splice(idx, 1);
    }
    return HttpResponse.json({ status: 'ok' }, { delay: 200 });
  }),

  // -------------------- DAG 执行进度 --------------------

  /** POST /api/v1/dag/execute -- 返回模拟的 DAG 执行结果 */
  http.post('/api/v1/dag/execute', async () => {
    const dagId = `dag-${Date.now()}`;

    // 初始化轮询计数器
    _dagPollCounters[dagId] = 0;

    const executeResponse = {
      dag_id: dagId,
      status: 'running' as const,
      task_results: {
        intent_route: { status: 'running' as const, execution_time_ms: 0 },
        intent_parse: { status: 'pending' as const, execution_time_ms: 0 },
        schema_link: { status: 'pending' as const, execution_time_ms: 0 },
        prompt_build: { status: 'pending' as const, execution_time_ms: 0 },
        sql_generate: { status: 'pending' as const, execution_time_ms: 0 },
        sql_validate: { status: 'pending' as const, execution_time_ms: 0 },
        sql_explain: { status: 'pending' as const, execution_time_ms: 0 },
      },
      total_time_ms: 0,
    };

    return HttpResponse.json(executeResponse, { delay: 300 });
  }),

  /** GET /api/v1/dag/:dagId/status -- 返回模拟的执行状态（轮询时模拟进度） */
  http.get('/api/v1/dag/:dagId/status', ({ params }) => {
    const dagId = params.dagId as string;
    const count = (_dagPollCounters[dagId] ?? 0) + 1;
    _dagPollCounters[dagId] = count;

    // 根据轮询次数模拟进度推进
    // 第 1-2 次: 意图路由/解析
    // 第 3-4 次: Schema Linking
    // 第 5-7 次: Prompt 组装 + SQL 生成
    // 第 8 次: SQL 验证
    // 第 9 次: SQL 解释
    // 第 10 次: 完成

    const makeNode = (
      nodeId: string,
      label: string,
      taskType: 'sql' | 'llm' | 'search' | 'action' | 'python',
      level: number,
      status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'cancelled',
      deps: string[],
      execTime?: number,
      error?: string,
    ) => ({
      node_id: nodeId,
      label,
      task_type: taskType,
      status,
      execution_time_ms: execTime,
      error,
      level,
      dependencies: deps,
    });

    const buildNodes = () => {
      const nodes = [];

      // Level 0: 意图路由
      if (count >= 1) {
        const intentRouteStatus = count >= 3 ? 'completed' : 'running';
        nodes.push(
          makeNode('intent_route', '意图路由', 'llm', 0, intentRouteStatus, [], count >= 3 ? 420 : undefined),
        );
      } else {
        nodes.push(makeNode('intent_route', '意图路由', 'llm', 0, 'running', []));
      }

      // Level 1: 意图解析
      if (count >= 2) {
        const intentParseStatus = count >= 3 ? 'completed' : 'running';
        nodes.push(
          makeNode('intent_parse', '意图解析', 'llm', 1, intentParseStatus, ['intent_route'], count >= 3 ? 680 : undefined),
        );
      } else {
        nodes.push(makeNode('intent_parse', '意图解析', 'llm', 1, 'pending', ['intent_route']));
      }

      // Level 2: Schema Linking
      if (count >= 3) {
        const schemaLinkStatus = count >= 5 ? 'completed' : 'running';
        nodes.push(
          makeNode('schema_link', 'Schema Linking', 'llm', 2, schemaLinkStatus, ['intent_parse'], count >= 5 ? 1250 : undefined),
        );
      } else {
        nodes.push(makeNode('schema_link', 'Schema Linking', 'llm', 2, 'pending', ['intent_parse']));
      }

      // Level 3: Prompt 组装
      if (count >= 5) {
        const promptBuildStatus = count >= 6 ? 'completed' : 'running';
        nodes.push(
          makeNode('prompt_build', 'Prompt 组装', 'llm', 3, promptBuildStatus, ['schema_link'], count >= 6 ? 320 : undefined),
        );
      } else {
        nodes.push(makeNode('prompt_build', 'Prompt 组装', 'llm', 3, 'pending', ['schema_link']));
      }

      // Level 4: SQL 生成
      if (count >= 6) {
        const sqlGenStatus = count >= 8 ? 'completed' : 'running';
        nodes.push(
          makeNode('sql_generate', 'SQL 生成', 'llm', 4, sqlGenStatus, ['prompt_build'], count >= 8 ? 2340 : undefined),
        );
      } else {
        nodes.push(makeNode('sql_generate', 'SQL 生成', 'llm', 4, 'pending', ['prompt_build']));
      }

      // Level 5: SQL 验证
      if (count >= 8) {
        const sqlValidateStatus = count >= 9 ? 'completed' : 'running';
        nodes.push(
          makeNode('sql_validate', 'SQL 验证', 'sql', 5, sqlValidateStatus, ['sql_generate'], count >= 9 ? 180 : undefined),
        );
      } else {
        nodes.push(makeNode('sql_validate', 'SQL 验证', 'sql', 5, 'pending', ['sql_generate']));
      }

      // Level 6: SQL 解释
      if (count >= 9) {
        const sqlExplainStatus = count >= 10 ? 'completed' : 'running';
        nodes.push(
          makeNode('sql_explain', 'SQL 解释', 'llm', 6, sqlExplainStatus, ['sql_validate'], count >= 10 ? 560 : undefined),
        );
      } else {
        nodes.push(makeNode('sql_explain', 'SQL 解释', 'llm', 6, 'pending', ['sql_validate']));
      }

      return nodes;
    };

    const isCompleted = count >= 10;
    const currentLevel = isCompleted ? -1 : Math.min(count, 6);

    const dagStatus: DAGExecutionStatus = {
      dag_id: dagId,
      status: isCompleted ? 'completed' : 'running',
      nodes: buildNodes(),
      total_time_ms: isCompleted ? 5750 : count * 580,
      current_level: currentLevel,
    };

    return HttpResponse.json(dagStatus, { delay: 200 });
  }),

  /** GET /api/v1/dag/history -- 返回模拟的历史记录 */
  http.get('/api/v1/dag/history', () => {
    const historyItems: DAGExecutionStatus[] = [
      {
        dag_id: 'dag-history-001',
        status: 'completed',
        current_level: -1,
        total_time_ms: 4230,
        nodes: [
          { node_id: 'intent_route', label: '意图路由', task_type: 'llm', status: 'completed', execution_time_ms: 380, level: 0, dependencies: [] },
          { node_id: 'intent_parse', label: '意图解析', task_type: 'llm', status: 'completed', execution_time_ms: 620, level: 1, dependencies: ['intent_route'] },
          { node_id: 'schema_link', label: 'Schema Linking', task_type: 'llm', status: 'completed', execution_time_ms: 1100, level: 2, dependencies: ['intent_parse'] },
          { node_id: 'prompt_build', label: 'Prompt 组装', task_type: 'llm', status: 'completed', execution_time_ms: 290, level: 3, dependencies: ['schema_link'] },
          { node_id: 'sql_generate', label: 'SQL 生成', task_type: 'llm', status: 'completed', execution_time_ms: 1420, level: 4, dependencies: ['prompt_build'] },
          { node_id: 'sql_validate', label: 'SQL 验证', task_type: 'sql', status: 'completed', execution_time_ms: 150, level: 5, dependencies: ['sql_generate'] },
          { node_id: 'sql_explain', label: 'SQL 解释', task_type: 'llm', status: 'completed', execution_time_ms: 270, level: 6, dependencies: ['sql_validate'] },
        ],
      },
      {
        dag_id: 'dag-history-002',
        status: 'failed',
        current_level: 4,
        total_time_ms: 3100,
        error: 'SQL 生成失败：未找到匹配的语义模型',
        nodes: [
          { node_id: 'intent_route', label: '意图路由', task_type: 'llm', status: 'completed', execution_time_ms: 350, level: 0, dependencies: [] },
          { node_id: 'intent_parse', label: '意图解析', task_type: 'llm', status: 'completed', execution_time_ms: 580, level: 1, dependencies: ['intent_route'] },
          { node_id: 'schema_link', label: 'Schema Linking', task_type: 'llm', status: 'completed', execution_time_ms: 950, level: 2, dependencies: ['intent_parse'] },
          { node_id: 'prompt_build', label: 'Prompt 组装', task_type: 'llm', status: 'completed', execution_time_ms: 310, level: 3, dependencies: ['schema_link'] },
          { node_id: 'sql_generate', label: 'SQL 生成', task_type: 'llm', status: 'failed', execution_time_ms: 910, error: '未找到匹配的语义模型', level: 4, dependencies: ['prompt_build'] },
        ],
      },
      {
        dag_id: 'dag-history-003',
        status: 'completed',
        current_level: -1,
        total_time_ms: 5890,
        nodes: [
          { node_id: 'intent_route', label: '意图路由', task_type: 'llm', status: 'completed', execution_time_ms: 400, level: 0, dependencies: [] },
          { node_id: 'intent_parse', label: '意图解析', task_type: 'llm', status: 'completed', execution_time_ms: 700, level: 1, dependencies: ['intent_route'] },
          { node_id: 'schema_link', label: 'Schema Linking', task_type: 'llm', status: 'completed', execution_time_ms: 1300, level: 2, dependencies: ['intent_parse'] },
          { node_id: 'prompt_build', label: 'Prompt 组装', task_type: 'llm', status: 'completed', execution_time_ms: 340, level: 3, dependencies: ['schema_link'] },
          { node_id: 'sql_generate', label: 'SQL 生成', task_type: 'llm', status: 'completed', execution_time_ms: 2100, level: 4, dependencies: ['prompt_build'] },
          { node_id: 'sql_validate', label: 'SQL 验证', task_type: 'sql', status: 'completed', execution_time_ms: 200, level: 5, dependencies: ['sql_generate'] },
          { node_id: 'sql_correct', label: 'SQL 纠错', task_type: 'llm', status: 'completed', execution_time_ms: 650, level: 5, dependencies: ['sql_validate'] },
          { node_id: 'sql_explain', label: 'SQL 解释', task_type: 'llm', status: 'completed', execution_time_ms: 200, level: 6, dependencies: ['sql_validate', 'sql_correct'] },
        ],
      },
    ];

    return HttpResponse.json(historyItems);
  }),

  // -------------------- Python 沙箱执行 --------------------

  /** POST /api/v1/sandbox/execute -- 模拟 Python 代码执行 */
  http.post('*/api/v1/sandbox/execute', async ({ request }) => {
    const body = (await request.json()) as { code: string };
    const code = body.code ?? '';

    // 安全检查：禁止 import os / subprocess 等危险模块
    const forbiddenPattern = /import\s+(os|subprocess|sys\s*\.\s*exit|shutil|signal|ctypes|multiprocessing)/i;
    if (forbiddenPattern.test(code)) {
      return HttpResponse.json({
        result: {
          success: false,
          status: 'security_error',
          return_code: 1,
          stdout: '',
          stderr: 'SecurityError: 不允许导入 os、subprocess 等系统模块',
          execution_time_ms: 5,
          output_bytes: 0,
          cpu_time_ms: 3,
          error: 'SecurityError: 不允许导入 os、subprocess 等系统模块',
          truncated: false,
          memory_used_mb: 12,
          security_issues: [
            { type: 'forbidden_import', message: '不允许导入 os、subprocess 等系统模块', snippet: code.match(forbiddenPattern)?.[0] },
          ],
        },
        trace_id: `mock-trace-${Date.now()}`,
      });
    }

    // 模拟 Python 输出：提取 print 语句的内容
    const simulatePythonOutput = (pythonCode: string): string => {
      const printRegex = /print\s*\((.*)\)/g;
      const outputs: string[] = [];
      let match: RegExpExecArray | null;

      while ((match = printRegex.exec(pythonCode)) !== null) {
        const arg = match[1].trim();
        // 处理简单的 f-string 和字符串字面量
        if (arg.startsWith('f"') || arg.startsWith("f'")) {
          outputs.push(arg.slice(2, -1).replace(/\{.*?\}/g, 'mock'));
        } else if (arg.startsWith('"') || arg.startsWith("'")) {
          outputs.push(arg.slice(1, -1));
        } else {
          outputs.push(`<${arg}>`);
        }
      }

      if (outputs.length === 0) {
        return 'Python 代码执行完成（无输出）';
      }
      return outputs.join('\n');
    };

    const stdout = simulatePythonOutput(code);

    return HttpResponse.json({
      result: {
        success: true,
        status: 'success',
        return_code: 0,
        stdout,
        stderr: '',
        execution_time_ms: 150,
        output_bytes: new TextEncoder().encode(stdout).length,
        cpu_time_ms: 120,
        error: '',
        truncated: false,
        memory_used_mb: 45,
        security_issues: [],
      },
      trace_id: `mock-trace-${Date.now()}`,
    });
  }),

  /** GET /api/v1/sandbox/info -- 沙箱运行信息 */
  http.get('*/api/v1/sandbox/info', () => {
    return HttpResponse.json({
      type: 'local_process',
      available: true,
      python_version: '3.11.9',
      installed_packages: ['pandas==2.2.1', 'numpy==1.26.4', 'scipy==1.13.0', 'scikit-learn==1.5.0', 'matplotlib==3.9.0', 'seaborn==0.13.2'],
      max_concurrency: 5,
      active_executions: 0,
    });
  }),

  /** GET /api/v1/sandbox/health -- 沙箱健康检查 */
  http.get('*/api/v1/sandbox/health', () => {
    return HttpResponse.json({ available: true });
  }),

  // -------------------- RCA 根因分析 --------------------

  /** POST /api/v1/rca/analyze -- 返回模拟的 RCA 分析结果 */
  http.post('/api/v1/rca/analyze', async ({ request }) => {
    const body = (await request.json()) as {
      question?: string;
      metric_name?: string;
    };

    const analysisId = `rca-${Date.now()}`;

    const report = {
      analysis_id: analysisId,
      question: body.question ?? '分析营收异常原因',
      anomaly: {
        metric_name: body.metric_name ?? 'GMV',
        current_value: 892345.0,
        baseline_value: 1234567.0,
        change_percent: -27.7,
        is_anomaly: true,
        anomaly_type: 'drop' as const,
        confidence: 0.92,
        direction: 'down' as const,
      },
      drill_downs: [
        {
          dimension_name: '地区',
          values: [
            { value: '华东', current: 345678.0, baseline: 456789.0, change: -111111.0, change_percent: -24.3, contribution: -111111.0, contribution_percent: -32.7 },
            { value: '华南', current: 234567.0, baseline: 389012.0, change: -154445.0, change_percent: -39.7, contribution: -154445.0, contribution_percent: -45.5 },
            { value: '华北', current: 178901.0, baseline: 212456.0, change: -33555.0, change_percent: -15.8, contribution: -33555.0, contribution_percent: -9.9 },
            { value: '华中', current: 89012.0, baseline: 112345.0, change: -23333.0, change_percent: -20.8, contribution: -23333.0, contribution_percent: -6.9 },
            { value: '西南', current: 44187.0, baseline: 63965.0, change: -19778.0, change_percent: -30.9, contribution: -19778.0, contribution_percent: -5.8 },
          ],
          top_contributors: [
            { value: '华南', current: 234567.0, baseline: 389012.0, change: -154445.0, change_percent: -39.7, contribution: -154445.0, contribution_percent: -45.5 },
            { value: '华东', current: 345678.0, baseline: 456789.0, change: -111111.0, change_percent: -24.3, contribution: -111111.0, contribution_percent: -32.7 },
            { value: '华北', current: 178901.0, baseline: 212456.0, change: -33555.0, change_percent: -15.8, contribution: -33555.0, contribution_percent: -9.9 },
          ],
        },
        {
          dimension_name: '商品类别',
          values: [
            { value: '电子产品', current: 423456.0, baseline: 567890.0, change: -144434.0, change_percent: -25.4, contribution: -144434.0, contribution_percent: -42.6 },
            { value: '服装鞋帽', current: 198765.0, baseline: 345678.0, change: -146913.0, change_percent: -42.5, contribution: -146913.0, contribution_percent: -43.3 },
            { value: '食品饮料', current: 156789.0, baseline: 178901.0, change: -22112.0, change_percent: -12.4, contribution: -22112.0, contribution_percent: -6.5 },
            { value: '家居用品', current: 78012.0, baseline: 89012.0, change: -11000.0, change_percent: -12.4, contribution: -11000.0, contribution_percent: -3.2 },
            { value: '美妆个护', current: 35323.0, baseline: 53086.0, change: -17763.0, change_percent: -33.5, contribution: -17763.0, contribution_percent: -5.2 },
          ],
          top_contributors: [
            { value: '服装鞋帽', current: 198765.0, baseline: 345678.0, change: -146913.0, change_percent: -42.5, contribution: -146913.0, contribution_percent: -43.3 },
            { value: '电子产品', current: 423456.0, baseline: 567890.0, change: -144434.0, change_percent: -25.4, contribution: -144434.0, contribution_percent: -42.6 },
            { value: '食品饮料', current: 156789.0, baseline: 178901.0, change: -22112.0, change_percent: -12.4, contribution: -22112.0, contribution_percent: -6.5 },
          ],
        },
      ],
      attribution: {
        total_change: -342222.0,
        total_change_percent: -27.7,
        dimensions: [
          { dimension: '地区', contribution: -342222.0, contribution_percent: -100.0 },
          { dimension: '商品类别', contribution: -342222.0, contribution_percent: -100.0 },
        ],
        key_drivers: [
          '华南地区销售额大幅下降 (-39.7%)',
          '服装鞋帽品类订单量骤减 (-42.5%)',
          '电子产品客单价下降 (-25.4%)',
        ],
      },
      summary:
        '本期 GMV 较基线下降 27.7%，主要受华南地区和服装鞋帽品类拖累。华南地区销售额同比下降 39.7%，是最大负面贡献因素；服装鞋帽品类订单量骤减 42.5%，与季节性促销结束及竞品活动有关。建议关注华南区域运营策略调整，并评估服装品类营销投入效果。',
      confidence: 0.92,
      execution_time_ms: 3250,
    };

    return HttpResponse.json(
      {
        analysis_id: analysisId,
        report,
        execution_time_ms: 3250,
      },
      { delay: 2000 },
    );
  }),

  /** GET /api/v1/rca/:analysisId/result -- 返回模拟的 RCA 结果 */
  http.get('/api/v1/rca/:analysisId/result', ({ params }) => {
    const analysisId = params.analysisId as string;

    const report = {
      analysis_id: analysisId,
      question: '分析营收异常原因',
      anomaly: {
        metric_name: 'GMV',
        current_value: 892345.0,
        baseline_value: 1234567.0,
        change_percent: -27.7,
        is_anomaly: true,
        anomaly_type: 'drop' as const,
        confidence: 0.92,
        direction: 'down' as const,
      },
      drill_downs: [
        {
          dimension_name: '地区',
          values: [
            { value: '华东', current: 345678.0, baseline: 456789.0, change: -111111.0, change_percent: -24.3, contribution: -111111.0, contribution_percent: -32.7 },
            { value: '华南', current: 234567.0, baseline: 389012.0, change: -154445.0, change_percent: -39.7, contribution: -154445.0, contribution_percent: -45.5 },
          ],
          top_contributors: [
            { value: '华南', current: 234567.0, baseline: 389012.0, change: -154445.0, change_percent: -39.7, contribution: -154445.0, contribution_percent: -45.5 },
          ],
        },
      ],
      attribution: {
        total_change: -342222.0,
        total_change_percent: -27.7,
        dimensions: [
          { dimension: '地区', contribution: -342222.0, contribution_percent: -100.0 },
        ],
        key_drivers: [
          '华南地区销售额大幅下降 (-39.7%)',
          '服装鞋帽品类订单量骤减 (-42.5%)',
        ],
      },
      summary: '本期 GMV 较基线下降 27.7%，主要受华南地区拖累。',
      confidence: 0.92,
      execution_time_ms: 3250,
    };

    return HttpResponse.json(report);
  }),

  /** GET /api/v1/rca/history -- 返回模拟的 RCA 分析历史 */
  http.get('/api/v1/rca/history', () => {
    return HttpResponse.json([
      {
        analysis_id: 'rca-history-001',
        question: '为什么本月营收下降了？',
        metric_name: 'GMV',
        anomaly_detected: true,
        change_percent: -27.7,
      },
      {
        analysis_id: 'rca-history-002',
        question: '用户活跃度是否有异常波动？',
        metric_name: 'DAU',
        anomaly_detected: false,
        change_percent: 2.3,
      },
      {
        analysis_id: 'rca-history-003',
        question: '上周订单量突然增长的原因？',
        metric_name: '订单量',
        anomaly_detected: true,
        change_percent: 45.6,
      },
    ]);
  }),
];
