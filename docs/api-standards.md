# API 设计规范

## 1. 通用约定

- **协议**：HTTPS（生产环境强制）
- **基础路径**：`/api/v{version}/{resource}`
- **Content-Type**：`application/json`（默认）
- **字符编码**：UTF-8
- **时间格式**：ISO 8601（`2026-05-27T14:30:00+08:00`）
- **时区**：服务端统一 UTC 存储，返回时带时区信息

## 2. RESTful 接口规范

### 2.1 URL 设计

```
GET    /api/v1/metrics              # 列表
GET    /api/v1/metrics/{id}         # 详情
POST   /api/v1/metrics              # 创建
PUT    /api/v1/metrics/{id}         # 全量更新
PATCH  /api/v1/metrics/{id}         # 部分更新
DELETE /api/v1/metrics/{id}         # 删除
```

**规则：**
- 资源名用**复数名词**（`/metrics`, `/sessions`, `/data-sources`）
- 多级资源不超过 3 层：`/api/v1/metrics/{id}/dimensions`
- 超过 3 层用查询参数替代：`GET /api/v1/metric-values?metric_id=xxx&dimension=xxx`
- URL 中的标识符用 kebab-case（`/data-sources`, `/sql-results`）

### 2.2 查询参数

```
GET /api/v1/metrics?page=1&page_size=20&sort=name:asc&search=营收&tags=核心指标,月度
```

| 参数 | 含义 | 默认值 |
|------|------|--------|
| `page` | 页码 | 1 |
| `page_size` | 每页条数 | 20，最大 100 |
| `sort` | 排序，格式 `field:asc\|desc` | 按创建时间倒序 |
| `search` | 搜索关键词 | - |
| `fields` | 返回字段白名单 | 全部 |

### 2.3 分页响应格式

```json
{
  "data": [
    { "id": "uuid-1", "name": "GMV" },
    { "id": "uuid-2", "name": "客单价" }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 58,
    "total_pages": 3
  }
}
```

### 2.4 批量操作

```json
// POST /api/v1/metrics/batch
{
  "items": [
    { "name": "GMV", "calculation": "SUM(amount)" },
    { "name": "订单量", "calculation": "COUNT(*)" }
  ]
}

// 响应
{
  "results": [
    { "index": 0, "id": "uuid-1", "status": "created" },
    { "index": 1, "status": "error", "message": "calculation 格式错误" }
  ]
}
```

## 3. 统一响应格式

### 3.1 成功响应

```json
{
  "data": { ... },
  "message": "操作成功"
}
```

### 3.2 错误响应

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "指标 xxx 不存在",
    "details": null
  },
  "trace_id": "abc123def456"
}
```

### 3.3 验证错误（422）

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数校验失败",
    "details": [
      { "field": "name", "message": "不能为空" },
      { "field": "calculation", "message": "仅支持 SUM/COUNT/AVG/MIN/MAX" }
    ]
  }
}
```

## 4. 错误码体系

### 4.1 错误码格式

`{领域}_{错误类型}`，大写蛇形命名。

### 4.2 通用错误码

| HTTP 状态码 | 错误码 | 说明 |
|-------------|--------|------|
| 400 | `BAD_REQUEST` | 请求参数错误 |
| 401 | `UNAUTHORIZED` | 未认证 |
| 403 | `PERMISSION_DENIED` | 无权限 |
| 404 | `RESOURCE_NOT_FOUND` | 资源不存在 |
| 409 | `CONFLICT` | 资源冲突（重复创建等） |
| 422 | `VALIDATION_ERROR` | 参数校验失败 |
| 429 | `RATE_LIMITED` | 请求频率超限 |
| 500 | `INTERNAL_ERROR` | 服务内部错误 |
| 502 | `UPSTREAM_ERROR` | 上游服务异常 |
| 503 | `SERVICE_UNAVAILABLE` | 服务不可用 |

### 4.3 业务错误码

| 错误码 | HTTP | 说明 |
|--------|------|------|
| `AUTH_TOKEN_EXPIRED` | 401 | Token 过期 |
| `AUTH_TOKEN_INVALID` | 401 | Token 无效 |
| `SQL_RISK_DETECTED` | 400 | 检测到高风险 SQL |
| `SQL_SYNTAX_ERROR` | 400 | SQL 语法错误 |
| `LLM_ERROR` | 502 | LLM 调用失败 |
| `LLM_TIMEOUT` | 504 | LLM 调用超时 |
| `LLM_RATE_LIMITED` | 429 | LLM 频率限制 |
| `QUERY_EXECUTION_FAILED` | 500 | 查询执行失败 |
| `QUERY_TIMEOUT` | 504 | 查询超时 |
| `DATASOURCE_UNREACHABLE` | 502 | 数据源不可达 |
| `SANDBOX_EXECUTION_FAILED` | 500 | 沙箱执行失败 |
| `EMBEDDING_FAILED` | 500 | 向量化失败 |
| `METRIC_NOT_FOUND` | 404 | 指标不存在 |
| `DIMENSION_NOT_FOUND` | 404 | 维度不存在 |
| `QUOTA_EXCEEDED` | 429 | 用户配额超限 |
| `LICENSE_INVALID` | 403 | 授权文件不存在或签名校验失败 |
| `LICENSE_EXPIRED` | 403 | 产品授权已过期 |
| `LICENSE_IP_DENIED` | 403 | 请求 IP 不在授权白名单内 |
| `LICENSE_FEATURE_DISABLED` | 403 | 请求的功能模块未授权 |
| `LICENSE_USER_LIMIT` | 429 | 并发用户数超过授权上限 |

## 5. API 版本管理

- URL 路径版本：`/api/v1/`, `/api/v2/`
- **v1 保持向后兼容**，破坏性变更升级到 v2
- 废弃接口返回 `Warning` header + 文档说明迁移路径
- 版本切换通过 APISIX 路由配置

## 6. SSE 接口规范

### 6.1 请求

```
POST /api/v1/chat/stream
Content-Type: application/json
Accept: text/event-stream

{
  "session_id": "uuid",
  "content": "上月营收是多少"
}
```

### 6.2 响应格式

```
event: message
data: {"type": "text", "content": "根据"}

event: message
data: {"type": "text", "content": "查询结果"}

event: sql
data: {"type": "sql", "sql": "SELECT SUM(amount) FROM orders WHERE month='2026-04'", "dialect": "mysql"}

event: chart
data: {"type": "chart", "spec": {"chartType": "bar", ...}}

event: done
data: {"type": "done", "message_id": "uuid"}
```

### 6.3 错误

```
event: error
data: {"type": "error", "code": "LLM_TIMEOUT", "message": "模型响应超时"}
```

## 7. WebSocket 接口规范（DAG 进度）

### 7.1 连接

```
WS /api/v1/dag/{execution_id}/progress
Authorization: Bearer <token>
```

### 7.2 消息格式

```json
// 服务端推送
{
  "event": "node_started",
  "data": {
    "node_id": "sql_gen_1",
    "node_type": "sql_generation",
    "status": "running",
    "timestamp": "2026-05-27T14:30:00+08:00"
  }
}

{
  "event": "node_completed",
  "data": {
    "node_id": "sql_gen_1",
    "status": "completed",
    "duration_ms": 1200,
    "result": { "sql": "SELECT ..." }
  }
}
```

## 8. gRPC 接口规范

### 8.1 命名

- Service：`PascalCase` + `Service` 后缀（`PlannerRuntimeService`）
- Method：`PascalCase` 动词开头（`ExecuteDAG`, `ResolveSchema`）
- Message：`PascalCase` + 语义后缀（`ExecuteDAGRequest`, `ResolveSchemaResponse`）
- Field：`snake_case`

### 8.2 Proto 文件组织

```
libs/datapilot-proto/
├── protos/
│   ├── common/
│   │   └── common.proto        # 共享消息类型
│   ├── planner/
│   │   └── planner.proto
│   ├── semantic/
│   │   └── semantic.proto
│   └── query/
│       └── query.proto
└── buf.yaml
```

### 8.3 错误处理

```protobuf
// 使用 gRPC status code + 自定义 error_details
enum ErrorCode {
  EC_UNSPECIFIED = 0;
  EC_NOT_FOUND = 1;
  EC_PERMISSION_DENIED = 2;
  EC_VALIDATION_FAILED = 3;
  EC_SQL_RISK = 4;
  EC_LLM_FAILURE = 5;
  EC_TIMEOUT = 6;
}

message ErrorDetail {
  ErrorCode code = 1;
  string message = 2;
  repeated string details = 3;
}
```

## 9. 接口文档

- FastAPI 自动生成 OpenAPI 3.0 文档：`/docs`（Swagger UI）+ `/redoc`
- gRPC 使用 Buf 生成文档
- API 变更通过 PR 描述中标注 `[API CHANGE]`
- 破坏性变更必须提前一个 Sprint 通知前端
