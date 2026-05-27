# 架构决策记录 (ADR)

> 本文档记录 DataPilot 项目中的关键架构决策及其理由。
> 每个决策遵循 ADR 模板：背景、决策、理由、后果。

---

## ADR-001: 使用 sqlglot 作为 SQL 解析与操作引擎

**状态**: 已采纳

**背景**:
NL2SQL 系统需要对生成的 SQL 进行多次 AST 级操作：
- RBAC 注入（行级 WHERE 条件、列级投影移除）
- SQL 校验（语法检查、成本预估）
- Self-Correction（修改子句而非字符串拼接）
- 方言转换（MySQL ↔ PostgreSQL）

候选方案：SQLGlot、SQLParse、自己写正则解析。

**决策**:
采用 sqlglot 作为统一 SQL 处理引擎。

**理由**:
1. sqlglot 支持 AST 级操作（增删 WHERE 条件、移除 SELECT 列），无需字符串拼接
2. 内置 MySQL/PostgreSQL/ClickHouse/Doris 等方言转译
3. Python 原生库，与 FastAPI 技术栈无缝集成
4. 活跃社区，持续更新新方言支持

**后果**:
- (+) RBAC 注入精确到 AST 级别，避免 SQL 注入风险
- (+) Self-Correction 可针对性修改出错子句
- (-) 学习曲线：团队需要熟悉 sqlglot AST 节点操作
- (-) 复杂 SQL（如递归 CTE）的支持可能不完善

---

## ADR-002: Phase1 合并部署 7 个微服务为 3 个进程

**状态**: 已采纳（Phase2 将拆分）

**背景**:
DataPilot 架构设计了 7 个微服务（Agent、Semantic、SQL Generator、Query Executor、Auth、Guardrail、Session），但 Phase1 团队只有 7 人，完全拆分会导致：
- 运维成本高：7 个进程 + 7 份配置
- 部署复杂：CI/CD、健康检查、日志聚合
- 本地开发困难：需要启动多个服务

**决策**:
Phase1 将 7 个服务合并为 3 个进程部署：
1. **API 进程**: Agent + Auth + Session + Guardrail（端口 8000）
2. **Core 进程**: Semantic + SQL Generator（端口 8001）
3. **Executor 进程**: Query Executor（端口 8002）

**理由**:
1. 代码层面保持模块独立（各服务是独立 Python 包），通过接口通信
2. Phase1 使用进程内调用替代 gRPC/HTTP，Phase2 切换为远程调用
3. 减少 DevOps 复杂度，团队可聚焦业务逻辑

**后果**:
- (+) 部署简化为 3 个 Docker 容器
- (+) 本地开发只需启动 2 个进程（API + Core，Executor 可合并）
- (-) 进程间需要切换通信方式，Phase1→Phase2 需要适配层
- (-) 资源隔离性较差，一个模块的 bug 可能影响同进程的其他模块

---

## ADR-003: 使用 PostgreSQL + pgvector 作为向量存储

**状态**: 已采纳

**背景**:
NL2SQL 需要向量相似度搜索来匹配语义元素（指标、维度、表）与用户问题。

候选方案：
- 独立向量数据库（Milvus、Qdrant、Weaviate）
- PostgreSQL + pgvector 扩展
- Redis + RediSearch 向量功能

**决策**:
采用 PostgreSQL + pgvector 作为统一存储。

**理由**:
1. 减少基础设施组件：不需要额外部署和维护独立向量数据库
2. pgvector 支持 IVFFlat 和 HNSW 索引，性能满足当前数据量级（千级向量）
3. 事务一致性：向量与结构化数据在同一个事务中更新
4. 团队已有 PostgreSQL 运维经验

**后果**:
- (+) 基础设施简单，运维成本低
- (+) 事务一致性保证
- (-) 大规模场景（百万级向量）性能可能不如专用向量数据库
- (-) 需要手动管理 IVFFlat 索引的聚类（CREATE INDEX 后需要训练）
- (~) Phase2 数据量增长后可能需要迁移到 Milvus

---

## ADR-004: 使用 RocketMQ 作为消息队列

**状态**: 已采纳

**背景**:
系统需要异步事件通信：查询审计日志、大结果集处理、缓存失效等。

候选方案：
- RocketMQ
- RabbitMQ
- Kafka
- Redis Streams

**决策**:
采用 RocketMQ。

**理由**:
1. 阿里云生态成熟，团队有运维经验
2. 支持延迟消息（审计日志归档）、事务消息
3. 适合业务消息场景（vs Kafka 更适合日志流）

**后果**:
- (+) 延迟消息支持审计日志归档调度
- (+) 团队熟悉度高
- (-) Phase1 合并部署模式下，大部分消息可通过进程内调用替代，RocketMQ 使用场景有限
- (~) Phase2 拆分后 RocketMQ 使用量会显著增加

---

## ADR-005: LLM 模型选型 — 国产模型优先

**状态**: 已采纳

**背景**:
NL2SQL 场景对中文理解能力要求高，且涉及数据安全合规。

候选方案：
- OpenAI GPT-4
- 国产模型（DeepSeek、通义千问）
- 开源自部署（Llama、Qwen-开源版）

**决策**:
采用国产模型，DeepSeek-V3 为主力 + 通义千问系列为辅助。

**理由**:
1. 中文理解能力强，对中文业务术语（"营收"、"同比"、"环比"）理解优于英文模型
2. 数据安全：国产模型可部署在国内服务器，满足数据不出境要求
3. 成本优势：DeepSeek-V3 的 Token 价格远低于 GPT-4
4. OpenAI 兼容 API：所有模型提供 OpenAI 兼容接口，代码层统一

**后果**:
- (+) 成本可控，适合高频 NL2SQL 场景
- (+) 中文语义理解好
- (-) 复杂推理能力（如多跳关联、嵌套子查询）可能弱于 GPT-4
- (-) 模型更新可能引入兼容性问题，需要版本锁定

---

## ADR-006: 使用 MinIO 存储大结果集

**状态**: 已采纳

**背景**:
查询结果可能超过 1MB（大结果集），直接通过 HTTP 响应传输不现实。

候选方案：
- MinIO（S3 兼容）
- Redis 大 Value
- 数据库临时表
- 文件系统

**决策**:
采用 MinIO，超过 1MB 的结果自动卸载。

**理由**:
1. S3 兼容，API 标准化
2. 支持预签名 URL，前端可直接下载
3. 可配置生命周期策略，自动清理过期结果
4. Docker 部署简单

**后果**:
- (+) 大结果集不占用数据库连接
- (+) 预签名 URL 减少后端流量
- (-) 增加基础设施复杂度（MinIO）
- (-) 查询结果有短暂延迟（写入 MinIO 的时间）

---

## ADR-007: 自建 Prompt 管理而非使用 LangChain

**状态**: 已采纳

**背景**:
NL2SQL 需要 Prompt 版本管理、A/B 测试、Token 预算控制。

候选方案：
- LangChain + LangSmith
- 自建 PromptManager
- 纯配置文件

**决策**:
自建 PromptManager 模块（`libs/datapilot-prompt`）。

**理由**:
1. LangChain 引入过多的间接抽象层，增加调试难度
2. 自建可精准控制 Token 预算和 Prompt 结构
3. A/B 测试与业务强相关，自建更灵活
4. Phase1 功能需求明确，不需要 LangChain 的通用能力

**后果**:
- (+) 精准控制 Prompt 结构和 Token 预算
- (+) 调试简单，无黑盒
- (+) A/B 测试与业务无缝集成
- (-) 需要自行实现版本管理和测试分流逻辑
- (-) 无法使用 LangSmith 等现成工具的追踪能力

---

## ADR-008: 前端使用 zustand 而非 Redux

**状态**: 已采纳

**背景**:
前端需要管理会话列表、当前会话、SSE 流式响应、用户信息等状态。

候选方案：
- Redux Toolkit
- zustand
- Jotai

**决策**:
采用 zustand。

**理由**:
1. API 极简，学习成本低，新团队快速上手
2. 无 Provider 包裹，组件外可访问 store
3. 天然支持 TypeScript
4. 代码量少，适合中小规模前端应用

**后果**:
- (+) 上手快，代码简洁
- (+) 与 React 18 并发模式兼容好
- (-) 大规模应用的状态管理可能不如 Redux Toolkit 成熟
- (-) DevTools 不如 Redux DevTools 功能丰富

---

## ADR-009: 使用 SSE 而非 WebSocket 进行 Chat 流式响应

**状态**: 已采纳

**背景**:
Chat 场景需要流式返回 AI 回复内容。

候选方案：
- SSE (Server-Sent Events)
- WebSocket

**决策**:
Chat 场景使用 SSE，其他场景（如 DAG 进度）使用 WebSocket。

**理由**:
1. SSE 是单向推送（服务端→客户端），匹配 Chat 场景
2. 浏览器原生支持 EventSource API
3. 实现简单，不需要心跳和重连逻辑（浏览器自动重连）
4. SSE 自动携带 Cookie/Authorization，认证更简单
5. WebSocket 保留给需要双向通信的场景（Phase2 DAG 编辑器）

**后果**:
- (+) 实现简单，前端代码少
- (+) 自动重连和事件 ID 追踪
- (-) SSE 不支持二进制传输
- (-) HTTP/1.1 下有连接数限制（HTTP/2 不受影响）

---

## ADR-010: 使用 APISIX 作为 API 网关

**状态**: 已采纳

**背景**:
需要统一的 API 入口、认证、限流、日志。

候选方案：
- APISIX
- Kong
- Nginx + Lua
- Spring Cloud Gateway

**决策**:
采用 APISIX。

**理由**:
1. 国产开源，中文社区活跃
2. 基于 Nginx/OpenResty，性能优秀
3. 插件丰富（JWT 认证、限流、日志、可观测性）
4. 支持 etcd 配置中心，动态配置无需重启

**后果**:
- (+) 统一入口，简化认证和限流
- (+) 插件生态丰富
- (-) 增加一层网络跳转（延迟约 1-2ms）
- (-) 需要维护 APISIX 配置

---

## ADR-011: 产品授权文件控制（License File）

**状态**: 已采纳

**背景**:
DataPilot 作为企业级产品交付给客户部署，需要防止未授权使用。需要在服务启动时和请求处理时进行授权校验。

候选方案：
- 授权文件（license.json）+ HMAC 签名
- 在线激活（联网验证）
- USB Dongle 硬件加密狗

**决策**:
Phase1 采用授权文件 + HMAC-SHA256 签名，IP 白名单 + 有效期校验。Phase2 可升级为在线激活 + 机器指纹。

**理由**:
1. 授权文件方案简单可靠，离线环境也能工作
2. HMAC-SHA256 签名防篡改，实现成本低
3. IP 白名单 + 有效期满足大多数企业交付场景
4. CLI 工具生成授权文件，内部管理方便
5. 后续可平滑升级（加机器指纹、在线验证、RSA 签名等）

**后果**:
- (+) 实现简单，不依赖外部服务
- (+) 离线环境兼容
- (+) Phase2 可渐进式升级
- (-) 授权文件需要手动分发和管理
- (-) Phase1 无法防止授权文件在多台机器上复制（Phase2 通过机器指纹解决）

---

## ADR 模板

新增 ADR 时使用以下模板：

```markdown
## ADR-XXX: [决策标题]

**状态**: [已采纳 / 已废弃 / 被替代 by ADR-XXX]

**背景**:
[描述面临的决策背景和问题]

**候选方案**:
1. [方案 A]
2. [方案 B]
3. [方案 C]

**决策**:
[选择哪个方案]

**理由**:
[为什么选择这个方案]

**后果**:
- (+) [正面影响]
- (-) [负面影响]
- (~) [中性影响]
```

提交 ADR 到 `docs/guides/adr-records.md`，并更新本索引。
