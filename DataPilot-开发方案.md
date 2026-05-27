# DataPilot 企业级 Semantic Data Agent - 完整开发方案

## Context

用户需要构建自己的企业级 Data Agent 产品（代号 DataPilot），区别于市面上的聊天机器人式产品。基于对阿里云/腾讯云/火山引擎/Spring DataAgent/Datus/K2View/MS Fabric/Teable 等 8+ 竞品的深度分析，确定差异化定位：**Semantic Runtime + Tool Execution + Governance System**，LLM 只是其中一个模块。

**技术选型已确定：**
- 后端：Python
- LLM：纯国产模型（通义千问/DeepSeek）
- 数据源：多种混合（MySQL/PostgreSQL + Doris/StarRocks/ClickHouse + API）
- 团队：8+人，6.5个月+

---

## 一、系统整体架构

### 1.1 微服务划分

#### Phase1：合并部署（7 个服务）

为降低 7 人团队 6 个月内的运维和联调成本，Phase1 将部分紧耦合服务合并部署：

| 服务 | 合并说明 | Phase2 拆分 |
|------|---------|------------|
| **Agent Service** | Agent Gateway + Chat Service | 拆分为独立服务 |
| **Semantic Service** | Semantic Layer + Metadata Service | 拆分为独立服务 |
| **SQL Generator Service** | NL2SQL 核心（独立） | - |
| **Query Executor Service** | 多源连接/执行（独立） | - |
| **Guardrail Service** | SQL 风险/成本/RBAC/权限（独立） | - |
| **Auth Service** | JWT 认证/RBAC（独立） | - |
| **Session Service** | 会话/上下文/记忆（独立） | - |

Phase2 新增：Planner Runtime、Tool Registry、Python Sandbox Manager

```
                    ┌───────────────────────────────────────┐
                    │          K8s Ingress (Nginx)          │
                    └────────────┬────────────┬─────────────┘
                                 │            │
                    ┌────────────▼──┐  ┌──────▼────────────┐
                    │  Web Chat UI  │  │  Admin Dashboard  │
                    │ (React+Vite)  │  │  (React+Vite)     │
                    └────────────┬──┘  └──────┬────────────┘
                                 │            │
                    ┌────────────▼────────────▼─────────────┐
                    │       API Gateway (APISIX)            │
                    │  JWT认证 / 限流 / 路由 / SSE代理       │
                    └───┬────────┬────────┬────────┬────────┘
                        │        │        │        │
           ┌────────────▼──┐  ┌──▼──────────▼────┐  ┌──────▼───────┐
           │ Agent Service │  │ Session Service  │  │ Auth Service │
           │ (Agent+Chat   │  │ (上下文/记忆)    │  │ (JWT/RBAC)   │
           │  +SSE/WS)     │  └─────────────────┘  └──────────────┘
           └──────┬────────┘
                  │
         ┌────────▼──────────────────────────────────────────┐
         │              Message Bus (RocketMQ)                │
         └───┬──────────────┬──────────────┬────────────────┘
             │              │              │
    ┌────────▼──────┐ ┌─────▼───────┐ ┌───▼────────────────┐
    │ SQL Generator │ │ Semantic    │ │ Query Executor     │
    │ (AST构建/     │ │ Service     │ │ (多源连接/执行)    │
    │  NL2SQL核心)  │ │ (语义+元数据)│ │                    │
    └───────┬───────┘ └─────┬───────┘ └───┬────────────────┘
            │               │              │
    ┌───────▼───────┐       │              │
    │ Guardrail     │◄──────┘              │
    │ (风险/成本/   │◄─────────────────────┘
    │  RBAC/权限)   │
    └───────────────┘
            │
    ┌───────▼──────────────────────────────────────┐
    │  MySQL | PostgreSQL | Doris | StarRocks | API │
    └──────────────────────────────────────────────┘
```

#### Phase2：完整拆分（10 个服务 + 基础设施）

Phase2 在 Phase1 验证稳定后拆分服务，并新增 Planner Runtime、Tool Registry、Python Sandbox Manager，形成完整微服务架构。

```
Phase2 完整架构（10 个服务 + 基础设施）：

                    ┌───────────────────────────────────────┐
                    │          K8s Ingress (Nginx)          │
                    └────────────┬────────────┬─────────────┘
                                 │            │
                    ┌────────────▼──┐  ┌──────▼────────────┐
                    │  Web Chat UI  │  │  Admin Dashboard  │
                    │ (React+Vite)  │  │  (React+Vite)     │
                    └────────────┬──┘  └──────┬────────────┘
                                 │            │
                    ┌────────────▼────────────▼─────────────┐
                    │       API Gateway (APISIX)            │
                    │  JWT认证 / 限流 / 路由 / SSE代理       │
                    └───┬────────┬────────┬────────┬────────┘
                        │        │        │        │
           ┌────────────▼┐  ┌───▼────┐  │  ┌────▼───────────┐
           │ Agent       │  │ Chat   │  │  │ Session Svc   │
           │ Gateway     │  │ Service│  │  │ (上下文/记忆)  │
           └──────┬───────┘  └────────┘  │  └───────────────┘
                  │                     │
         ┌────────▼─────────────────────▼─────────────────────┐
         │              Message Bus (RocketMQ)                 │
         └───┬──────────────┬──────────────┬──────────────────┘
             │              │              │
    ┌────────▼──────┐ ┌─────▼───────┐ ┌───▼────────────────┐
    │ Planner       │ │ Semantic    │ │ Tool Registry      │
    │ Runtime       │ │ Service     │ │ Service            │
    │ (DAG编排)     │ │ (语义层)     │ │ (工具注册/执行)    │
    └───────┬───────┘ └─────┬───────┘ └───┬────────────────┘
            │               │              │
    ┌───────▼───────┐ ┌─────▼────────┐ ┌──▼─────────────────┐
    │ SQL Generator │ │ Metadata Svc │ │ Python Sandbox Mgr  │
    │ (AST构建/验证)│ │ (同步/向量)   │ │ (容器编排)         │
    └───────┬───────┘ └──────────────┘ └────────────────────┘
            │
    ┌───────▼────────────┐
    │ Query Executor     │
    │ (多源连接/执行)    │
    └───────┬────────────┘
            │
    ┌───────▼──────────────────────────────────────┐
    │  MySQL | PostgreSQL | Doris | StarRocks | API │
    └──────────────────────────────────────────────┘
```

### 1.2 通信方式

#### Phase1 通信（合并部署，跨进程调用为主）

| 类型 | 方式 | 场景 |
|------|------|------|
| 进程内调用 | Python 函数 | Agent Service 内部（Agent↔Chat）、Semantic 内部（语义↔元数据） |
| 跨进程同步 | gRPC | Agent → SQL Generator, Agent → Semantic, Agent → Query Executor |
| 异步事件 | RocketMQ | query.completed, embedding.generated, audit.event |
| 前端推送 | SSE | Chat 消息流式输出 |

#### Phase2 通信（完整拆分后）

| 类型 | 方式 | 场景 |
|------|------|------|
| 同步调用 | gRPC | 所有服务间调用（Agent→Planner→Semantic→SQL Gen→Query Executor） |
| 异步事件 | RocketMQ | query.submitted, task.completed, sandbox.result_ready |
| 前端推送 | SSE | Chat 消息流式输出 |
| 前端推送 | WebSocket | DAG 执行进度实时推送 |

---

## 二、详细技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| Web 框架 | **FastAPI** | 异步支持好、自动 OpenAPI 文档、SSE 原生 |
| gRPC 框架 | grpcio + grpclib | 微服务高性能通信 |
| ORM | SQLAlchemy 2.0 (async) | 成熟稳定，多方言支持 |
| 数据验证 | Pydantic v2 | 与 FastAPI 原生集成 |
| SQL AST | **sqlglot** | 原生支持 MySQL/PG/Doris/StarRocks/ClickHouse 方言转换 |
| 关系库 | PostgreSQL 16 + **pgvector** | 元数据 + 语义向量一体化 |
| 向量库 | Phase1: pgvector + **IVFFlat 索引** / Phase2: Milvus | 快速起步，IVFFalt 适合 <10 万条向量 |
| 缓存 | Redis 7 Cluster + **MinIO（大结果）** | 小结果放缓存，大结果(>1MB)存 MinIO，避免 Redis 内存浪费 |
| 消息队列 | **Apache RocketMQ 5.x** | 国产开源，支持事务/延迟/顺序消息 |
| 熔断降级 | **circuitbreaker + 自研降级策略** | gRPC 调用熔断 + LLM 降级（返回历史相似查询） |
| API 网关 | APISIX | 国产高性能 |
| 对象存储 | MinIO | S3 兼容，图表资源/审计归档 |
| 监控 | Prometheus + Grafana + Loki | 标准组合 |
| 链路追踪 | Jaeger (OpenTelemetry) | 分布式追踪 |
| 前端 | React + TypeScript + Vite | 现代 SPA |
| Prompt 管理 | **自研 PromptManager** (DB 版本化 + A/B 分流) | NL2SQL 核心质量保障，外部工具不满足 Prompt 版本化+效果追踪一体化需求 |
| 图表 | ECharts + VegaLite | 图表渲染 |
| Embedding | 通义 text-embedding-v3 / BGE-M3 | 中文语义好 |

### 2.1 国产 LLM 选型策略

通过 **LLM 抽象层** 实现多模型可插拔切换，不绑定单一模型：

| 用途 | 首选 | 备选 | 选型理由 |
|------|------|------|---------|
| 复杂推理 (NL2SQL/RCA/DAG) | **DeepSeek-V3** | Qwen-Max | 推理能力强，价格低 |
| 日常对话/解释 | Qwen-Plus | Qwen-Turbo | 速度快、成本低 |
| 结构化输出 | DeepSeek-V3 (JSON Mode) | Qwen-Max | 结构化稳定 |
| Text Embedding | text-embedding-v3 | BGE-M3 (自部署) | 中文语义好 |
| Function Calling | Qwen-Max | DeepSeek-V3 | FC 能力成熟 |

所有国产模型均通过 **OpenAI 兼容接口** 统一接入，DeepSeek 和 Qwen 都支持此协议。

---

## 三、项目目录结构

```
datapilot/
├── services/                      # 微服务（Phase1 合并部署）
│   ├── agent-service/             # Phase1: Agent Gateway + Chat Service
│   │   └── src/datapilot_agent/
│   │       ├── agent/core.py      # Agent主循环
│   │       ├── chat/              # SSE/WebSocket长连接
│   │       ├── llm/               # LLM Provider实现
│   │       │   ├── provider.py    # 统一协议
│   │       │   ├── qwen.py        # 通义千问
│   │       │   ├── deepseek.py    # DeepSeek
│   │       │   └── router.py      # 模型路由+熔断+降级
│   │       └── prompt_templates/  # Prompt模板
│   ├── semantic-service/          # Phase1: Semantic Layer + Metadata Service
│   │   └── src/datapilot_semantic/
│   │       ├── models/            # Metric/Dimension/Table模型 (含嵌套/虚拟/版本)
│   │       ├── metadata/          # 数据源注册/Schema提取/血缘
│   │       ├── retrieval/         # 向量检索+关键词+混合重排+语义缓存
│   │       └── translation/       # 指标/维度/过滤/时间粒度解析
│   ├── sql-generator-service/     # NL2SQL核心
│   │   └── src/datapilot_sqlgen/
│   │       ├── ast/               # sqlglot AST构建+方言适配+能力矩阵
│   │       ├── validation/        # SQL验证+Dry-run预执行+成本预估
│   │       └── generator/         # NL2SQL主流程+Few-shot+分场景纠错
│   ├── query-executor-service/    # 多源连接器+异步执行+结果缓存
│   ├── guardrail-service/         # SQL风险/成本/合规/行级+列级权限
│   ├── session-service/           # 会话/上下文/记忆
│   └── auth-service/              # JWT/LDAP/RBAC
│
│   # Phase2 新增
│   ├── planner-runtime/           # DAG任务编排引擎
│   ├── tool-registry-service/     # 工具注册中心
│   └── sandbox-manager/           # Python沙箱Pod管理
│
├── libs/                          # 共享库
│   ├── datapilot-common/          # 配置/异常/日志/遥测
│   ├── datapilot-license/         # **产品授权**（授权文件校验/IP白名单/有效期）
│   ├── datapilot-llm/             # LLM抽象层+Provider+路由+调用日志
│   ├── datapilot-prompt/          # Prompt模板管理+版本化+A/B测试+Token预算
│   ├── datapilot-sql/             # sqlglot AST封装+方言适配+验证器
│   └── datapilot-proto/           # gRPC Proto定义
│
├── web/                           # 前端 Monorepo
│   ├── packages/
│   │   ├── chat-ui/               # 聊天界面
│   │   ├── chart-engine/          # 图表引擎 (ECharts/VegaLite)
│   │   └── admin-dashboard/       # 管理后台
│   └── pnpm-workspace.yaml
│
├── infra/                         # 基础设施
│   ├── k8s/                       # Helm Charts + Kustomize
│   ├── docker/                    # Dockerfiles
│   └── scripts/                   # 运维脚本
│
├── tests/                         # 测试
│   ├── unit/                      # 单元测试 (pytest)
│   ├── integration/               # 集成测试 (testcontainers)
│   ├── e2e/                       # E2E测试 (Playwright)
│   └── benchmarks/                # NL2SQL评估+性能基准
│
├── docker-compose.dev.yml          # 本地开发环境
├── pyproject.toml                  # Python workspace根配置
└── Makefile
```

---

## 四、分阶段开发路线

### Phase 1: MVP - Semantic SQL Agent（第 1-13 周）

#### Sprint 1: 基础设施（第 1-2 周）

**目标：可运行的微服务骨架，用户可登录、发消息，前后端可并行开发**

| 任务 | 交付物 |
|------|--------|
| Monorepo 初始化、CI pipeline | 项目骨架、GitHub Actions |
| K8s dev 环境 + docker-compose.dev.yml | 本地一键启动 |
| Auth Service (JWT + 用户表) | 认证 API |
| API Gateway (APISIX + 路由) | 网关配置 |
| Session Service (PG + Redis) | 会话 CRUD |
| Agent Service 骨架 (FastAPI + SSE + WebSocket) | SSE/WS 端点 |
| **产品授权模块（datapilot-license）** | 授权文件校验 + IP 白名单 + 有效期 |
| 前端 Chat UI 骨架 (React) | 基本聊天窗口 |
| datapilot-common 共享库 | 日志/异常/遥测 |
| **OpenAPI 契约定义 + Mock 服务** | 前后端并行开发基础 |
| **Prometheus + Grafana 基础大盘** | QPS/延迟/错误率监控 |
| **NL2SQL 测试用例设计** | 100+ 测试用例框架（3 档难度） |

#### Sprint 2: Semantic Layer（第 3-4 周）

**目标：语义层核心，元数据管理和语义检索可用**

| 任务 | 交付物 |
|------|--------|
| 数据源注册、连接管理 | 数据源 CRUD API |
| Schema Extractor：自动提取表结构 | Schema 入库 |
| Metric/Dimension/Table 数据模型 | 语义层核心模型 |
| **指标版本机制**（version + effective_time） | 口径一致性保障 |
| **虚拟维度/指标**（CASE WHEN 计算） | 减少物理冗余 |
| Embedding 生成器 (text-embedding-v3) | 向量化管道 |
| pgvector 向量检索（IVFFlat 索引） | 语义搜索 API |
| 混合检索 (向量+关键词) + RRF 重排 | 混合检索 API |
| **语义缓存**（Metric/Dimension 元数据→Redis） | 减少高频 PG 访问 |
| **Prompt 模板管理**（版本化 + A/B 测试框架） | Prompt 管理系统 |
| Admin Dashboard：语义模型管理页面 | 管理 UI |
| 3 个业务域样例数据注册完成 | 样例 Metric/Dimension |

#### Sprint 3a: NL2SQL 核心（第 5-6 周）

**目标：LLM 接入和 SQL 生成链路可用**

| 任务 | 交付物 |
|------|--------|
| LLM 抽象层：Provider 协议 + Qwen/DeepSeek 实现 | datapilot-llm 库 |
| Model Router + 熔断/降级策略（**分级模型：简单→Turbo，复杂→V3**） | 模型可切换+智能降级 |
| **LLM 调用日志**（token 消耗、延迟、成本、成功率） | 成本追踪基础 |
| **意图路由**（SQL 查询 / 闲聊 / 超出范围，各走不同模型） | 意图分类器 |
| Intent Parser：结构化输出 | 意图解析 API |
| Schema Linking：意图→表/字段匹配 | Schema 选择 |
| SQL AST Builder (sqlglot) | AST 构建器 |
| NL2SQL 主流程 (Intent→Semantic→Schema→SQL) | NL2SQL 核心 |
| Few-shot 选择 (相似度匹配) + 企业专属 Few-shot 库 | Few-shot 引擎 |

#### Sprint 3b: 验证与集成（第 7-8 周）

**目标：验证体系完善，端到端链路可用**

| 任务 | 交付物 |
|------|--------|
| SQL Validator + 方言适配 | SQL 验证器 |
| **SQL Dry-run 预执行**（通过只读模式验证表存在/权限/类型） | 双重校验 |
| **SQL 成本预估**（EXPLAIN ANALYZE 预计算扫描行数/执行时间） | 成本控制 |
| **分场景 Self-Correction**（语法错误/表不存在/结果为空 各自定制纠错 Prompt） | 自纠错机制 |
| Guardrail 基础：SQL 风险检测、行数限制、**查询配额** | 安全拦截+成本控制 |
| 端到端集成：自然语言→SQL→执行→结果 | 完整链路 |
| **用户可编辑 SQL 后重新执行** | 人工干预能力 |
| **用户反馈闭环**（编辑 SQL 自动收录为 Few-shot、满意度 👍/👎） | 持续优化基础 |
| **SQL 自然语言解释**（"这个查询统计了..."） | SQL 可读性 |
| **Token 预算策略**（Few-shot + 表结构 + 历史对话超窗口时按优先级裁剪） | 上下文管理 |
| NL2SQL 测试（简单>=70%/中等>=50%/复杂>=30%） | 测试报告 |

#### Sprint 4: Execution Layer（第 9-11 周）

**目标：多数据源连接、异步执行、结果缓存、细粒度权限**

| 任务 | 交付物 |
|------|--------|
| **数据源能力矩阵**（各数据源 SQL 语法支持情况） | 方言兼容性参考表 |
| MySQL/PostgreSQL 连接器 (连接池 pool_size=10) | OLTP 连接器 |
| Doris/StarRocks 连接器 (连接池 pool_size=20) | OLAP 连接器 |
| ClickHouse 连接器 (连接池 pool_size=15) | 连接器 |
| **差异化重试**（临时错误重试，语法错误直接终止） | 重试策略 |
| 统一结果格式化 (JSON/CSV) | 结果格式化 |
| 异步执行 (提交+轮询) | 异步 API |
| 结果缓存（小结果→Redis, 大结果>1MB→MinIO） | 分级缓存 |
| **大结果集分页**（默认 LIMIT 1000 + 游标分页 + 懒加载） | 大数据量处理 |
| **数据新鲜度标注**（实时/小时级/T+1，结果附带数据截止时间） | 信息透明 |
| RBAC 行级权限 (SQL WHERE 注入) | 权限过滤 |
| **列级权限**（隐藏敏感字段） | 列权限控制 |
| **数据脱敏**（手机号、身份证等） | 脱敏规则 |
| **操作权限**（只读/可导出/可执行 DDL） | 操作级权限 |
| **数据源健康监控**（连接池使用率、平均延迟、不可达自动摘除） | 数据源可观测性 |

#### Sprint 5: Frontend + Phase1 收尾（第 12-13 周）

**目标：完整用户体验，Phase1 集成验收**

| 任务 | 交付物 |
|------|--------|
| SQL Explain 展示 + **SQL 自然语言解释** | SQL 解释面板 |
| **用户编辑 SQL 并重新执行** | SQL 编辑能力 |
| ECharts 图表 (折线/柱/饼) | 图表渲染 |
| 数据表格 (排序/筛选/分页/导出/**懒加载**) | 表格组件 |
| 危险 SQL 确认机制 | 确认对话框 |
| 加载态/错误态/重试 | UX 完善 |
| **异常场景友好提示**（未匹配指标/SQL超时/超出范围引导） | 错误提示优化 |
| **新手引导**（首次登录展示示例查询 + 语义模型介绍） | 用户入门 |
| **查询历史与收藏**（查看历史、收藏常用、一键复用） | 效率提升 |
| **单会话 10+ 轮上下文关联** | 多轮对话能力 |
| **业务指标大盘**（DAU、查询频次、NL2SQL 准确率趋势、编辑率、热门指标） | 运营决策支持 |
| Phase1 E2E 测试 + 压力测试 | 测试报告 |
| 95% 请求 < 2 秒 | 性能达标 |
| **熔断降级机制验证**（LLM 全不可用时返回历史相似查询） | 降级测试 |

**Phase1 交付总结：**
- 企业可试点的 Semantic SQL Agent
- **产品授权控制**（授权文件 + IP 白名单 + 有效期校验，未授权不可使用）
- 自然语言→SQL→执行→结果→图表 完整链路
- 国产模型 (Qwen/DeepSeek) 可切换 + 分级模型策略 + Prompt 版本管理
- 5 种数据源支持 + 数据源能力矩阵 + 健康监控
- **行级 + 列级权限 + 数据脱敏 + 操作权限**
- 语义层增强：指标版本、虚拟维度/指标、语义缓存
- NL2SQL 分场景纠错 + SQL Dry-run + 成本预估 + SQL 自然语言解释
- 用户反馈闭环（编辑 SQL→Few-shot 自动收录）+ 满意度收集
- 意图路由（SQL/闲聊/超出范围各走不同通道）+ Token 预算管理
- 大结果集分页 + 数据新鲜度标注 + 查询历史与收藏
- 用户可编辑 SQL + 10 轮上下文 + 新手引导 + 异常友好提示
- 查询配额 + 熔断降级 + 审计日志 + LLM 成本追踪
- **3 个典型业务场景验证**（销售数据查询/用户行为分析/库存统计）
- 业务指标大盘 + Admin 管理后台

---

### Phase 2: Multi-Step Agent（第 14-27 周）

#### Sprint 6: 服务拆分 + Planner Runtime（第 14-16 周）
- **服务拆分**：Agent Service → Agent Gateway + Chat Service，Semantic → Semantic + Metadata
- DAG Builder/Executor：拓扑排序 + 并行调度（**Phase2 才支持条件分支**）
- 失败重试 (指数退避)，执行限制 max_depth=5, max_retry=3
- 多任务类型 (SQL/Python/Search/Action)
- DAG 执行进度可视化

#### Sprint 7: Python Sandbox（第 17-18 周）
- K8s Pod 池管理 (预热/回收/扩缩)
- **定时清理无响应 Pod**（30s 超时强制销毁）
- **Pod 资源监控**，超阈值自动扩缩
- 安全策略：seccomp + NetworkPolicy + readOnlyRootFS + AST 代码检查
- pandas/sklearn/matplotlib/seaborn 执行环境（10+ 常用库）
- 资源限制：CPU 1核 / 内存 512Mi / 超时 30s / 输出 1MB

#### Sprint 8: Tool Registry + RCA（第 19-21 周）
- 工具注册/发现/能力描述
- Function Calling 集成
- RCA 分析流程：异常检测→维度下钻→归因分析
- 数据解释：趋势分析、Key Driver 标注

#### Sprint 9: Chart Engine + Dashboard（第 22-24 周）
- 统一 Chart Spec 规范
- ECharts 全图表类型渲染
- LLM 智能图表类型推荐
- Dashboard 自动生成 (多图表布局 + 过滤器)
- **Dashboard 自动刷新 + 多维度下钻**
- **跨源查询 DAG**（如 MySQL 取用户→Doris 算销量→Python 做聚合，Arrow 格式传输）

#### Sprint 10: Memory + 优化 + 生产就绪（第 25-27 周）
- 短期记忆 (Redis 会话上下文)
- 长期记忆 (用户偏好、历史查询模式)
- NL2SQL 准确率优化至 >= 85%
- **幻觉防护系统**（事实校验/结果合理性/数值范围/SQL-结果一致性）
- 审计日志全链路
- **灰度发布**（按租户灰度分流 + 自动回滚：错误率>3%触发）
- Prometheus + Grafana 监控大盘
- 生产部署 + **试点计划启动**

**Phase2 交付总结：**
- 多步 Agent（DAG 编排 + 条件分支 + 并行调度）
- Python Sandbox（10+ 常用库 + 多层安全 + Pod 自动管理）
- 工具注册中心 + Function Calling + RCA 分析
- 完整 Dashboard（自动生成 + 多维度下钻 + 自动刷新）
- 跨源查询 DAG（Arrow 格式传输）
- 短期记忆 + 长期记忆 + 幻觉防护
- NL2SQL 准确率 >= 85%（中等查询）
- 服务拆分为 10 个独立微服务
- 完整多租户支持
- 灰度发布 + 生产运维体系
- 试点验证通过，具备全面推广条件

---

## 五、关键技术方案

### 5.1 NL2SQL 完整流程（10 步）

```
用户输入 → Session上下文加载(10+轮) → Token 预算检查
→ 意图路由 (Intent Router)
   ├─ SQL 查询 → 继续 NL2SQL 流程
   ├─ 闲聊 → Qwen-Turbo 轻量响应
   └─ 超出范围 → 友好提示 + 引导已有语义模型
→ Intent Parsing (LLM结构化输出)
→ Semantic Resolution (指标/维度/时间/过滤解析)
→ Schema Linking (表选择+JOIN路径推导)
→ SQL Generation (LLM + sqlglot AST)
→ SQL Validation & Guardrail (语法/风险/成本/权限)
   ├─ AST 级校验 (表/列是否存在、方言兼容性)
   ├─ Dry-run 预执行 (只读模式验证权限/类型)
   └─ SQL 成本预估 (EXPLAIN ANALYZE: 扫描行数/执行时间)
→ Self-Correction Loop (最多3轮，分场景纠错)
   ├─ 语法错误 → AST 校验反馈 → 修正 SQL
   ├─ 表/字段不存在 → 元数据匹配反馈 → 重新 Schema Linking
   └─ 执行超时/结果为空 → 过滤条件放宽建议 → 用户确认
→ Query Execution (异步+分级缓存+大结果集分页)
   ├─ 小结果 (<1MB) → Redis
   └─ 大结果 (>=1MB) → MinIO + 默认 LIMIT 1000 + 游标分页
→ Result Processing (摘要+图表推荐+异常检测+数据新鲜度标注)
→ SQL 自然语言解释 → 用户可编辑 SQL → 重新执行
→ 用户反馈收集 (满意度 + 编辑后的 SQL 自动收录为 Few-shot)
→ Response Streaming (SSE推送)
```

### 5.2 SQL AST 方案（基于 sqlglot）

**不直接输出字符串 SQL，必须走 AST → Render 流程：**
- 使用 sqlglot 构建 SQL AST
- AST 级别验证表/列是否存在
- AST 级别注入 RBAC WHERE 条件（行级 + 列级）
- sqlglot 原生方言转换：通用 AST → MySQL/PG/Doris/StarRocks/ClickHouse
- **数据源能力矩阵**：各数据源 SQL 语法支持表，AST 阶段做方言兼容性校验
  - 如 Doris 不支持 `WITH RECURSIVE`、ClickHouse 不支持多表 `JOIN` → 自动降级或提示
- **SQL Dry-run 预执行**：通过各数据源只读模式验证表权限、字段类型匹配
- **SQL 成本预估**：`EXPLAIN ANALYZE` 预计算扫描行数和执行时间，超阈值触发简化建议或人工确认

### 5.3 DAG 执行引擎

- 自研轻量引擎（非 Airflow/Prefect，因为需要秒级实时响应）
- **Phase1**：支持线性多步任务（SQL→Python→Search），不涉及复杂条件分支
- **Phase2**：新增条件分支、并行调度
- 支持能力：DAG 构建、拓扑排序、失败重试 (指数退避)、超时控制
- 执行限制：max_depth=5, max_retry=3

### 5.4 Python Sandbox 安全方案

多层防护：
1. **AST 级检查**：禁止 import os/sys/subprocess/socket 等
2. **K8s SecurityContext**：runAsNonRoot, readOnlyRootFS, drop ALL capabilities
3. **NetworkPolicy**：完全禁止出站流量
4. **资源限制**：CPU 1核 / 内存 512Mi / 超时 30s / 输出 1MB
5. **seccomp**：RuntimeDefault 配置
6. **Pod 生命周期管理**：定时清理无响应 Pod（30s 超时强制销毁），资源监控超阈值自动扩缩

### 5.5 Semantic Layer 三层抽象

```
Semantic Model (业务视图) → Logical Layer (Metric/Dimension/Filter) → Physical Layer (数据源表)
```

语义检索：向量检索 (pgvector IVFFlat) + 关键词匹配 → RRF 混合重排 → 关系补全 (JOIN推导) → RBAC 权限过滤

#### 语义层增强能力

- **指标嵌套**：支持 Metric 引用其他 Metric（如「环比增长率 = (本期值-上期值)/上期值」）
- **维度层级**：支持层级结构（如「省份→城市→区县」），支持自动上卷/下钻
- **时间粒度自动转换**：日/周/月/季自动聚合
- **虚拟维度/指标**：基于现有字段计算（如「年龄段 = CASE WHEN age<20 THEN '青少年' ...」），减少物理冗余
- **指标版本机制**：version + effective_time，防止同指标不同口径（如「GMV」含税/不含税）
- **语义缓存**：Metric/Dimension 元数据 + 向量缓存到 Redis，避免高频访问 PG
- **元数据增量同步**：仅同步变更表/字段，变更后自动更新向量库

### 5.6 权限体系（RBAC 三层粒度）

#### 行级权限
通过 sqlglot AST 注入 WHERE 条件：
- 静态值过滤：`region IN ('华东','华南')`
- 动态属性：`user.regions` 映射为用户可访问区域
- 策略优先级和合并

#### 列级权限
- 控制用户可访问的字段，隐藏敏感字段（如手机号、身份证、薪资）
- 通过 AST 移除 SELECT 中无权限的列

#### 数据脱敏
- 手机号 → 138****1234
- 身份证 → 310***********1234
- 银行卡 → 6222 **** **** 1234
- 按数据源+字段配置脱敏规则

#### 操作权限
- 只读：仅查询，禁止导出
- 可导出：允许查询+导出
- 可执行 DDL：允许创建/修改表（仅管理员）

#### 查询配额
- 按用户/角色设置配额：日执行次数上限、小时扫描行数上限
- 大表查询强制 LIMIT，超配额提示用户

### 5.7 Prompt 管理体系

NL2SQL 质量高度依赖 Prompt，需作为一等公民管理：

- **Prompt 三层结构**：系统 Prompt（角色定义）→ Few-shot Prompt（示例注入）→ 用户 Prompt（输入拼接）
- **版本管理**：每次 Prompt 修改记录版本号 + 变更说明 + 效果指标，支持回滚
- **A/B 测试**：同一场景多个 Prompt 版本随机分流，对比准确率/延迟
- **Token 预算策略**：当 Few-shot + 表结构 + 历史对话总量超过模型窗口时，按以下优先级裁剪：
  1. 保留系统 Prompt（不可裁剪）
  2. 保留用户最近 3 轮对话
  3. 裁剪 Few-shot 示例（优先保留高相似度示例）
  4. 裁剪表结构描述（保留命中表，移除无关表）
- **LLM 调用日志**：每次调用记录模型、token 消耗（prompt/completion）、延迟、成本、成功率

### 5.8 意图路由

用户输入先经过意图分类，分流到不同处理通道：

| 意图类型 | 判断方式 | 处理模型 | 响应 |
|---------|---------|---------|------|
| SQL 查询 | LLM 分类器 | DeepSeek-V3 | 走 NL2SQL 完整流程 |
| 闲聊/解释 | LLM 分类器 | Qwen-Turbo | 轻量响应，不消耗 V3 资源 |
| 超出范围 | LLM 分类器 | - | 友好提示 + 引导到已有语义模型 |
| 需人工介入 | 规则（连续 3 次纠错失败） | - | 转人工 / 提供历史相似查询 |

### 5.9 用户反馈闭环

用户交互产生的数据是 NL2SQL 持续优化的核心资产：

- **编辑 SQL 自动收录**：用户修改后的 SQL 自动进入 Few-shot 候选库（经审核后生效）
- **满意度反馈**：每次查询结果附带 👍/👎，低满意度查询自动标记供分析
- **高频纠错模式发现**：当同一类 SQL 错误编辑率 > 20%，自动触发 Prompt 优化建议
- **Few-shot 质量评估**：定期统计 Few-shot 命中率和效果，淘汰低效示例

### 5.10 大结果集与数据新鲜度

#### 大结果集处理
- 默认 LIMIT 1000 行，前端展示"共 N 行，当前显示前 1000 行"
- 超过 1000 行提示用户加过滤条件，或点击"加载更多"（游标分页）
- 超过 10 万行禁止全量导出，引导用户使用 Python Sandbox 处理

#### 数据新鲜度
- 语义模型标注数据源新鲜度级别：`realtime` / `hourly` / `daily` / `custom`
- 查询结果附带数据截止时间提示："数据截至 2026-05-26 23:59"
- 用户问"今天的订单"但数据源为 T+1 时，主动提示数据延迟

### 5.11 多租户隔离

企业产品需要多部门/多子公司共用一个部署，最小实现方案：

- **隔离粒度**：`tenant_id` 字段贯穿所有核心表（users, sessions, data_sources, metrics, dimensions, semantic_models, rbac_policies, nl2sql_examples）
- **API 层**：JWT Token 中携带 `tenant_id`，所有查询自动注入租户过滤条件
- **数据隔离**：不同租户的语义模型、数据源、查询历史、配额完全隔离，互不可见
- **配额隔离**：查询配额、LLM 成本预算按租户独立计算
- **Phase1**：单租户（hardcode `tenant_id`），预留字段扩展
- **Phase2**：完整多租户支持 + Admin 租户管理界面

### 5.12 LLM 成本预算

| 层级 | 控制方式 | 说明 |
|------|---------|------|
| 月度总预算 | 设定上限（如 ¥50,000/月） | 接近 80% 告警，超出后降级为缓存+历史查询 |
| 租户预算 | 按租户分配月度额度 | 某租户超额不影响其他租户 |
| 单次查询预算 | Token 上限（prompt 8K + completion 4K） | 防止单次调用异常消耗 |
| 用户级配额 | 日查询次数上限 | 防止个别用户滥用 |

成本追踪：`llm_call_logs` 表记录每次调用成本，Prometheus 面板展示日/周/月成本趋势，按模型/租户/用户维度聚合。

### 5.13 Model Router 判断逻辑

避免用 LLM 判断是否用 LLM（鸡生蛋问题 + 额外成本），采用**规则启发式 + 失败升级**：

```
Step 1: 规则快速判断
  ├─ 纯闲聊/问候 → Qwen-Turbo（关键词匹配：你好/谢谢/是什么）
  ├─ 命中高置信 Few-shot（相似度 > 0.95）→ Qwen-Turbo（轻量复用）
  └─ 涉及多表 JOIN / 窗口函数 / 复杂聚合 → DeepSeek-V3

Step 2: 失败升级（仅对 Step 1 判断为"简单"的查询）
  ├─ Qwen-Turbo 结构化输出解析失败 → 升级到 DeepSeek-V3
  └─ DeepSeek-V3 也失败 → 返回友好错误 + 历史相似查询

Step 3: 熔断降级
  └─ DeepSeek-V3 不可用 → 降级为 Qwen-Max，仍不可用 → 纯缓存模式
```

**判断特征：**
- 简单：单表查询 + 简单过滤 + 命中已有 Few-shot
- 中等：多表 JOIN + 时间范围过滤 + 排序/聚合
- 复杂：窗口函数、嵌套子查询、跨数据源、需要计算推导

### 5.14 会话管理

| 项目 | 策略 |
|------|------|
| 会话超时 | 30 分钟无操作自动过期 |
| 最大消息数 | 单会话 50 条消息，超出后提示用户开启新会话 |
| 历史会话列表 | 用户可查看/切换/删除历史会话 |
| 会话数据保留 | 活跃会话 90 天，过期会话归档至 MinIO |
| 上下文窗口 | Token 预算策略控制（5.7 节），超出时按优先级裁剪 |
| 跨设备 | 同一用户可在不同设备查看历史会话（基于 user_id） |

### 5.15 API 数据源集成

| 能力 | 说明 |
|------|------|
| 协议支持 | REST API（GET/POST）、GraphQL |
| 认证方式 | API Key / OAuth2 Bearer Token / Basic Auth |
| 响应映射 | API JSON 响应 → 虚拟表结构（配置 JSON Path 映射规则） |
| 分页处理 | offset/limit、cursor-based、link header |
| 缓存策略 | 定时拉取到本地（不可实时查询），由 Admin 配置同步频率 |
| 数据新鲜度 | API 数据源自动标记为 `hourly` 或 `custom` |
| 限制 | 不支持 JOIN（单 API 作为独立数据表）、不支持 WHERE 下推 |

Phase2 实现，Phase1 仅支持关系型/OLAP 数据源。

### 5.16 幻觉防护系统

| 防护层 | 机制 | 触发条件 |
|--------|------|---------|
| 事实校验 | SQL 中引用的表/字段必须在元数据中存在 | AST 校验失败 → 拒绝执行 |
| 结果合理性 | 聚合结果与历史同口径值对比 | 偏差 > 50% → 标记"结果异常，请核实" |
| 数值范围 | 指标值与预设合理范围对比 | 超出范围 → 标记"数值异常" |
| SQL-结果一致性 | SELECT 字段与返回列对齐 | 不一致 → 重新生成或拒绝 |
| 时序校验 | 趋势类查询结果时序连续性检查 | 断崖式下跌/暴涨 → 提示可能异常 |

### 5.17 产品授权机制

企业级产品交付需要授权文件控制，未授权的部署不允许使用。Phase1 采用轻量方案，Phase2 可升级深度认证。

#### 授权文件格式（`license.json`）

```json
{
  "product": "DataPilot",
  "licensee": "xxx公司",
  "license_key": "DP-XXXX-XXXX-XXXX",
  "issued_at": "2026-05-27",
  "expires_at": "2027-05-27",
  "allowed_ips": ["192.168.1.0/24", "10.0.0.1"],
  "max_concurrent_users": 100,
  "features": ["nl2sql", "semantic_model", "export"],
  "signature": "HMAC-SHA256签名"
}
```

#### 校验层级

| 校验项 | 说明 | 失败处理 |
|--------|------|---------|
| **签名校验** | HMAC-SHA256 验证文件未被篡改 | 服务启动失败，日志记录 |
| **有效期校验** | `issued_at` ~ `expires_at` | 服务启动失败 + 管理界面告警 |
| **IP 白名单** | 请求 IP 是否在 `allowed_ips` 范围内（支持 CIDR） | 返回 403 + `LICENSE_IP_DENIED` |
| **功能许可** | `features` 控制可用功能模块 | 对应功能返回 403 + `LICENSE_FEATURE_DISABLED` |
| **并发用户** | `max_concurrent_users` 限制在线用户数 | 排队等待或返回 `LICENSE_USER_LIMIT` |

#### 实现架构

```
libs/datapilot-license/
├── license.py          # LicenseInfo 数据模型 + 解析
├── validator.py        # 校验逻辑（签名/有效期/IP/功能）
├── middleware.py       # FastAPI 中间件（启动校验 + 请求拦截）
├── crypto.py           # HMAC-SHA256 签名/验证
├── cli.py              # CLI 工具（生成授权文件）
└── LICENSE.example.json
```

**集成方式**：
- Agent Service 启动时加载并校验 `license.json`，校验失败**拒绝启动**
- 通过 FastAPI 中间件在请求层做 IP 校验（带 Redis 缓存，避免每次请求都解析）
- 未授权请求返回标准错误码（`LICENSE_INVALID` / `LICENSE_EXPIRED` / `LICENSE_IP_DENIED`）

#### Phase1 vs Phase2 授权对比

| 维度 | Phase1 | Phase2（可升级） |
|------|--------|----------------|
| 校验方式 | IP 白名单 + 有效期 | + 机器指纹（MAC/主板序列号）+ 在线激活 |
| 功能控制 | features 列表 | + 按租户/用户粒度的功能开关 |
| 并发控制 | max_concurrent_users 全局 | + 按角色的并发和配额控制 |
| 授权管理 | 手动替换 license.json | + 管理界面在线查看/续期 |
| 防篡改 | HMAC-SHA256 签名 | + RSA 非对称签名 + 在线验证 |
| 审计 | 启动日志记录 | + 授权变更审计日志 |

---

## 六、核心数据模型

**PostgreSQL 核心表（所有业务表携带 `tenant_id` 字段用于多租户隔离）：**
- `tenants` — 租户配置（名称、域名、LLM 月度成本预算、状态）
- `data_sources` — 数据源连接配置（含连接池参数 pool_size、**freshness_level**）
- `datasource_capabilities` — 数据源 SQL 语法能力矩阵（支持的语法特性标记）
- `source_tables` — 物理表元数据 + pgvector 语义向量
- `metrics` — 业务指标定义 (name, calculation, embedding, **version, effective_time**, **parent_metric_id** 支持嵌套)
- `dimensions` — 分析维度 (column_name, synonyms, **hierarchy** 层级, embedding, **is_virtual** 虚拟标记)
- `metric_dimensions` — 指标-维度多对多关联
- `table_relationships` — JOIN 路径定义
- `semantic_models` — 业务语义视图
- `users / sessions / messages` — 用户会话消息（**session 含 max_messages=50, expires_at 30min**）
- `rbac_policies / user_policy_bindings` — RBAC 策略（**含列级权限 column_masking_rules**）
- `data_masking_rules` — 数据脱敏规则（字段+脱敏类型+配置）
- `user_quotas` — 用户查询配额（日次数/小时扫描行数上限）
- `audit_logs` — 审计日志 (谁/何时/SQL/扫描行数/风险等级/返回行数, MinIO 冷存储归档)
- `query_cache` — 查询结果缓存
- **`nl2sql_examples`** — Few-shot 示例库 (question, sql, embedding, domain, difficulty, source: builtin/user_contributed, is_verified)
- **`prompt_versions`** — Prompt 模板版本 (version, content, scene, effectiveness_metrics, ab_test_results)
- **`llm_call_logs`** — LLM 调用日志 (model, prompt_tokens, completion_tokens, latency_ms, cost, success, trace_id)
- **`user_feedbacks`** — 用户反馈 (query_id, satisfaction, edited_sql, feedback_text, created_at)
- **`query_history`** — 查询历史 (user_id, session_id, question, sql, datasource, row_count, latency_ms, **is_favorited**)
- **`datasource_health`** — 数据源健康状态 (datasource_id, pool_usage, avg_latency_ms, last_heartbeat, status: healthy/degraded/down)

---

## 七、团队分工（8+ 人）

| 角色 | Sprint 1-5 (Phase1) | Sprint 6-8 (Phase2 前半) | Sprint 9-10 (Phase2 收尾) |
|------|-------------------|------------------------|------------------------|
| 架构师/TL (1) | LLM 抽象层、**Prompt 管理体系**、系统设计 | DAG 引擎架构、服务拆分 | 全局优化 |
| 后端A (1) | Auth/Session/Agent Service | SQL Generator | Tool Registry |
| 后端B (1) | Gateway/Guardrail | Query Executor/缓存/分页 | 权限/审计 |
| 后端C (1) | Semantic Service (含元数据) | SQL AST Builder | RCA 分析 |
| 后端D (1) | Semantic 检索/缓存 | 语义检索优化 | Memory 系统 |
| 后端E (1) | Sprint3+加入 | 数据源连接器/健康监控 | Python Sandbox |
| 前端A (1) | Chat UI 骨架 | 图表/SQL 展示 | Dashboard |
| 前端B (1) | Sprint2+加入 | Admin 管理 | Dashboard 高级 |
| 测试工程师 (1) | Sprint1 提前介入 NL2SQL 用例设计 | 测试自动化 | 全链路测试 |
| DevOps (1) | CI/CD/K8s + **监控大盘** | 沙箱安全、服务拆分部署 | 生产运维 |

---

## 八、风险应对

| 风险 | 应对策略 |
|------|---------|
| 国产 LLM 准确率不足 | Prompt 工程 + Few-shot（**企业专属库按业务域分类**）+ 分场景 Self-Correction + **人工干预（用户可编辑 SQL）** + 预留 OpenAI 应急通道 |
| SQL 方言兼容 | sqlglot AST 转换 + 方言适配器 + **数据源能力矩阵**（各数据源 50+ 典型 SQL 测试）+ 不兼容语法自动降级（如窗口函数→子查询） |
| LLM 延迟过高 | **分级模型响应**（简单→Qwen-Turbo，复杂→DeepSeek-V3）+ SSE 流式 + 异步执行 + 分级缓存 + **预计算高频查询**（如「昨日销售额」） |
| 查询成本失控 | EXPLAIN 预分析 + 扫描行数限制 + **用户/角色查询配额** + 大表强制 LIMIT + 离线计算大口径指标 |
| 沙箱安全 | 多层防护 + 独立 Namespace + 定期审计 + **定时清理无响应 Pod** + Pod 资源监控 |
| 向量召回不足 | 混合检索 + RRF 重排 + BGE-Reranker + 同义词库 + **人工标注语义-表/字段关联** + 元数据变更自动更新向量 |
| **微服务依赖雪崩** | **各服务增加熔断器**（gRPC 调用超时/失败次数阈值）+ 核心服务多副本 + **降级策略**（LLM 不可用→返回历史相似查询） |
| **元数据同步延迟** | **增量同步**（仅同步变更表/字段）+ 同步失败告警+重试 + 元数据变更后自动更新向量库 |

---

## 九、验证方案

1. **NL2SQL 准确率**：100+ 测试用例分 3 档难度
   - 简单（单表无过滤）：Phase1 >= 70%，Phase2 >= 85%
   - 中等（多表 JOIN+过滤）：Phase1 >= 50%，Phase2 >= 75%
   - 复杂（子查询/窗口函数）：Phase1 >= 30%，Phase2 >= 60%
2. **性能基准**：k6/Locust 压测，P95 < 2s，吞吐 > 100 QPS
3. **安全测试**：OWASP Top 10 + SQL 注入 + 权限绕过（行级+列级+脱敏验证）
4. **沙箱逃逸测试**：AST 绕过 + 网络探测 + 文件系统突破
5. **CI 门禁**：单测覆盖 >= 70%，集成测试通过率 >= 95%
6. **熔断降级测试**：模拟 LLM 全不可用，验证降级策略生效
7. **业务场景验收**：3 个典型场景端到端通过（销售数据查询/用户行为分析/库存统计）
8. **上下文记忆测试**：单会话 10+ 轮上下文关联准确率 >= 90%

---

## 十一、K8s 资源规划

### Phase1 资源分配（开发/测试环境）

| 服务 | Replicas | CPU request | Memory request | 说明 |
|------|----------|------------|----------------|------|
| Agent Service | 2 | 1 | 2Gi | LLM 调用密集，SSE 长连接 |
| SQL Generator | 2 | 1 | 1Gi | CPU 密集（sqlglot AST） |
| Semantic Service | 2 | 1 | 2Gi | pgvector 检索，向量计算 |
| Query Executor | 2 | 0.5 | 1Gi | I/O 密集（数据库连接池） |
| Guardrail | 1 | 0.5 | 512Mi | 轻量校验 |
| Auth / Session | 2 | 0.5 | 512Mi | 轻量 CRUD |
| **基础设施** | | | | |
| PostgreSQL 16 | 1 | 1 | 4Gi | 元数据 + pgvector |
| Redis 7 | 3 (cluster) | 0.5 | 2Gi | 缓存 + 会话 + 分布式锁 |
| RocketMQ | 2 (broker) | 1 | 2Gi | 消息队列 |
| APISIX | 2 | 0.5 | 512Mi | API 网关 |
| MinIO | 2 | 0.5 | 2Gi | 对象存储 |
| Prometheus + Grafana | 1 | 0.5 | 1Gi | 监控 |

**总计**：~12 CPU cores, ~25 Gi 内存（开发环境可按 50% 缩减）

### Phase2 新增资源

| 新增服务 | Replicas | CPU | Memory |
|---------|----------|-----|--------|
| Planner Runtime | 2 | 1 | 1Gi |
| Tool Registry | 1 | 0.5 | 512Mi |
| Sandbox Manager | 1 | 0.5 | 512Mi |
| Python Sandbox Pods | 按需 (max 10) | 1/each | 512Mi/each |

---

## 十二、Phase1 试点计划

### 试点范围

| 项目 | 内容 |
|------|------|
| 试点部门 | 2-3 个业务部门（数据分析团队优先） |
| 试点用户 | 20-50 人（数据分析师 + 业务运营） |
| 试点周期 | Phase1 交付后 4 周 |
| 试点数据域 | 3 个已注册的业务域 |

### 试点成功标准

| 指标 | 目标值 |
|------|--------|
| 日活跃用户 (DAU) | >= 15 人 |
| 人均日查询次数 | >= 5 次 |
| NL2SQL 准确率（简单查询） | >= 70% |
| 用户 SQL 编辑率 | < 30%（编辑率越低说明 NL2SQL 越好） |
| 用户满意度 (👍/👎) | >= 80% 正向 |
| P95 响应延迟 | < 2 秒 |

### 试点→全面推广 Gate

- 全部试点成功标准达标
- 无 P0 安全事故
- 灰度发布机制验证通过
- 多租户隔离验证通过

---

## 十三、灰度发布策略

| 策略 | 说明 |
|------|------|
| 按租户灰度 | 新版本先部署到测试租户，验证后逐步开放生产租户 |
| 按比例灰度 | APISIX 路由 10% 流量到新版本，观察错误率 |
| 自动回滚 | 错误率 > 3% 或 P95 延迟 > 5s 持续 2 分钟 → 自动回滚 |
| 数据库迁移 | 新旧表并行（`_v2` 后缀），双写过渡 1 周，确认后迁移数据 |

---

## 十四、关键架构决策

1. **sqlglot 做 AST** 而非字符串拼接 → 安全 + 方言兼容 + RBAC 注入
2. **Phase1 pgvector + IVFFlat** 而非 Milvus → 减少运维组件，IVFFlat 索引适合 <10 万条向量
3. **RocketMQ** 而非 Kafka → 国产开源 + 延迟消息 + 事务消息
4. **自研 DAG 引擎** 而非 Airflow → 需要秒级实时 + Phase2 条件分支 + 动态 DAG
5. **SSE** 而非 WebSocket 做消息流 → 单向推送足够，实现更简单
6. **Phase1 合并服务**而非一步到位 10 服务 → 7 人团队 6 个月交付可行性优先，Phase2 拆分
7. **分级缓存**（Redis 小结果 + MinIO 大结果）而非统一 Redis → 避免大结果占用 Redis 内存
8. **SQL AST 校验 + Dry-run 预执行** 双重验证 → 单 AST 校验无法发现权限/类型问题
9. **分级模型响应**（Turbo 处理简单查询，V3 处理复杂推理）→ 成本与质量平衡
10. **自研 PromptManager** 而非外部工具 → Prompt 版本化 + A/B 测试 + 效果追踪一体化，外部工具无法满足
11. **意图路由分流**（SQL/闲聊/超出范围各走不同通道）→ 节省高成本模型资源 + 提升用户体验
12. **用户反馈闭环**（编辑 SQL→Few-shot 收录）→ 用户行为数据驱动 NL2SQL 持续优化，降低人工调优成本
13. **Model Router 规则启发式** 而非 LLM 分类 → 避免额外 LLM 调用成本，失败升级兜底
14. **多租户 tenant_id 字段** 贯穿设计 → Phase1 预留、Phase2 完整支持，避免后期大规模重构
15. **LLM 月度成本预算 + 租户级配额** → 生产运营必需，防止单租户/异常用户成本失控
16. **产品授权文件控制** → 企业级产品交付必需，Phase1 采用 IP 白名单 + 有效期，Phase2 可升级深度认证
