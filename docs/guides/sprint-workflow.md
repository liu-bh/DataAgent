# Sprint 工作流与看板模板

> 本文档定义 Sprint 执行流程、看板管理规范、DOD（Definition of Done）检查清单。

## 1. Sprint 周期

| 项目 | 说明 |
|------|------|
| Sprint 时长 | 2 周（Phase1） |
| Sprint 规划会 | Sprint 第一天，1.5 小时 |
| 每日站会 | 每天 9:30，15 分钟 |
| Sprint Review | Sprint 最后一天下午，1 小时 |
| Sprint Retro | Sprint Review 之后，30 分钟 |

## 2. 看板列定义

```
Todo ──────► In Progress ──────► In Review ──────► Done
                                                  │
                                            ┌─────▼─────┐
                                            │  Blocked  │
                                            └───────────┘
```

| 列 | 含义 | 规则 |
|----|------|------|
| **Todo** | 已规划但未开始 | Sprint Planning 后填入 |
| **In Progress** | 正在开发 | 每人同时最多 2 个 |
| **In Review** | 开发完成，等待 CR | 必须关联 PR 链接 |
| **Blocked** | 被外部依赖阻塞 | 必须注明阻塞原因和责任人 |
| **Done** | 已合并到目标分支 | 必须通过 DOD 检查 |

### WIP 限制

| 角色类型 | In Progress 上限 | In Review 上限 |
|---------|----------------|--------------|
| 后端开发 | 2 | 2 |
| 前端开发 | 2 | 2 |
| 全栈 | 3 | 3 |

## 3. Issue 状态流转

```
Open → In Progress → In Review → Done
  │        │
  └──► Blocked ──► In Progress (解除阻塞后)
```

### 状态说明

| 状态 | 何时进入 | 必须包含 |
|------|---------|---------|
| Open | Issue 创建时 | 标题、描述、验收标准、优先级 |
| In Progress | 开发者认领时 | Assignee、关联 Sprint |
| In Review | PR 创建时 | PR 链接、自测结果 |
| Done | PR 合并后 | 合并 Commit SHA |
| Blocked | 遇到阻塞时 | 阻塞原因、依赖方 |

## 4. 任务拆分原则

### 4.1 单个 Issue 粒度

| 维度 | 建议 |
|------|------|
| 工作量 | 1-3 天（最大不超过 5 天） |
| 影响范围 | 单一服务或单一前端模块 |
| 可独立验证 | 有明确的验收标准 |
| 可独立交付 | 不依赖其他未完成的 Issue |

### 4.2 拆分方式

```
大需求 → 按功能拆分
  例: "RBAC 权限系统" →
    ├─ Issue A: 行级权限 AST 注入
    ├─ Issue B: 列级权限 AST 移除
    ├─ Issue C: 数据脱敏规则
    └─ Issue D: 操作权限校验

大需求 → 按层次拆分
  例: "NL2SQL 核心" →
    ├─ Issue A: LLM 抽象层
    ├─ Issue B: Schema Linking
    ├─ Issue C: SQL AST Builder
    └─ Issue D: 端到端集成

大需求 → 按前后端拆分
  例: "查询历史功能" →
    ├─ Issue A (后端): 查询历史 API
    └─ Issue B (前端): 查询历史 UI
```

## 5. DOD（Definition of Done）检查清单

### 5.1 所有 Issue 通用 DOD

- [ ] 代码已编写且符合编码规范
- [ ] 单元测试已编写且通过
- [ ] `uv run ruff check .` 通过
- [ ] `uv run ruff format --check .` 通过
- [ ] 代码审查已通过（至少 1 人 Approve）
- [ ] PR 已合并到目标分支
- [ ] 关联的 Issue 已关闭

### 5.2 后端 Issue 附加 DOD

- [ ] API 端点可通过 Swagger UI 测试
- [ ] 数据库变更有 Alembic 迁移文件
- [ ] 新增业务表包含 `tenant_id` 字段
- [ ] 错误场景有正确的错误码和错误消息
- [ ] OpenAPI 文档已更新

### 5.3 前端 Issue 附加 DOD

- [ ] `pnpm lint` 通过
- [ ] `pnpm type-check` 通过
- [ ] `pnpm format:check` 通过
- [ ] TypeScript 类型定义已更新（如有 API 变更）
- [ ] MSW Mock 已更新（如有 API 变更）
- [ ] 加载态/错误态已处理
- [ ] 在 Chrome + Firefox 下验证通过

### 5.4 跨端 Issue 附加 DOD

- [ ] 前后端联调通过
- [ ] API 契约文档已同步
- [ ] E2E 测试已更新（如适用）

## 6. 每日站会模板

每人回答 3 个问题（15 分钟内完成）：

```
1. 昨天完成了什么？
   - Issue #12: 完成了行级权限 AST 注入，已提交 PR

2. 今天计划做什么？
   - Issue #13: 开始列级权限 AST 移除
   - Review Issue #10 的 PR

3. 有什么阻塞？
   - Issue #13 需要等 Issue #11 的 Schema Linking 完成（预计明天解除）
```

## 7. Sprint Review 模板

### 7.1 Review 会议议程（1 小时）

```
1. Sprint 目标回顾（5 min）
   - 本 Sprint 的目标是什么？
   - 是否达成？

2. Demo 演示（30 min）
   - 每个完成的 Issue 简要演示
   - 重点演示端到端功能

3. 数据指标回顾（10 min）
   - 完成 Issue 数 / 总 Issue 数
   - 代码行数变更
   - Bug 数量
   - 测试覆盖率变化

4. 未完成项分析（10 min）
   - 哪些 Issue 未完成？原因？
   - 是否需要调整 Sprint 计划？

5. 下个 Sprint 预告（5 min）
   - 下个 Sprint 的目标
   - 需要提前准备的依赖
```

### 7.2 Sprint Review 报告模板

```markdown
# Sprint X Review 报告

## Sprint 信息
- Sprint: X (Phase1)
- 时间: YYYY-MM-DD ~ YYYY-MM-DD
- 目标: [一句话描述]

## 完成情况

| 指标 | 数值 |
|------|------|
| 计划 Issue | N |
| 完成 Issue | N |
| 完成率 | N% |
| 新增 Bug | N |
| 修复 Bug | N |

## 完成的功能
- Issue #1: [功能描述]
- Issue #2: [功能描述]

## 未完成的功能
- Issue #3: [原因分析]

## 风险与问题
- [描述]
```

## 8. Sprint Retro 模板（30 分钟）

### 8.1 Retro 格式

使用"开始/停止/继续"格式：

```
开始做（What to Start）:
- [ ] ...

停止做（What to Stop）:
- [ ] ...

继续做（What to Continue）:
- [ ] ...
```

### 8.2 行动项跟踪

每次 Retro 产出的行动项必须：
- 有明确的责任人
- 有截止日期
- 下一轮 Retro 回顾执行情况

## 9. 优先级定义

| 优先级 | 标签 | 含义 | 响应时间 |
|--------|------|------|---------|
| **P0 - 紧急** | `p0-critical` | 线上故障、安全漏洞 | 立即响应 |
| **P1 - 高** | `p1-high` | Sprint 内必须完成 | 当天响应 |
| **P2 - 中** | `p2-medium` | 计划内任务 | 2 天内响应 |
| **P3 - 低** | `p3-low` | 改进优化 | 下个 Sprint 安排 |

## 10. Issue 模板快捷创建

```markdown
## Bug 报告
标题: [Bug] {简短描述}
标签: bug, p{优先级}
必须: 复现步骤、预期行为、实际行为、环境信息

## 功能需求
标题: [Feature] {简短描述}
标签: enhancement, p{优先级}
必须: 功能描述、验收标准、优先级

## 开发任务
标题: [Task] {简短描述}
标签: task, sprint-{N}
必须: 描述、拆分子任务、关联 Issue、验收标准
```
