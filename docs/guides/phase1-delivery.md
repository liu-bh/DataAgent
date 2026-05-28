# Phase1 交付报告

> DataPilot Phase1 合并部署方案，7 个微服务合并为 3 进程。本文档记录 Phase1 的功能交付清单、架构概览、部署指南和验收标准。

## 功能清单

### 核心链路
- [x] 产品授权控制（datapilot-license，服务启动前置校验）
- [x] 自然语言 → SQL → 执行 → 结果 完整链路
- [x] NL2SQL 核心（意图路由 + 语义解析 + Schema Linking + SQL 生成）
- [x] Self-Correction 自纠错（错误分类 + LLM 纠错 + 多轮修复）

### LLM 接入
- [x] LLM 抽象层（datapilot-llm，统一 Provider 接口）
- [x] 多模型接入（DeepSeek-V3 + Qwen Turbo/Plus/Max）
- [x] 分级策略（按场景自动选择最优模型）
- [x] 熔断保护（CircuitBreaker，连续失败自动熔断 + 半开探测恢复）
- [x] 调用日志（LLMCallLogger，记录 token、延迟、成本）

### 数据源
- [x] 5 种数据源支持（MySQL、PostgreSQL、Doris、StarRocks、ClickHouse）
- [x] SQL 方言适配（datapilot-sql，sqlglot AST 构建 + 方言转换）
- [x] 连接器工厂模式 + 重试机制

### 安全与权限
- [x] RBAC 权限体系（行级权限 AST 注入 WHERE + 列级权限 AST 移除 SELECT 列）
- [x] 数据脱敏（敏感字段自动脱敏）
- [x] SQL 风险检测（DDL/DML 拦截、系统表访问检测、子查询深度限制）
- [x] 查询配额（每租户每小时/每日配额控制，Redis INCR + EXPIRE 滑动窗口）
- [x] 行数限制（SQL 自动添加 LIMIT，防止大结果集）
- [x] 熔断器（租户级请求频率熔断）

### 数据质量
- [x] SQL 验证 + Dry-run + 成本预估（datapilot-sqlgen/validation）
- [x] SQL 后处理（JSON 提取 → AST 解析 → 方言转换 → 添加 LIMIT → SELECT * 替换）
- [x] SQL 自然语言解释（SQLInterpreter，摘要 + 关键信息 + 潜在问题）

### Prompt 管理
- [x] Prompt 版本管理（datapilot-prompt）
- [x] A/B 测试（多版本 Prompt 对比测试）
- [x] Token 预算管理（TokenBudgetManager，Few-shot 裁剪）

### 语义层
- [x] 语义模型管理（datapilot-semantic，表/指标/维度 CRUD）
- [x] 向量搜索 + 混合检索（pgvector IVFFlat + 关键词检索）
- [x] 数据源接入（多数据源元数据管理）

### 缓存
- [x] 分级结果缓存（<1MB 存 Redis，>=1MB 存 MinIO）

### 会话管理
- [x] 会话 CRUD + 消息历史（session-service）
- [x] 用户反馈闭环（thumbs_up/thumbs_down + Few-shot 候选收集）

### 前端
- [x] Chat UI + Admin Dashboard
- [x] 前端图表 + SQL 编辑 + 反馈闭环

## 架构概览

### Phase1 合并部署方案

7 个微服务合并为 3 进程，使用进程内调用替代 gRPC：

```
┌──────────────────────────────────────────────────────────┐
│                   进程 1: API Gateway                     │
│                                                          │
│  agent-service (主入口)                                   │
│  ├── Chat 路由 (/api/v1/chat/*)                          │
│  ├── Session 代理路由 (/api/v1/sessions/*)               │
│  └── 认证中间件 (JWT 校验)                                │
│                                                          │
│  auth-service (认证)                                      │
│  ├── /api/v1/auth/login                                   │
│  ├── /api/v1/auth/refresh                                 │
│  ├── /api/v1/auth/logout                                  │
│  └── /api/v1/auth/me                                      │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                   进程 2: 数据服务                         │
│                                                          │
│  semantic-service (语义模型)                              │
│  ├── 语义模型 CRUD                                        │
│  ├── 数据源管理                                           │
│  └── 向量搜索                                             │
│                                                          │
│  sql-generator-service (NL2SQL)                          │
│  ├── NL2SQL Pipeline (7 步编排)                           │
│  ├── 意图路由 + 解析 + Schema Linking                     │
│  ├── SQL 生成 + 后处理 + 解释                              │
│  └── Self-Correction 自纠错                               │
│                                                          │
│  guardrail-service (安全防护)                             │
│  ├── SQL 风险检测                                         │
│  ├── 行数限制                                             │
│  └── 查询配额                                             │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                   进程 3: 执行服务                         │
│                                                          │
│  query-executor-service (查询执行)                        │
│  ├── 多源查询引擎                                         │
│  ├── 异步任务管理                                         │
│  └── 结果缓存                                             │
│                                                          │
│  session-service (会话管理)                               │
│  ├── 会话生命周期                                         │
│  └── 消息历史                                             │
└──────────────────────────────────────────────────────────┘
```

### NL2SQL Pipeline 流程

```
用户问题
   │
   ▼
┌─────────────┐
│ 意图路由      │ → chitchat / out_of_scope 直接返回文本
│ IntentRouter │
└──────┬──────┘
       │ sql_query
       ▼
┌─────────────┐
│ 意图解析      │ 提取查询类型、过滤条件、时间范围
│ IntentParser │
└──────┬──────┘
       ▼
┌─────────────┐
│ Schema       │ 选择相关表和字段
│ Linking      │ 构建语义上下文
└──────┬──────┘
       ▼
┌─────────────┐
│ Prompt       │ 组装 System Prompt + 语义上下文 + Few-shot
│ 组装          │ Token 预算裁剪
└──────┬──────┘
       ▼
┌─────────────┐
│ LLM 生成     │ JSON mode 输出 {sql, explanation, confidence}
│ (DeepSeek/   │ 熔断保护 + 自动降级
│  Qwen)       │
└──────┬──────┘
       ▼
┌─────────────┐
│ SQL 后处理   │ JSON 提取 → AST 验证 → 方言转换
│              │ → 添加 LIMIT → SELECT * 替换
└──────┬──────┘
       ▼
┌─────────────┐
│ 验证 + 安全   │ Guardrail 风险检测 + 配额检查
│              │ SQL Validation + Dry-run + 成本预估
└──────┬──────┘
       ▼
   返回结果
```

## 部署指南

### 环境要求

| 组件 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 后端运行时 |
| Node.js | 18+ | 前端构建 |
| PostgreSQL | 16 | 主数据库 + pgvector |
| Redis | 7 | 缓存 + 配额管理 |
| MinIO | latest | 大结果集对象存储 |

### 快速启动

```bash
# 1. 启动基础设施
docker compose -f docker-compose.dev.yml up -d

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入必要的 API Key 和密钥

# 3. 产品授权
cp license.json.example license.json
# 或运行: uv run python -m datapilot_license

# 4. 数据库迁移
cd services/semantic-service && uv run alembic upgrade head

# 5. 启动后端服务（3 个进程）
uv run python -m datapilot_agent.main &       # 进程 1
uv run python -m datapilot_sqlgen.main &      # 进程 2 (数据服务)
uv run python -m datapilot_queryexec.main &   # 进程 3 (执行服务)

# 6. 启动前端
cd web && pnpm install && pnpm dev
```

### 环境变量

关键环境变量：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `AGENT_DATABASE_URL` | PostgreSQL 连接串 | - |
| `AGENT_REDIS_URL` | Redis 连接串 | `redis://localhost:6379/0` |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | - |
| `QWEN_API_KEY` | 通义千问 API Key | - |
| `JWT_SECRET_KEY` | JWT 签名密钥（>=32 字符） | - |
| `LICENSE_FILE_PATH` | 授权文件路径 | `./license.json` |
| `MINIO_ENDPOINT` | MinIO 端点 | `localhost:9000` |

完整参考：`docs/guides/environment-variables.md`

## 验收标准

### 功能验收

| 编号 | 验收项 | 验收方法 | 通过标准 |
|------|--------|----------|----------|
| F01 | NL2SQL 完整链路 | 输入自然语言问题，返回 SQL + 结果 | 端到端延迟 < 10s，SQL 准确率 > 80% |
| F02 | 闲聊识别 | 输入问候语 | 返回文本回复，不生成 SQL |
| F03 | 超出范围识别 | 输入非数据问题 | 返回友好提示 |
| F04 | DDL 拦截 | 尝试生成 DROP TABLE | Guardrail 拦截 |
| F05 | DML 拦截 | 尝试生成 INSERT/UPDATE/DELETE | Guardrail 拦截 |
| F06 | 行数限制 | 无 LIMIT 的 SELECT | 自动添加 LIMIT |
| F07 | 配额控制 | 超出配额后请求 | 返回配额不足提示 |
| F08 | 熔断降级 | LLM 服务不可用 | 降级返回占位 SQL |
| F09 | 多租户隔离 | 不同租户的数据查询 | 数据严格隔离 |
| F10 | 会话管理 | 创建/查询/删除会话 | CRUD 正常工作 |
| F11 | 用户反馈 | 提交 thumbs_up/thumbs_down | 反馈记录成功 |
| F12 | 产品授权 | 未授权启动 | 服务拒绝启动 |

### 集成测试覆盖

| 测试文件 | 测试类 | 测试数 |
|----------|--------|--------|
| `test_api_flow.py` | TestAPIFlow | 7 |
| `test_api_flow.py` | TestSQLGenAPIFlow | 5 |
| `test_api_flow.py` | TestAuthAPIFlow | 6 |
| `test_nl2sql_pipeline.py` | TestNL2SQLPipeline | 7 |
| `test_nl2sql_pipeline.py` | TestNL2SQLPipelineDegradation | 5 |
| `test_guardrail_flow.py` | TestGuardrailFlow | 15 |
| `test_guardrail_flow.py` | TestGuardrailAPI | 5 |
| `test_scenarios/test_sales_query.py` | TestSalesScenario | 4 |
| `test_scenarios/test_user_behavior.py` | TestUserBehaviorScenario | 3 |
| `test_scenarios/test_inventory.py` | TestInventoryScenario | 4 |
| `test_degradation.py` | TestDegradation | 10 |
| **合计** | | **71** |

```bash
# 运行全部集成测试
uv run pytest tests/integration/ -v

# 运行特定场景
uv run pytest tests/integration/test_scenarios/ -v
uv run pytest tests/integration/test_degradation.py -v
```

## 已知限制

1. **SSE 流式响应**：当前为 Stub 实现，Sprint 5 完善
2. **SQL 执行**：端到端执行为 Stub，返回空结果，Sprint 4 完善
3. **Few-shot 存储**：用户反馈的 Few-shot 候选仅记录日志，未持久化
4. **Token 黑名单**：登出后的 Token 黑名单使用内存 set，服务重启后失效
5. **向量搜索**：pgvector 使用 IVFFlat 索引，大规模数据需要 HNSW
6. **多租户 Schema**：当前使用共享 Schema + tenant_id 字段，未来可改为 Schema 隔离
7. **监控告警**：Prometheus + Grafana 配置为基本骨架，告警规则待完善

## 后续计划（Phase2）

### Sprint 6：生产就绪
- SSE 流式响应完整实现
- SQL 执行引擎完整对接
- Token 黑名单迁移到 Redis
- 性能压测与优化（P99 < 5s）
- 生产级监控告警配置

### Sprint 7：能力增强
- 多轮对话上下文管理
- 图表推荐引擎（自动选择最佳可视化类型）
- Few-shot 持久化 + 自动入库
- SQL 执行结果缓存策略优化
- 查询结果导出（CSV / Excel）

### Sprint 8：规模扩展
- 水平扩容支持（K8s HPA）
- 分布式会话（Redis Cluster）
- 多租户 Schema 隔离
- gRPC 服务通信（取代进程内调用）
- 审计日志
