# 本地开发环境搭建指南

## 前置依赖

| 工具 | 版本 | 安装方式 |
|------|------|---------|
| Python | >= 3.11 | python.org 或 `pyenv install 3.11` |
| Node.js | >= 20 | https://nodejs.org |
| pnpm | >= 8 | `npm install -g pnpm` |
| Docker | >= 24 | https://docs.docker.com/get-docker/ |
| Docker Compose | >= 2.20 | Docker Desktop 自带 |
| Git | >= 2.40 | 系统自带或 git-scm.com |
| uv | >= 0.1 | `pip install uv` 或 https://docs.astral.sh/uv |

## 1. 克隆仓库

```bash
git clone <仓库地址> datapilot
cd datapilot
```

## 2. 启动基础设施（数据库/缓存/队列）

```bash
# 一键启动 PostgreSQL + Redis + RocketMQ + MinIO
docker compose -f docker-compose.dev.yml up -d

# 验证各服务健康
docker compose -f docker-compose.dev.yml ps

# PostgreSQL 连接测试（密码见 .env.example）
psql postgresql://datapilot:datapilot@localhost:5432/datapilot
```

## 3. 后端环境搭建

```bash
# 安装 uv（如未安装）
pip install uv

# 同步所有 Python 依赖（workspace 根目录的 pyproject.toml）
uv sync

# 初始化共享库
uv pip install -e libs/datapilot-common
uv pip install -e libs/datapilot-llm
uv pip install -e libs/datapilot-prompt
uv pip install -e libs/datapilot-sql
uv pip install -e libs/datapilot-proto

# 复制环境变量模板
cp services/agent-service/.env.example services/agent-service/.env
cp services/semantic-service/.env.example services/semantic-service/.env
cp services/sql-generator-service/.env.example services/sql-generator-service/.env
cp services/query-executor-service/.env.example services/query-executor-service/.env

# 编辑 .env 文件，填入实际的数据库连接串、Redis 地址等
# 注意：每个服务的 .env 中 DATASEMANTIC_DATABASE_URL 指向同一个 PG
```

### 3.1 数据库迁移

```bash
# 在每个有 Alembic 的服务目录下执行
cd services/semantic-service
uv run alembic upgrade head

cd services/auth-service
uv run alembic upgrade head
```

### 3.2 启动单个服务（开发模式）

```bash
# 启动 Semantic Service（开发模式，自动热重载）
cd services/semantic-service
uv run python -m datapilot_semantic.main
# 访问 http://localhost:8001/docs 查看 API 文档

# 启动 SQL Generator Service
cd services/sql-generator-service
uv run python -m datapilot_sqlgen.main
# 访问 http://localhost:8002/docs

# 启动 Agent Service
cd services/agent-service
uv run python -m datapilot_agent.main
# 访问 http://localhost:8000/docs
```

## 4. 前端环境搭建

```bash
cd web

# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev

# 访问 http://localhost:5173（Chat UI）
# 访问 http://localhost:5174（Admin Dashboard，如已配置）
```

## 5. 验证全部启动

```bash
# 1. 基础设施
curl http://localhost:5432          # PostgreSQL（无响应即正常，PG 不暴露 HTTP）
docker compose -f docker-compose.dev.yml ps  # 所有服务 Up

# 2. 后端 API
curl http://localhost:8000/health   # Agent Service 健康检查
curl http://localhost:8001/health   # Semantic Service
curl http://localhost:8002/health   # SQL Generator

# 3. 前端
curl http://localhost:5173          # Chat UI
```

## 6. 代码质量检查

```bash
# Python 格式化 + Lint（根目录执行，uv 会检查所有 workspace）
uv run ruff check .
uv run ruff format --check .

# Python 类型检查（逐步开启）
uv run mypy services/agent-service/src/

# 前端 Lint + 格式化
cd web && pnpm lint && pnpm format:check

# 提交检查（pre-commit）
pre-commit run --all-files
```

## 7. 常见问题

| 问题 | 解决方案 |
|------|---------|
| `uv sync` 失败 | 检查 Python 版本 >= 3.11；删除 `.venv/` 后重试 |
| PostgreSQL 连不上 | 检查 docker-compose 是否启动：`docker compose ps` |
| Redis 连不上 | 同上，检查 Redis 容器状态 |
| 端口被占用 | 修改 .env 中的端口配置，或 `lsof -i :8000` 查看占用进程 |
| pnpm install 慢 | 配置镜像源：`pnpm config set registry https://registry.npmmirror.com` |
| `alembic upgrade` 报错 | 确认 DATABASE_URL 指向正确的 PG 且已启动 |

## 8. 日常开发命令速查

```bash
# 启动基础设施
docker compose -f docker-compose.dev.yml up -d

# 启动某个后端服务（带热重载）
uv run python -m datapilot_{service}.main

# 运行单元测试
uv run pytest tests/unit/ -v

# 运行集成测试（需要基础设施）
uv run pytest tests/integration/ -v

# 前端开发
cd web && pnpm dev

# 代码检查
uv run ruff check . && uv run ruff format --check .
```
