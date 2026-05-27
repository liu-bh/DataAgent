.PHONY: help dev infra infra-down lint format test migrate-up migrate-down

help: ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================
# 基础设施
# ============================================

infra: ## 启动基础设施（PG + Redis + MinIO + Prometheus + Grafana + Jaeger）
	docker compose -f docker-compose.dev.yml up -d

infra-down: ## 停止基础设施
	docker compose -f docker-compose.dev.yml down

infra-ps: ## 查看基础设施状态
	docker compose -f docker-compose.dev.yml ps

infra-logs: ## 查看基础设施日志
	docker compose -f docker-compose.dev.yml logs -f

# ============================================
# 后端服务
# ============================================

dev-agent: ## 启动 Agent Service（开发模式）
	cd services/agent-service && uv run python -m datapilot_agent.main

dev-semantic: ## 启动 Semantic Service（开发模式）
	cd services/semantic-service && uv run python -m datapilot_semantic.main

dev-sqlgen: ## 启动 SQL Generator Service（开发模式）
	cd services/sql-generator-service && uv run python -m datapilot_sqlgen.main

dev-queryexec: ## 启动 Query Executor Service（开发模式）
	cd services/query-executor-service && uv run python -m datapilot_queryexec.main

dev-guardrail: ## 启动 Guardrail Service（开发模式）
	cd services/guardrail-service && uv run python -m datapilot_guardrail.main

dev-session: ## 启动 Session Service（开发模式）
	cd services/session-service && uv run python -m datapilot_session.main

dev-auth: ## 启动 Auth Service（开发模式）
	cd services/auth-service && uv run python -m datapilot_auth.main

# ============================================
# 代码质量
# ============================================

lint: ## 运行 Ruff Lint
	uv run ruff check .

format: ## 运行 Ruff 格式化
	uv run ruff format .

format-check: ## 检查 Ruff 格式化
	uv run ruff format --check .

typecheck: ## 运行 mypy 类型检查
	uv run mypy services/agent-service/src/
	uv run mypy services/semantic-service/src/
	uv run mypy services/auth-service/src/

# ============================================
# 测试
# ============================================

test: ## 运行单元测试
	uv run pytest tests/unit/ -v

test-integration: ## 运行集成测试（需要基础设施）
	uv run pytest tests/integration/ -v

test-all: ## 运行全部测试
	uv run pytest tests/ -v

test-cov: ## 运行测试并生成覆盖率报告
	uv run pytest tests/unit/ -v --cov --cov-report=html

# ============================================
# 数据库迁移
# ============================================

migrate-up: ## 执行数据库迁移
	cd services/auth-service && uv run alembic upgrade head
	cd services/semantic-service && uv run alembic upgrade head

migrate-down: ## 回滚数据库迁移（一个版本）
	cd services/auth-service && uv run alembic downgrade -1
	cd services/semantic-service && uv run alembic downgrade -1

migrate-create: ## 创建新迁移文件（用法: make migrate-create name=add_users）
	cd services/auth-service && uv run alembic revision --autogenerate -m "$(name)"

# ============================================
# 前端
# ============================================

dev-frontend: ## 启动前端开发服务器
	cd web && pnpm dev

frontend-lint: ## 前端 Lint
	cd web && pnpm lint

frontend-format: ## 前端格式化
	cd web && pnpm format

# ============================================
# 工具
# ============================================

install: ## 安装全部依赖
	uv sync
	cd web && pnpm install

license-generate: ## 生成授权文件（用法: make license-generate licensee="xxx" days=365）
	uv run python -m datapilot_license.cli generate \
		--licensee "$(licensee)" \
		--ips "$(ips)" \
		--days "$(days)"

clean: ## 清理生成文件
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null
	find . -type f -name "*.pyc" -delete 2>/dev/null
	rm -rf .coverage coverage.xml
