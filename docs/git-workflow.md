# Git 工作流规范

## 1. 分支策略

### 1.1 分支类型

| 分支 | 命名 | 生命周期 | 保护 |
|------|------|---------|------|
| `main` | `main` | 永久 | 强制 PR + CI 通过 + 1 人 Review |
| `develop` | `develop` | 永久 | 强制 PR + CI 通过 |
| `release/*` | `release/v1.0.0` | 临时 | 强制 PR |
| `feature/*` | `feature/DP-123-add-metric-model` | 临时 | - |
| `bugfix/*` | `bugfix/DP-456-sql-injection-fix` | 临时 | - |
| `hotfix/*` | `hotfix/DP-789-auth-bypass` | 临时 | 强制 PR |

### 1.2 分支流程

```
main ─────────────────────────────────── merge (tag) ────
  │                                          ▲
  └── develop ───────────────────────────────┘
        │           │              │
        ▼           ▼              ▼
   feature/*   feature/*     release/*
        │           │              │
        └──── merge ──┘────────────┘
```

**规则：**
- `feature/*` 从 `develop` 创建，完成后合回 `develop`
- `release/*` 从 `develop` 创建，测试通过后合回 `main` + `develop`
- `hotfix/*` 从 `main` 创建，修复后合回 `main` + `develop`
- 禁止直接 push 到 `main`/`develop`，必须走 PR
- 禁止在公共分支上 rebase

### 1.3 分支命名

```
feature/<JIRA-ID>-<简要描述>
bugfix/<JIRA-ID>-<简要描述>
hotfix/<JIRA-ID>-<简要描述>
release/v<major>.<minor>.<patch>
```

- 使用 kebab-case
- 描述不超过 50 个字符
- 示例：`feature/DP-123-add-semantic-search`, `bugfix/DP-456-fix-sql-dialect`

## 2. Commit 规范

### 2.1 Commit Message 格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

**type（必填）：**

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 Bug |
| `refactor` | 重构（不改变行为） |
| `perf` | 性能优化 |
| `docs` | 文档变更 |
| `style` | 代码格式（不影响逻辑） |
| `test` | 测试相关 |
| `chore` | 构建/CI/工具变更 |
| `ci` | CI/CD 配置变更 |

**scope（可选）：** 影响的模块，如 `semantic`, `sqlgen`, `chat-ui`, `auth`

**subject（必填）：** 简要描述，不超过 72 字符，使用祈使句

### 2.2 示例

```
feat(semantic): add hybrid retrieval with RRF reranking

implement vector + keyword hybrid search with Reciprocal Rank
Fusion reranking for semantic model retrieval.

Refs: DP-123
```

```
fix(sqlgen): correct dialect conversion for StarRocks DATE_ADD

The sqlglot AST was generating DATE_ADD with wrong argument order
for StarRocks dialect. Fixed by adding dialect-specific transform.

Fixes: DP-456
```

### 2.3 规则

- 每次提交只做一件事（不混合多个不相关的变更）
- 提交前运行 `ruff check` + `ruff format`（Python）或 `eslint + prettier`（TS）
- 提交信息不使用 emoji
- 禁止 `git push --force` 到公共分支
- 禁止提交 `__pycache__/`, `.venv/`, `node_modules/`, `.env`

### 2.4 配置

项目配置 commitlint 自动检查：

```json
// .commitlintrc.json
{
  "extends": ["@commitlint/config-conventional"],
  "rules": {
    "type-enum": [2, "always", [
      "feat", "fix", "refactor", "perf", "docs", "style", "test", "chore", "ci"
    ]],
    "subject-max-length": [2, "always", 72]
  }
}
```

## 3. Pull Request 规范

### 3.1 PR 标题

```
[<JIRA-ID>] <type>: <简要描述>
```

示例：`[DP-123] feat(semantic): add hybrid retrieval with RRF reranking`

### 3.2 PR 描述模板

```markdown
## 变更说明
<!-- 描述本次变更的内容和目的 -->

## 变更类型
- [ ] feat
- [ ] fix
- [ ] refactor
- [ ] perf

## 影响范围
<!-- 列出受影响的模块/服务 -->

## 测试
- [ ] 单元测试已通过
- [ ] 集成测试已通过
- [ ] 手动验证（描述验证步骤）

## 检查清单
- [ ] 代码符合开发规范
- [ ] 无硬编码配置
- [ ] 无敏感信息
- [ ] API 文档已更新（如有 API 变更）
- [ ] 数据库迁移已验证（如有 schema 变更）

## 关联
Closes DP-xxx
```

### 3.3 PR 规则

- 必须关联 JIRA issue
- 分支保持与目标分支同步（rebase 或 merge develop）
- PR 体量建议不超过 **400 行**，大变更拆分多个 PR
- 至少 **1 人** Code Review 通过
- CI 全部通过才可合并
- Reviewer 在 **2 个工作日内** 完成 Review

## 4. Code Review 规范

### 4.1 Review 重点

- **正确性**：逻辑是否正确，边界条件是否处理
- **安全性**：是否存在注入、权限绕过、信息泄露
- **性能**：N+1 查询、不必要的循环、缺失索引
- **可维护性**：命名是否清晰、复杂度是否合理
- **规范**：是否符合团队开发规范

### 4.2 Review 礼仪

- 使用建议性语气："是否可以考虑..." 而非 "这样写不对"
- 区分 blocking（必须修改）和 nit（建议优化）
- 大方向问题在 PR 早期提出，不要等最后才说
- 同意修改时直接 Approve，不要反复讨论

### 4.3 Review 时限

| 优先级 | Review 时限 | 示例 |
|--------|-----------|------|
| P0（紧急） | 4 小时 | hotfix、线上问题 |
| P1（重要） | 1 个工作日 | Sprint 核心功能 |
| P2（常规） | 2 个工作日 | 优化、重构 |

## 5. .gitignore 规范

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.env
*.egg

# Node
node_modules/
dist/
.next/

# IDE
.vscode/settings.json
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Secrets
*.pem
*.key
secrets/
```

## 6. Tag 与发布

- 格式：`v{major}.{minor}.{patch}`（语义化版本）
- `main` 合并后自动创建 tag（GitHub Actions）
- Release Note 由 PR 描述自动生成
- Tag 创建后触发镜像构建 + K8s 部署
