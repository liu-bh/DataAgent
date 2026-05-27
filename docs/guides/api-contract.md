# API 契约定义（OpenAPI Spec 摘要）

> 完整 OpenAPI JSON 文件位于 `web/packages/chat-ui/src/api/openapi.yaml`，由后端 FastAPI 自动生成。
> 前端开发基于此契约进行 Mock 开发，后端变更需同步更新。

## 1. 通用约定

- 基础路径：`/api/v1`
- Content-Type：`application/json`
- 认证：`Authorization: Bearer <access_token>`
- 时间格式：ISO 8601（`2026-05-27T14:30:00+08:00`）
- 多租户：JWT Token 中携带 `tenant_id`，网关自动注入

## 2. 核心 API 端点

### 2.1 认证 `Auth Service`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/login` | 登录，返回 access_token + refresh_token |
| POST | `/api/v1/auth/refresh` | 刷新 Token |
| POST | `/api/v1/auth/logout` | 登出，吊销 Token |
| GET | `/api/v1/auth/me` | 获取当前用户信息 |

### 2.2 会话 `Session Service`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/sessions` | 会话列表（分页） |
| POST | `/api/v1/sessions` | 创建新会话 |
| GET | `/api/v1/sessions/{id}` | 获取会话详情 |
| PATCH | `/api/v1/sessions/{id}` | 更新会话（标题/归档） |
| DELETE | `/api/v1/sessions/{id}` | 删除会话 |
| GET | `/api/v1/sessions/{id}/messages` | 获取会话消息列表 |

### 2.3 Chat `Agent Service`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/chat/message` | 发送消息（同步，返回完整结果） |
| POST | `/api/v1/chat/stream` | 发送消息（SSE 流式响应） |
| POST | `/api/v1/chat/execute-sql` | 用户编辑 SQL 后重新执行 |

#### POST `/api/v1/chat/message`

```json
// Request
{
  "session_id": "uuid",
  "content": "上月营收是多少"
}

// Response
{
  "data": {
    "message_id": "uuid",
    "content": "根据查询结果，上个月的总营收为 1,234,567 元。",
    "sql": "SELECT SUM(amount) FROM orders WHERE month='2026-04'",
    "sql_dialect": "mysql",
    "sql_explanation": "这个查询从 orders 表中汇总 2026 年 4 月的 amount 字段",
    "chart_spec": { "chartType": "bar", "xAxis": "month", "yAxis": "revenue" },
    "freshness_note": "数据截至 2026-05-25 23:59",
    "data_cutoff": "2026-05-25T23:59:00+08:00",
    "total_rows": 15000,
    "has_more": false
  },
  "trace_id": "abc123"
}
```

#### POST `/api/v1/chat/stream`

```
Accept: text/event-stream
Content-Type: application/json

// Request body 同上

// SSE 事件流
event: status
data: {"type": "thinking"}

event: message
data: {"type": "text", "content": "根据"}

event: message
data: {"type": "text", "content": "查询结果..."}

event: sql
data: {"type": "sql", "sql": "SELECT ...", "dialect": "mysql"}

event: chart
data: {"type": "chart", "spec": {...}}

event: done
data: {"type": "done", "message_id": "uuid"}

event: error
data: {"type": "error", "code": "LLM_TIMEOUT", "message": "模型响应超时"}
```

#### POST `/api/v1/chat/execute-sql`

```json
// Request
{
  "session_id": "uuid",
  "original_sql": "SELECT SUM(amount) FROM orders",
  "edited_sql": "SELECT SUM(amount) FROM orders WHERE month='2026-04'",
  "datasource_id": "uuid"
}

// Response: 与 /chat/message 格式相同
```

### 2.4 查询历史

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/query-history` | 查询历史（分页、按时间倒序） |
| GET | `/api/v1/query-history/favorites` | 收藏的查询 |
| POST | `/api/v1/query-history/{id}/favorite` | 收藏/取消收藏 |
| GET | `/api/v1/query-history/stats` | 查询统计（总数、编辑率等） |

### 2.5 语义模型 `Semantic Service`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/semantic-models` | 语义模型列表 |
| POST | `/api/v1/semantic-models` | 创建语义模型 |
| GET | `/api/v1/semantic-models/{id}` | 语义模型详情 |
| PUT | `/api/v1/semantic-models/{id}` | 更新语义模型 |
| GET | `/api/v1/metrics` | 指标列表（支持搜索） |
| POST | `/api/v1/metrics` | 创建指标 |
| PUT | `/api/v1/metrics/{id}` | 更新指标 |
| GET | `/api/v1/dimensions` | 维度列表 |
| POST | `/api/v1/dimensions` | 创建维度 |
| GET | `/api/v1/metrics/{id}/dimensions` | 指标关联的维度 |

### 2.6 数据源 `Semantic Service`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/data-sources` | 数据源列表 |
| POST | `/api/v1/data-sources` | 注册数据源 |
| GET | `/api/v1/data-sources/{id}` | 数据源详情 |
| PUT | `/api/v1/data-sources/{id}` | 更新数据源 |
| POST | `/api/v1/data-sources/{id}/sync` | 触发元数据同步 |
| GET | `/api/v1/data-sources/{id}/tables` | 获取已同步的表列表 |
| GET | `/api/v1/data-sources/{id}/health` | 数据源健康状态 |

### 2.7 Prompt 管理 `Agent Service`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/prompts` | Prompt 版本列表（按 scene） |
| GET | `/api/v1/prompts/{scene}/active` | 当前激活版本 |
| POST | `/api/v1/prompts` | 创建 Prompt 版本 |
| PUT | `/api/v1/prompts/{id}/activate` | 激活指定版本 |
| GET | `/api/v1/prompts/{id}/ab-results` | A/B 测试结果 |

## 3. 游标分页规范

### 标准分页（offset）

```
GET /api/v1/metrics?page=1&page_size=20

Response:
{
  "data": [...],
  "pagination": { "page": 1, "page_size": 20, "total": 58, "total_pages": 3 }
}
```

### 游标分页（大结果集）

```
GET /api/v1/chat/message?cursor=eyJpYWdl...&limit=50

Response:
{
  "data": { "rows": [...], "total_rows": 15000, "has_more": true },
  "cursor": "eyJwYWdl..."  // 传给下一次请求
}
```

## 4. 错误响应格式

所有错误返回统一格式，详见 `api-standards.md`。

## 5. Mock 服务

前端开发使用 MSW (Mock Service Worker) 进行 API Mock：

```typescript
// web/packages/chat-ui/src/mocks/handlers.ts
import { http, HttpResponse } from 'msw'

export const handlers = [
  http.post('/api/v1/chat/message', async () => {
    return HttpResponse.json({
      data: {
        message_id: 'mock-uuid',
        content: '这是 Mock 响应',
        sql: 'SELECT 1',
        total_rows: 100,
      },
      trace_id: 'mock-trace-id',
    })
  }),
]
```
