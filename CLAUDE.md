# DataPilot - 项目上下文

## 项目简介

DataPilot 是企业级 Semantic Data Agent，让业务人员通过自然语言查询数据。核心能力：NL2SQL、多数据源支持、语义模型管理、流式对话 + 可视化图表。

## 技术栈

- **后端**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), sqlglot
- **前端**: React 18, TypeScript, Vite, pnpm monorepo, zustand, Tailwind CSS, ECharts
- **数据库**: PostgreSQL 16 + pgvector (IVFFlat)
- **缓存**: Redis 7
- **消息队列**: Apache RocketMQ 5.x
- **LLM**: DeepSeek-V3 (复杂推理) + Qwen 系列 (Turbo/Plus/Max), OpenAI 兼容接口
- **向量**: pgvector IVFFlat, Embedding: text-embedding-v3
- **网关**: APISIX
- **监控**: Prometheus + Grafana + Loki + Jaeger (OpenTelemetry)
- **对象存储**: MinIO

## 项目结构

```
datapilot/
├── services/                # 微服务
│   ├── agent-service/       # 主服务 (Agent+Chat+SSE)
│   ├── semantic-service/    # 语义模型+元数据
│   ├── sql-generator-service/  # NL2SQL 核心
│   ├── query-executor-service/  # 多源查询执行
│   ├── guardrail-service/  # SQL 风险/权限
│   ├── session-service/    # 会话管理
│   └── auth-service/       # JWT/RBAC
├── libs/                    # 共享库
│   ├── datapilot-common/    # 配置/异常/日志/遥测
│   ├── datapilot-license/   # 产品授权 (IP白名单+有效期)
│   ├── datapilot-llm/       # LLM 抽象层+Provider+路由
│   ├── datapilot-prompt/    # Prompt 管理+版本化+A/B测试
│   ├── datapilot-sql/       # sqlglot AST封装+方言适配
│   └── datapilot-proto/     # gRPC Proto定义
├── web/                     # 前端 pnpm monorepo
│   └── packages/chat-ui/    # Chat UI
├── docs/                    # 文档
│   ├── guides/              # 操作指南 (12份)
│   └── *.md                 # 开发规范 (10份)
├── tests/                   # 测试
├── infra/                   # K8s/Docker/脚本
└── docker-compose.dev.yml
```

## 编码规范

### Python (后端)

- 包管理: `uv`
- 格式化/Lint: `ruff` (配置在 pyproject.toml)
- 类型注解: 全部函数必须有参数和返回值类型注解
- 异步: FastAPI 路由使用 `async def`, 数据库操作使用 SQLAlchemy async session
- Pydantic: 所有请求/响应模型继承 `BaseModel`, 使用 `model_config = ConfigDict(from_attributes=True)`
- SQLAlchemy: 使用声明式基类 `DeclarativeBase`, 多租户所有业务表携带 `tenant_id`
- SQL 操作: 不拼接字符串 SQL, 使用 sqlglot AST 构建
- 命名: 文件/模块 `snake_case`, 类 `PascalCase`, 函数/变量 `snake_case`, 常量 `UPPER_SNAKE_CASE`
- 错误处理: 自定义异常继承 `AppError`, FastAPI exception handler 统一捕获
- 日志: 使用 structlog, 结构化 JSON 输出

### TypeScript (前端)

- 包管理: `pnpm`
- 格式化: Prettier (`.prettierrc`)
- Lint: ESLint (`eslint.config.js`)
- 组件: 函数式组件 + Hooks, Props 使用 interface 定义
- 状态管理: zustand store
- 样式: Tailwind CSS 工具类优先
- 命名: 组件 `PascalCase.tsx`, 工具函数/Store `camelCase.ts`, 样式类 `kebab-case`

### 通用

- Git 提交: `type(scope): subject` 格式 (feat/fix/docs/refactor/test/chore)
- 语言: 注释和文档使用中文
- 多租户: 所有业务表/查询必须携带 `tenant_id`

## 核心架构约束

1. **SQL 必须走 AST**: 不拼接字符串 SQL, 通过 sqlglot AST 构建 → 方言转换 → 渲染输出
2. **RBAC 通过 AST 注入**: 行级权限用 AST 注入 WHERE, 列级权限用 AST 移除 SELECT 列
3. **LLM 通过抽象层调用**: 不直接调用模型 API, 通过 `datapilot-llm` 的 Provider 接口
4. **产品授权前置**: 服务启动时校验 license.json, 未授权拒绝启动
5. **大结果集分级缓存**: <1MB 存 Redis, ≥1MB 存 MinIO
6. **Phase1 合并部署**: 7 服务合并为 3 进程, 使用进程内调用替代 gRPC

## 文档索引

开发规范 (docs/):
- `python-standards.md` — P0, 后端规范
- `typescript-standards.md` — P0, 前端规范
- `api-standards.md` — P0, API 设计
- `database-standards.md` — P0, 数据库规范
- `git-workflow.md` — P0, Git 工作流
- `security-standards.md` — P1, 安全规范 (含产品授权)
- `service-communication.md` — P1, 服务通信
- `testing-standards.md` — P1, 测试规范
- `logging-standards.md` — P2, 日志监控
- `documentation-standards.md` — P2, 文档规范

操作指南 (docs/guides/):
- `local-dev-setup.md` — 本地环境搭建
- `environment-variables.md` — 环境变量参考
- `data-model.md` — 数据模型
- `api-contract.md` — API 契约
- `grpc-proto-definitions.md` — gRPC Proto 定义
- `semantic-model-registration.md` — 语义模型注册
- `datasource-onboarding.md` — 数据源接入
- `adr-records.md` — 架构决策记录
- `test-data-preparation.md` — 测试数据与评测
- `prompt-engineering.md` — Prompt 工程
- `troubleshooting.md` — 故障排查
- `onboarding.md` — 新成员入职

## 常用命令

```bash
# 基础设施
docker compose -f docker-compose.dev.yml up -d

# 后端 (每个服务目录下)
uv run python -m datapilot_{service}.main

# 前端
cd web && pnpm install && pnpm dev

# 代码检查
uv run ruff check . && uv run ruff format --check .
cd web && pnpm lint && pnpm format:check

# 测试
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v

# 数据库迁移
cd services/semantic-service && uv run alembic upgrade head
```

## 环境变量

关键环境变量 (各服务 .env):
- `AGENT_DATABASE_URL` / `SEMANTIC_DATABASE_URL` — PostgreSQL 连接串
- `AGENT_REDIS_URL` — Redis 连接串
- `DEEPSEEK_API_KEY` / `QWEN_API_KEY` — LLM API Key
- `JWT_SECRET_KEY` — JWT 签名密钥 (至少32字符)
- `LICENSE_FILE_PATH` — 授权文件路径, 默认 `./license.json`

完整参考: `docs/guides/environment-variables.md`
