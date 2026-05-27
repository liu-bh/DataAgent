# Sprint 1 并行开发计划

> 阶段 0 已完成（项目骨架 + 基础设施配置），本文档为阶段 1 的并行开发执行计划。

## 1. 依赖关系

```
阶段 0（已完成 ✅）: Monorepo 骨架 + docker-compose.dev.yml

阶段 1（5 个 Track 并行）:
  Track A ──┐
  Track B ──┤  各 Track 互不干扰，按文件/目录隔离
  Track C ──┤
  Track D ──┤
  Track E ──┘

阶段 2: 集成联调 + 验证
```

## 2. Track 间文件隔离

| 目录 | Track A | Track B | Track C | Track D | Track E |
|------|---------|---------|---------|---------|---------|
| `libs/datapilot-common/` | **写** | - | - | 读 | - |
| `libs/datapilot-license/` | - | **写** | - | 读 | - |
| `libs/datapilot-llm/` | - | - | - | - | - |
| `libs/datapilot-prompt/` | - | - | - | - | - |
| `libs/datapilot-sql/` | - | - | - | - | - |
| `libs/datapilot-proto/` | - | - | - | - | - |
| `web/` | - | - | **写** | - | - |
| `services/auth-service/` | - | - | - | **写** | 读 |
| `services/session-service/` | - | - | - | **写** | 读 |
| `services/agent-service/` | - | - | - | **写** | 读 |
| `services/semantic-service/` | - | - | - | - | - |
| `services/sql-generator-service/` | - | - | - | - | - |
| `services/query-executor-service/` | - | - | - | - | - |
| `services/guardrail-service/` | - | - | - | - | - |
| `infra/` | - | - | - | - | **写** |

**无文件冲突**：每个 Track 只写自己负责的目录。

## 3. 跨 Track 接口约定

### Track D → Track A（datapilot-common）

```python
from datapilot_common.exceptions import AppError, NotFoundError
from datapilot_common.database import get_async_session, Base, TenantBase
from datapilot_common.deps import get_current_user, get_db
from datapilot_common.logging import get_logger
```

### Track D → Track B（datapilot-license）

```python
from datapilot_license.middleware import LicenseMiddleware
```

### Track C → 后端（通过 MSW Mock 完全解耦）

```typescript
// 前端全程使用 MSW Mock，无需等后端
```

## 4. Track A：公共库（datapilot-common）

**负责目录**: `libs/datapilot-common/src/datapilot_common/`
**无外部依赖**，其他 Track 依赖本 Track 的产出。

| # | 任务 | 产出文件 |
|---|------|---------|
| A-1 | 配置加载模块 | `config.py`（Pydantic Settings，从 .env 加载） |
| A-2 | 自定义异常体系 | `exceptions.py`（AppError、NotFoundError、AuthError、LicenseError、QuotaError） |
| A-3 | FastAPI 异常处理器 | `middleware/error_handler.py`（统一错误响应格式） |
| A-4 | structlog 日志配置 | `logging.py`（JSON 格式、trace_id 注入） |
| A-5 | 数据库基类 | `database.py`（AsyncSession 工厂、Base、TenantBase） |
| A-6 | 通用依赖注入 | `deps/auth.py`（get_db、get_current_user、get_tenant_id） |
| A-7 | Prometheus 指标 | `metrics.py`（请求计数、延迟直方图） |
| A-8 | 单元测试 | `tests/unit/test_common/` |

### 参考文档
- `CLAUDE.md` — 编码规范
- `docs/python-standards.md` — 后端规范（异常、多租户、熔断降级）
- `docs/api-standards.md` — 错误响应格式
- `docs/logging-standards.md` — 日志格式

---

## 5. Track B：产品授权（datapilot-license）

**负责目录**: `libs/datapilot-license/src/datapilot_license/`
**完全独立**，仅依赖 Python 标准库 + Pydantic + Redis。

| # | 任务 | 产出文件 |
|---|------|---------|
| B-1 | 授权数据模型 | `license.py`（LicenseInfo Pydantic model） |
| B-2 | HMAC 签名/验签 | `crypto.py`（签名生成、签名验证） |
| B-3 | 授权校验器 | `validator.py`（有效期、IP 白名单 CIDR、功能许可、并发限制） |
| B-4 | FastAPI 中间件 | `middleware.py`（启动校验 + 请求 IP 拦截 + Redis 缓存） |
| B-5 | CLI 生成工具 | `cli.py`（`python -m datapilot_license.cli generate`） |
| B-6 | 示例授权文件 | `LICENSE.example.json` |
| B-7 | 单元测试 | `tests/unit/test_license/` |

### 参考文档
- `DataPilot-开发方案.md` 第 5.17 节 — 产品授权机制
- `docs/guides/adr-records.md` ADR-011 — 授权方案架构决策
- `docs/security-standards.md` 1.2 节 — 产品授权安全规范
- `docs/api-standards.md` — LICENSE_* 错误码

---

## 6. Track C：前端 Chat UI 骨架

**负责目录**: `web/packages/chat-ui/src/`
**完全独立**，全程使用 MSW Mock，无需等后端。

| # | 任务 | 产出文件 |
|---|------|---------|
| C-1 | Vite + React + TS 配置 | `vite.config.ts`、`tsconfig.json`、`tsconfig.node.json` |
| C-2 | Tailwind CSS 配置 | `tailwind.config.ts`、`postcss.config.js`、`src/globals.css` |
| C-3 | zustand Store 骨架 | `stores/authStore.ts`、`stores/chatStore.ts`、`stores/sessionStore.ts` |
| C-4 | API 请求层 | `api/client.ts`（axios 实例、拦截器、Token 刷新） |
| C-5 | TypeScript 类型定义 | `types/api.ts`（ChatMessage、Session、User、CursorPageResult 等） |
| C-6 | MSW Mock 服务 | `mocks/handlers.ts`（Auth、Session、Chat、Semantic 全部 API Mock） |
| C-7 | 路由配置 | `router/index.tsx`（登录页、聊天页、设置页） |
| C-8 | 登录页 | `pages/Login/index.tsx` |
| C-9 | 聊天主界面布局 | `pages/Chat/index.tsx`（侧边栏 + 消息区 + 输入区） |
| C-10 | SSE 流式消息 Hook | `hooks/useSSEStream.ts` |
| C-11 | ESLint 配置 | `eslint.config.js` |
| C-12 | 基础组件 | `components/Button.tsx`、`Input.tsx`、`Loading.tsx`、`MessageBubble.tsx` |
| C-13 | `index.html` + `src/main.tsx` + `src/App.tsx` 入口 |

### 参考文档
- `CLAUDE.md` — 技术栈、前端编码规范
- `docs/typescript-standards.md` — React 组件、Hooks、zustand、SSE 流式
- `docs/guides/api-contract.md` — 全部 API 契约（请求/响应格式）
- `docs/guides/api-contract-workflow.md` — Mock 同步流程

---

## 7. Track D：后端服务骨架 + Auth + Session

**负责目录**: `services/auth-service/`、`services/session-service/`、`services/agent-service/`
**依赖**: Track A（异常、数据库基类）和 Track B（授权中间件）
**解耦方式**: Track A/B 未完成时先使用本地 stub。

| # | 任务 | 产出文件 |
|---|------|---------|
| D-1 | Auth Service: 用户模型 | `auth-service/.../models/user.py`（SQLAlchemy） |
| D-2 | Auth Service: Alembic 配置 | `auth-service/alembic/`（env.py + 首个迁移） |
| D-3 | Auth Service: JWT 工具 | `auth-service/.../services/jwt.py`（签发、验证、刷新） |
| D-4 | Auth Service: 认证 API | `auth-service/.../api/routes/auth.py`（login、refresh、logout、me） |
| D-5 | Auth Service: Pydantic Schema | `auth-service/.../schemas/` |
| D-6 | Auth Service: 单元测试 | `tests/unit/test_auth/` |
| D-7 | Session Service: 会话模型 | `session-service/.../models/session.py` |
| D-8 | Session Service: Alembic 配置 | `session-service/alembic/` |
| D-9 | Session Service: 会话 API | `session-service/.../api/routes/sessions.py`（CRUD + 消息列表） |
| D-10 | Session Service: Pydantic Schema | `session-service/.../schemas/` |
| D-11 | Session Service: 单元测试 | `tests/unit/test_session/` |
| D-12 | Agent Service: FastAPI 入口重构 | `agent-service/.../__init__.py`（挂载 license 中间件 + CORS） |
| D-13 | Agent Service: 聊天路由 | `agent-service/.../api/routes/chat.py`（SSE stub + 同步 stub） |
| D-14 | Agent Service: 会话路由 | `agent-service/.../api/routes/sessions.py`（代理转发） |

### 参考文档
- `CLAUDE.md` — 多租户 tenant_id、编码规范
- `docs/python-standards.md` — FastAPI、Pydantic、SQLAlchemy、JWT
- `docs/guides/api-contract.md` — Auth、Session、Chat API 契约
- `docs/guides/data-model.md` — users、sessions、messages 表结构
- `docs/security-standards.md` — JWT 规范、RBAC 模型
- `docs/guides/database-migration.md` — Alembic 迁移规范

---

## 8. Track E：基础设施配置

**负责目录**: `infra/`、`services/*/Dockerfile`
**依赖**: 阶段 0 的 docker-compose + Track D 的服务端口

| # | 任务 | 产出文件 |
|---|------|---------|
| E-1 | 各服务 Dockerfile | `services/*/Dockerfile`（7 个） |
| E-2 | APISIX 网关配置 | `infra/apisix/config.yaml`（路由、JWT 插件、限流） |
| E-3 | Grafana 数据源和 Dashboard | `infra/grafana/provisioning/` |
| E-4 | Jaeger 配置 | `infra/jaeger/` |
| E-5 | CI/CD deploy workflow | `.github/workflows/deploy.yml` |
| E-6 | 数据库初始化脚本完善 | `infra/scripts/init-db.sql`（建库、建角色、初始 admin 用户） |
| E-7 | docker-compose.override.yml | 本地开发热重载配置 |

### 参考文档
- `docs/guides/environment-variables.md` — 全部服务端口和配置
- `docs/service-communication.md` — Phase1 通信架构
- `docs/logging-standards.md` — Prometheus 指标定义

---

## 9. 验证清单

### 阶段 0 验证（已完成 ✅）

- [x] `docker compose -f docker-compose.dev.yml up -d` 全部启动
- [x] `uv sync` 成功
- [x] 各服务可启动（`/health` 返回 200）
- [x] 目录骨架符合开发方案

### 阶段 1 验证

**Track A:**
- [ ] `from datapilot_common.exceptions import AppError` 正常
- [ ] `from datapilot_common.database import get_async_session` 正常
- [ ] `uv run pytest tests/unit/test_common/ -v` 全部通过

**Track B:**
- [ ] 无 license.json 时服务启动报错
- [ ] 有效 license.json 时服务正常启动
- [ ] IP 不在白名单时返回 403
- [ ] `python -m datapilot_license.cli generate` 可生成授权文件
- [ ] `uv run pytest tests/unit/test_license/ -v` 全部通过

**Track C:**
- [ ] `cd web && pnpm dev` 可访问 http://localhost:5173
- [ ] 登录页可正常渲染
- [ ] 聊天页布局正确
- [ ] MSW Mock API 可用
- [ ] `pnpm lint && pnpm type-check` 通过

**Track D:**
- [ ] `POST /api/v1/auth/login` 返回 JWT
- [ ] `POST /api/v1/auth/refresh` 刷新 Token
- [ ] `GET /api/v1/auth/me` 返回用户信息
- [ ] `GET /api/v1/sessions` 返回会话列表
- [ ] `POST /api/v1/sessions` 创建会话
- [ ] `GET /health` 各服务返回 200
- [ ] `uv run pytest tests/unit/test_auth/ tests/unit/test_session/ -v` 全部通过

**Track E:**
- [ ] 各服务 Dockerfile 可构建
- [ ] APISIX 配置可启动
- [ ] Grafana Dashboard 可访问
- [ ] CI deploy workflow 语法正确
