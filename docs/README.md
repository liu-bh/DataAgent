# DataPilot 开发规范体系

## 适用范围

本规范适用于 DataPilot 项目全部开发成员，涵盖后端、前端、DevOps 各角色。
所有代码合入主分支前**必须符合本规范**，CI pipeline 会自动检查。

## 规范文档索引

| 文档 | 内容 | 优先级 |
|------|------|--------|
| [Python 后端规范](python-standards.md) | 命名、类型、异步、FastAPI/Pydantic/SQLAlchemy、**多租户、熔断降级** | **P0** |
| [TypeScript 前端规范](typescript-standards.md) | React 组件、Hooks、状态管理、样式、**游标分页、会话管理、数据新鲜度** | **P0** |
| [API 设计规范](api-standards.md) | RESTful、gRPC、错误码、版本管理、**大结果集响应** | **P0** |
| [数据库规范](database-standards.md) | 命名、迁移、索引、SQL 编写、pgvector、**多租户 tenant_id、新数据表** | **P0** |
| [Git 工作流](git-workflow.md) | 分支策略、提交规范、PR、Code Review | **P0** |
| [测试规范](testing-standards.md) | 单测/集成/E2E、覆盖率、mock、**NL2SQL 三档准确率、Phase1 额外测试场景** | **P1** |
| [安全规范](security-standards.md) | 认证鉴权、注入防护、沙箱、密钥管理、**数据脱敏规则、操作权限、查询配额** | **P1** |
| [微服务通信规范](service-communication.md) | gRPC、RocketMQ、SSE/WebSocket、**Phase1/Phase2 通信区别** | **P1** |
| [日志与监控规范](logging-standards.md) | 日志格式、链路追踪、Prometheus、告警、**LLM 指标、业务指标大盘** | **P2** |
| [文档规范](documentation-standards.md) | API 文档、架构文档、变更记录 | **P2** |

> **P0** = 强制执行，CI 门禁阻断 | **P1** = Code Review 检查 | **P2** = 推荐遵循

## 通用原则

1. **简洁优先**：代码能简单就不要复杂，能直接就不要间接
2. **一致性**：同一模块/服务的代码风格保持统一
3. **可读性 > 聪明度**：清晰的代码胜过 clever 的技巧
4. **安全默认**：所有对外接口默认需要认证，显式开放才可匿名
5. **渐进增强**：先跑通再优化，先单测再集成
6. **多租户意识**：所有业务表携带 `tenant_id`，Phase1 预留 Phase2 完整支持

## 工具链

| 用途 | 工具 | 配置文件 |
|------|------|---------|
| Python 格式化 | Ruff | `pyproject.toml` |
| Python Lint | Ruff | `pyproject.toml` |
| Python 类型检查 | mypy | `pyproject.toml` |
| TypeScript 格式化 | Prettier | `.prettierrc` |
| TypeScript Lint | ESLint | `eslint.config.js` |
| 提交检查 | pre-commit + husky | `.pre-commit-config.yaml` |
| Commit 规范 | commitlint | `.commitlintrc.json` |

## 版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.2 | 2026-05-27 | 补充产品授权错误码、更新环境变量 |
| v1.1 | 2026-05-27 | 同步开发方案更新：多租户、LLM 指标、脱敏规则、分页、Phase 通信区别 |
| v1.0 | 2026-05-27 | 初始版本 |
