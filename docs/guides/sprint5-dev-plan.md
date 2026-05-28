# Sprint 5: Frontend + Phase1 收尾 — 并行开发计划

> 目标：完整用户体验，Phase1 集成验收
> 依赖：Sprint 1-4 全部后端 + 前端骨架

## 并行 Track 划分

### Track A: ECharts 图表 + 数据可视化

**目录隔离**: `web/packages/chat-ui/src/components/` + `web/packages/chat-ui/src/hooks/`
**无后端依赖**，前端独立开发。

| # | 任务 | 产出文件 |
|---|------|----------|
| A-1 | 图表组件 | `components/ChartPanel.tsx` — ECharts 封装（折线/柱/饼图自动识别） |
| A-2 | 图表类型推断 Hook | `hooks/useChartType.ts` — 根据数据列类型自动推荐图表类型 |
| A-3 | 图表配置工厂 | `utils/chartConfig.ts` — 各图表类型的 ECharts option 配置 |
| A-4 | 消息气泡集成 | 扩展 `MessageBubble.tsx` — 数据结果自动渲染图表 |
| A-5 | MSW Mock 更新 | 扩展 `mocks/handlers.ts` — 图表相关 Mock 数据 |

**图表自动识别规则**:
- 时间列 + 数值列 → 折线图（趋势）
- 维度列 + 数值列 → 柱状图（对比）
- 少量维度 + 数值列 → 饼图（占比）
- 用户可手动切换图表类型

---

### Track B: 查询历史 + 收藏 + 多轮上下文

**目录隔离**: `web/packages/chat-ui/src/stores/` + `web/packages/chat-ui/src/components/` + `web/packages/chat-ui/src/api/`
**依赖**: 已有 Session API

| # | 任务 | 产出文件 |
|---|------|----------|
| B-1 | 查询历史组件 | `components/QueryHistory.tsx` — 查询历史列表（时间/问题/SQL 摘要） |
| B-2 | 收藏组件 | `components/StarredQueries.tsx` — 收藏的查询列表 + 一键复用 |
| B-3 | Store 扩展 | 扩展 `chatStore.ts` — history 状态 + star/unstar actions + contextMessages（10 轮上下文） |
| B-4 | API 层 | `api/history.ts` — 查询历史 CRUD + 收藏 API |
| B-5 | 类型定义 | 扩展 `types/api.ts` — QueryHistory, StarredQuery 类型 |
| B-6 | MSW Mock | 扩展 `mocks/handlers.ts` — 历史/收藏 API Mock |
| B-7 | 侧边栏集成 | 扩展 `Sidebar.tsx` — 添加"历史"和"收藏"Tab |

**10 轮上下文策略**:
- `contextMessages` 保留最近 20 条消息（10 轮对话）
- 发送消息时附带 `contextMessages` 给后端
- 显示"已携带上下文"标识

---

### Track C: 新手引导 + UX 完善

**目录隔离**: `web/packages/chat-ui/src/components/` + `web/packages/chat-ui/src/pages/`
**无后端依赖**

| # | 任务 | 产出文件 |
|---|------|----------|
| C-1 | 新手引导组件 | `components/OnboardingGuide.tsx` — 首次登录引导（步骤提示 + 示例查询） |
| C-2 | 危险 SQL 确认 | `components/DangerSqlConfirm.tsx` — DDL/DROP 等危险操作确认对话框 |
| C-3 | 错误提示优化 | `components/ErrorFriendly.tsx` — 异常场景友好提示（未匹配指标/SQL超时/超出范围引导） |
| C-4 | 空状态页面 | `components/EmptyState.tsx` — 新会话空状态（推荐查询 + 快速开始） |
| C-5 | Chat 页面集成 | 扩展 `pages/Chat/index.tsx` — 集成引导、空状态、错误提示 |
| C-6 | 加载/错误态 Hook | `hooks/useAsyncAction.ts` — 通用异步操作 Hook（loading/error/retry） |
| C-7 | Store 扩展 | 扩展 `authStore.ts` — onboardingCompleted 状态 |

**新手引导流程**:
1. 欢迎语 + "DataPilot 可以帮你查询数据"
2. 展示 3 个示例查询按钮（点击直接发送）
3. "查看语义模型" 按钮
4. 完成引导后记录到 localStorage

---

### Track D: 业务指标大盘 + Admin 增强

**目录隔离**: `web/packages/admin-dashboard/src/`
**依赖**: Sprint 2 的 admin-dashboard 骨架

| # | 任务 | 产出文件 |
|---|------|----------|
| D-1 | 大盘概览页 | `pages/Dashboard/index.tsx` — DAU、查询频次、NL2SQL 准确率趋势 |
| D-2 | 指标卡片 | `components/MetricCard.tsx` — 指标卡片（数值 + 趋势箭头 + 对比） |
| D-3 | 趋势图表 | `components/TrendChart.tsx` — ECharts 折线图（查询频次/准确率） |
| D-4 | 热门指标排行 | `components/TopMetrics.tsx` — 热门查询指标排行 |
| D-5 | 用户查询分析 | `pages/Analytics/index.tsx` — 查询分布、编辑率、满意度统计 |
| D-6 | API 层 | `api/dashboard.ts` — 大盘数据 API |
| D-7 | MSW Mock | `mocks/handlers.ts` — 大盘数据 Mock |
| D-8 | 类型定义 | `types/dashboard.ts` — 大盘相关类型 |

---

### Track E: Phase1 集成验收 + E2E 测试

**目录隔离**: `tests/e2e/` + `tests/integration/` + 文档
**依赖**: 全部 Sprint 产出

| # | 任务 | 产出文件 |
|---|------|----------|
| E-1 | E2E 测试框架 | `tests/e2e/conftest.py` — Playwright 或 httpx AsyncClient 测试基础设施 |
| E-2 | API 集成测试 | `tests/integration/test_api_flow.py` — 端到端 API 链路测试（登录→创建会话→查询→获取结果） |
| E-3 | NL2SQL 集成测试 | `tests/integration/test_nl2sql_pipeline.py` — Pipeline 集成测试（mock LLM） |
| E-4 | Guardrail 集成测试 | `tests/integration/test_guardrail_flow.py` — 安全拦截集成测试 |
| E-5 | 3 个业务场景验证 | `tests/integration/test_scenarios/` — 销售数据查询/用户行为分析/库存统计 |
| E-6 | 熔断降级测试 | `tests/integration/test_degradation.py` — LLM 不可用降级验证 |
| E-7 | Phase1 交付文档 | `docs/guides/phase1-delivery.md` — Phase1 功能清单 + 部署指南 + 验收标准 |

---

## Track 间文件隔离矩阵

| 目录 | Track A | Track B | Track C | Track D | Track E |
|------|---------|---------|---------|---------|---------|
| `chat-ui/components/` | 写(ChartPanel) | 写(History/Starred) | 写(Onboarding/Errors) | - | - |
| `chat-ui/hooks/` | 写(useChartType) | - | 写(useAsyncAction) | - | - |
| `chat-ui/stores/` | - | 写(chatStore) | 写(authStore) | - | - |
| `chat-ui/api/` | - | 写(history.ts) | - | - | - |
| `chat-ui/types/` | - | 写(api.ts) | - | - | - |
| `chat-ui/mocks/` | 改(handlers) | 改(handlers) | - | - | - |
| `chat-ui/pages/Chat/` | - | - | 写(index.tsx) | - | - |
| `chat-ui/components/MessageBubble.tsx` | 改 | - | - | - | - |
| `chat-ui/components/Sidebar.tsx` | - | 改 | - | - | - |
| `admin-dashboard/` | - | - | - | **写** | - |
| `tests/integration/` | - | - | - | - | **写** |
| `tests/e2e/` | - | - | - | - | **写** |
| `docs/` | - | - | - | - | **写** |

**冲突风险点**:
- `chat-ui/stores/chatStore.ts`: Track B 扩展。**约定：仅 Track B 修改。**
- `chat-ui/stores/authStore.ts`: Track C 扩展。**约定：仅 Track C 修改。**
- `chat-ui/components/MessageBubble.tsx`: Track A 扩展。**约定：仅 Track A 修改。**
- `chat-ui/components/Sidebar.tsx`: Track B 扩展。**约定：仅 Track B 修改。**
- `chat-ui/mocks/handlers.ts`: Track A 和 Track B 都追加。**约定：各自在末尾追加不同 handler，不冲突。**
- `chat-ui/types/api.ts`: Track B 扩展。**约定：仅 Track B 修改。**

## 验证方式

- Track A: `cd web && pnpm --filter chat-ui build`（TypeScript 编译通过）
- Track B: `cd web && pnpm --filter chat-ui build`
- Track C: `cd web && pnpm --filter chat-ui build`
- Track D: `cd web && pnpm --filter admin-dashboard build`
- Track E: `uv run pytest tests/integration/ -v`
