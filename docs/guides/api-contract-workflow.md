# 前后端协作契约工作流

> 本文档定义前后端基于 API 契约的协作流程，确保接口变更可追踪、Mock 同步、前后端并行开发不脱节。

## 1. 核心原则

```
契约驱动开发（Contract-First）：
  1. 先定义 API 契约（OpenAPI YAML） → 再写代码
  2. 契约即文档 → 自动生成 Mock
  3. 契约变更 → 通知前端 → 同步更新 Mock
  4. 破坏性变更 → 必须升级版本号
```

## 2. 协作流程

### 2.1 新增接口

```
后端开发者                    前端开发者
    │                            │
    ├─ 1. 编写 OpenAPI YAML ────►│
    │                            ├─ 2. 基于 Mock 开始开发
    │                            │
    ├─ 3. 实现后端接口            │
    ├─ 4. 更新 OpenAPI (如有调整)►│
    │                            ├─ 5. 切换到真实 API
    │                            │
    ├─ 6. Code Review             │
    └─ 7. 合并                   └─ 7. 合并
```

### 2.2 修改现有接口

```
后端开发者                    前端开发者
    │                            │
    ├─ 1. 评估变更影响 ──────────►│
    │   (Breaking? 新字段? 类型变更?)
    │                            │
    ├─ 2. 更新 OpenAPI YAML ────►│
    ├─ 3. 更新 MSW Mock ────────►│
    │                            ├─ 4. 调整前端代码
    │                            │
    ├─ 5. 实现后端变更            │
    ├─ 6. Code Review             │
    └─ 7. 合并                   └─ 7. 合并
```

## 3. 契约文件管理

### 3.1 文件位置

```
web/packages/chat-ui/src/api/openapi.yaml   # 前端维护的 OpenAPI 契约
services/*/src/api/openapi.yaml              # 后端各服务自动生成的完整 API
```

### 3.2 契约模板（新增接口）

```yaml
# openapi.yaml 新增接口模板
paths:
  /api/v1/{resource}:
    get:
      operationId: listResources
      summary: 资源列表
      tags: [Resource]
      parameters:
        - name: page
          in: query
          schema:
            type: integer
            default: 1
        - name: page_size
          in: query
          schema:
            type: integer
            default: 20
            maximum: 100
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/Resource'
                  pagination:
                    $ref: '#/components/schemas/Pagination'
        '401':
          $ref: '#/components/responses/Unauthorized'
```

## 4. 变更分级

| 变更级别 | 定义 | 处理方式 | 前端影响 |
|---------|------|---------|---------|
| **兼容变更** | 新增可选字段、新增接口 | 正常合并，通知前端 | 无影响（可选使用新字段） |
| **弃用变更** | 字段标记废弃、接口标记废弃 | `Deprecated: true` + 文档说明 | 前端收到 Warning，下个版本移除 |
| **破坏性变更** | 删除字段、修改类型、修改路径 | **必须升级 API 版本**（v1→v2） | 前端必须同步修改 |

### 4.1 破坏性变更检查清单

```markdown
- [ ] 评估是否可以通过兼容方式实现（新增字段 > 删除字段）
- [ ] 如果必须 Breaking Change，确认升级路径
- [ ] 更新 OpenAPI 版本号
- [ ] 更新前端 Mock 和 TypeScript 类型
- [ ] 在 PR 中明确标注 Breaking Change
- [ ] 通知所有前端开发者
```

## 5. Mock 服务配置

### 5.1 MSW Handler 更新流程

```typescript
// web/packages/chat-ui/src/mocks/handlers.ts

import { http, HttpResponse } from 'msw'

// 新增/修改 Mock Handler
export const handlers = [
  // 新接口 Mock
  http.get('/api/v1/new-resource', () => {
    return HttpResponse.json({
      data: [],
      pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 },
    })
  }),

  // 修改现有接口 Mock（保持与 OpenAPI 同步）
  http.post('/api/v1/chat/message', async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json({
      data: {
        message_id: 'mock-uuid',
        content: 'Mock 响应',
        // 新增字段必须同步
        sql_explanation: '这个 Mock 查询...',
        freshness_note: 'Mock 数据',
        total_rows: 100,
        has_more: false,
      },
      trace_id: 'mock-trace',
    })
  }),
]
```

### 5.2 Mock 数据原则

| 原则 | 说明 |
|------|------|
| 真实性 | Mock 数据结构与真实 API 完全一致 |
| 完整性 | 包含所有字段，包括可选字段 |
| 边界值 | 准备空数据、大数据、错误码等场景 |
| 一致性 | Mock 数据与 OpenAPI Schema 定义一致 |

## 6. TypeScript 类型同步

### 6.1 自动生成（推荐）

```bash
# 从 OpenAPI 自动生成 TypeScript 类型
cd web/packages/chat-ui
pnpm openapi-typescript src/api/openapi.yaml --output src/types/api.d.ts
```

### 6.2 手动维护

如不使用自动生成，接口变更时必须同步更新：

```typescript
// web/packages/chat-ui/src/types/api.ts

// 与 OpenAPI 契约保持同步
export interface ChatMessageResponse {
  message_id: string
  content: string
  sql?: string
  sql_dialect?: string
  sql_explanation?: string    // 新增时必须加
  chart_spec?: ChartSpec
  freshness_note?: string     // 新增时必须加
  data_cutoff?: string
  total_rows: number
  has_more: boolean
  cursor?: string
}
```

## 7. 接口变更通知机制

### 7.1 通知触发条件

- 任何 API 路径的变更（新增/修改/删除）
- 请求/响应字段的变更（新增/删除/类型修改）
- 错误码的变更
- 分页格式的变更

### 7.2 通知方式

| 方式 | 场景 |
|------|------|
| PR 评论 `@mention` 前端负责人 | 所有 API 变更 |
| PR Label `api-change` | 自动标记 |
| Breaking Change 必须在 PR 标题标注 | `[Breaking]` |

## 8. OpenAPI 自动生成

后端 FastAPI 自动生成 OpenAPI JSON：

```python
# services/agent-service/src/datapilot_agent/main.py
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(title="DataPilot Agent Service", version="1.0.0")

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
    # 自定义扩展：添加错误码说明
    openapi_schema["components"]["schemas"]["ErrorResponse"] = {
        "type": "object",
        "properties": {
            "error": {"type": "object", "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
                "details": {"type": "object"},
            }}
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

## 9. 协作效率规范

| 规范 | 说明 |
|------|------|
| 前端不依赖后端启动 | 通过 MSW Mock 完全独立开发 |
| 契约先行 | 接口文档先于实现 |
| 类型同步 | OpenAPI → TypeScript 类型保持一致 |
| 变更通知 | API 变更必须通知前端 |
| 版本控制 | Breaking Change 必须升级版本号 |
| 自动化 | CI 中检查 OpenAPI 与 TypeScript 类型是否同步 |
