# 新成员入职指南

> 本文档帮助新加入 DataPilot 团队的成员快速了解项目、搭建环境、开始开发。

## 1. 项目概览

**DataPilot** 是一个企业级语义数据 Agent，让业务人员通过自然语言查询数据。

### 核心能力

- 自然语言转 SQL（NL2SQL）
- 多数据源支持（MySQL/PG/Doris/ClickHouse）
- 语义模型管理（指标/维度/表关系）
- 流式对话 + 可视化图表
- RBAC 权限 + 数据脱敏

### 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11, FastAPI, SQLAlchemy 2.0, sqlglot |
| 前端 | React 18, TypeScript, Vite, zustand, Tailwind CSS, ECharts |
| 数据库 | PostgreSQL 16 + pgvector |
| 缓存 | Redis |
| 消息队列 | RocketMQ |
| LLM | DeepSeek-V3, 通义千问 |
| 向量 | pgvector (IVFFlat) |
| 网关 | APISIX |
| 监控 | Prometheus + Grafana + Jaeger |

### 架构（Phase1）

```
用户 → APISIX → API 进程（Agent + Auth + Session + Guardrail）
                 → Core 进程（Semantic + SQL Generator）
                 → Executor 进程（Query Executor）
                 → PostgreSQL + Redis + MinIO
```

## 2. 第一天：环境搭建

### 2.1 获取权限

1. 申请 Git 仓库访问权限
2. 获取 LLM API Key（DeepSeek / 通义千问）
3. 获取开发环境 VPN/网络配置

### 2.2 安装工具

```bash
# 必须工具
Python >= 3.11
Node.js >= 20
pnpm >= 8
Docker >= 24
Git >= 2.40

# 推荐
uv (Python 包管理)
VS Code + Python/ESLint/Tailwind 扩展
```

> 详细安装步骤见 [本地开发环境搭建](local-dev-setup.md)

### 2.3 启动项目

```bash
# 1. 克隆仓库
git clone <仓库地址>
cd datapilot

# 2. 启动基础设施
docker compose -f docker-compose.dev.yml up -d

# 3. 安装后端依赖
uv sync

# 4. 复制环境变量
cp services/agent-service/.env.example services/agent-service/.env
# 编辑 .env 填入 API Key 等配置

# 5. 数据库迁移
cd services/semantic-service && uv run alembic upgrade head
cd services/auth-service && uv run alembic upgrade head

# 6. 启动后端
cd services/agent-service && uv run python -m datapilot_agent.main

# 7. 启动前端
cd web && pnpm install && pnpm dev
```

### 2.4 验证

- 后端 API 文档：http://localhost:8000/docs
- 前端 Chat UI：http://localhost:5173
- Jaeger 追踪：http://localhost:16686

## 3. 第二天：了解代码

### 3.1 目录结构

```
datapilot/
├── services/                    # 微服务
│   ├── agent-service/           # 主服务（Chat、Session、Auth、Guardrail）
│   ├── semantic-service/        # 语义模型管理
│   ├── sql-generator-service/   # SQL 生成与校验
│   └── query-executor-service/  # 查询执行
├── libs/                        # 共享库
│   ├── datapilot-common/        # 公共工具（配置、异常、中间件）
│   ├── datapilot-llm/           # LLM 客户端（多模型、熔断、成本追踪）
│   ├── datapilot-prompt/        # Prompt 管理（版本、A/B 测试）
│   ├── datapilot-sql/           # SQL 工具（sqlglot 封装、RBAC 注入）
│   └── datapilot-proto/         # gRPC Proto 定义
├── web/                         # 前端
│   └── packages/
│       └── chat-ui/             # Chat UI
├── docs/                        # 文档
│   ├── guides/                  # 操作指南
│   └── *.md                     # 开发规范
└── tests/                       # 测试
```

### 3.2 核心流程：一次 NL2SQL 查询的完整路径

```
用户输入 → Intent识别 → Schema Linking → SQL生成 → SQL校验 → 执行 → 响应
```

代码追踪（以 Agent Service 为入口）：

1. `agent-service/src/api/routes/chat.py` → 接收请求
2. `agent-service/src/services/intent_router.py` → 意图识别
3. `semantic-service/src/services/schema_linker.py` → 语义匹配
4. `sql-generator-service/src/services/sql_generator.py` → SQL 生成
5. `sql-generator-service/src/services/sql_validator.py` → SQL 校验
6. `query-executor-service/src/services/query_executor.py` → 执行查询
7. `agent-service/src/api/routes/chat.py` → 返回响应（SSE 或同步）

### 3.3 必读文档

按优先级阅读：

| 顺序 | 文档 | 内容 |
|------|------|------|
| 1 | `docs/guides/api-contract.md` | API 接口定义 |
| 2 | `docs/guides/data-model.md` | 数据模型 |
| 3 | `docs/guides/environment-variables.md` | 环境变量 |
| 4 | `docs/python-standards.md` | 后端编码规范 |
| 5 | `docs/typescript-standards.md` | 前端编码规范 |
| 6 | `docs/api-standards.md` | API 设计规范 |
| 7 | `docs/guides/semantic-model-registration.md` | 语义模型机制 |
| 8 | `docs/guides/prompt-engineering.md` | Prompt 工程 |
| 9 | `docs/guides/grpc-proto-definitions.md` | gRPC 定义 |
| 10 | `docs/guides/adr-records.md` | 架构决策 |

## 4. 第一周：完成入门任务

### 4.1 熟悉代码库

- 通读核心模块代码，理解 NL2SQL 流程
- 运行本地环境，完成一次完整的对话查询
- 阅读并理解单元测试

### 4.2 完成第一个 Issue

选择一个 `good-first-issue` 标签的任务：

```bash
# 创建开发分支
git checkout -b feature/issue-xxx

# 开发
# ...

# 运行代码检查
uv run ruff check .
uv run ruff format --check .

# 运行测试
uv run pytest tests/unit/ -v

# 提交
git add <files>
git commit -m "feat: xxx"

# 推送并创建 PR
git push origin feature/issue-xxx
```

### 4.3 提交规范

```
<type>(<scope>): <subject>

类型：
feat:     新功能
fix:      Bug 修复
docs:     文档
refactor: 重构
test:     测试
chore:    构建/工具

示例：
feat(sql-generator): 添加 JOIN 顺序优化
fix(chat): 修复 SSE 连接中断后不自动重连
docs(guide): 更新语义模型注册文档
```

## 5. 角色专属指引

### 后端开发

- 重点关注：FastAPI 路由、SQLAlchemy 模型、Pydantic Schema
- 核心规范：`docs/python-standards.md`、`docs/database-standards.md`
- 入口服务：`services/agent-service`
- 测试：`uv run pytest tests/unit/ -v`

### 前端开发

- 重点关注：React 组件、zustand Store、SSE 流式处理、ECharts
- 核心规范：`docs/typescript-standards.md`
- 入口：`web/packages/chat-ui/src/`
- 测试：`cd web && pnpm test`

### 数据/算法开发

- 重点关注：语义模型、NL2SQL Pipeline、Prompt 工程
- 核心规范：`docs/guides/prompt-engineering.md`、`docs/guides/test-data-preparation.md`
- 入口：`services/sql-generator-service`

## 6. 日常开发

### 分支策略

```
main (主分支，受保护)
├── feature/xxx (功能分支)
├── fix/xxx (修复分支)
└── release/v1.x (发布分支)
```

### 代码检查

```bash
# Python
uv run ruff check .
uv run ruff format --check .

# 前端
cd web && pnpm lint && pnpm format:check

# 提交前（pre-commit 自动执行）
pre-commit run --all-files
```

### 常用命令

```bash
# 启动基础设施
docker compose -f docker-compose.dev.yml up -d

# 启动后端（开发模式，自动热重载）
cd services/agent-service && uv run python -m datapilot_agent.main

# 启动前端
cd web && pnpm dev

# 运行测试
uv run pytest tests/unit/ -v

# 查看 API 文档
# http://localhost:8000/docs
```

## 7. 获取帮助

| 问题类型 | 找谁 / 去哪 |
|---------|------------|
| 业务逻辑 | 产品经理 / `docs/guides/` |
| 技术架构 | 技术负责人 / `docs/guides/adr-records.md` |
| 编码规范 | `docs/` 下的规范文档 |
| 开发环境问题 | `docs/guides/troubleshooting.md` |
| API 接口 | `docs/guides/api-contract.md` |
| 数据模型 | `docs/guides/data-model.md` |
