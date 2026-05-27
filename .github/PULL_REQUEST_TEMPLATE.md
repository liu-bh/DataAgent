## 变更类型

- [ ] feat: 新功能
- [ ] fix: Bug 修复
- [ ] docs: 文档更新
- [ ] refactor: 代码重构
- [ ] test: 测试相关
- [ ] chore: 构建/工具变更
- [ ] perf: 性能优化
- [ ] ci: CI/CD 变更

## 变更说明

<!-- 描述本次 PR 的变更内容 -->

## 关联 Issue

Closes #
Related to #

## 影响范围

| 模块 | 变更 | Breaking Change |
|------|------|----------------|
| 后端 | | |
| 前端 | | |
| 数据库 | | |
| 文档 | | |

## 测试情况

- [ ] 单元测试通过 (`uv run pytest tests/unit/ -v`)
- [ ] 代码检查通过 (`uv run ruff check .`)
- [ ] 前端检查通过 (`cd web && pnpm lint`)
- [ ] 手动验证通过
- [ ] 新增/更新测试用例

### 测试详情

<!-- 描述测试方法和结果 -->

## 检查清单

- [ ] 遵循编码规范 (`docs/python-standards.md` / `docs/typescript-standards.md`)
- [ ] 无硬编码的敏感信息（API Key、密码等）
- [ ] 数据库变更有对应的 Alembic 迁移文件
- [ ] API 变更更新了 OpenAPI 文档
- [ ] 多租户 `tenant_id` 已处理（如涉及业务表）
- [ ] 大结果集已处理分页/缓存（如涉及查询）
- [ ] 异常场景有友好提示

## 截图（如有 UI 变更）

<!-- 粘贴截图 -->

## 备注

<!-- 其他需要 Reviewer 关注的事项 -->
