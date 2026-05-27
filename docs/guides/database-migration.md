# 数据库迁移工作流（Alembic）

> 本文档定义 Alembic 数据库迁移的规范流程，确保 Schema 变更可控、可回滚、可审计。

## 1. 迁移文件管理

### 1.1 目录结构

```
services/
├── semantic-service/
│   └── alembic/
│       ├── versions/              # 迁移文件存放目录
│       │   ├── 0001_initial_schema.py
│       │   ├── 0002_add_metrics_version.py
│       │   └── ...
│       ├── env.py                 # Alembic 环境配置
│       ├── script.py.mako         # 迁移模板
│       └── alembic.ini            # Alembic 配置
└── auth-service/
    └── alembic/
        └── versions/
```

### 1.2 文件命名规则

```
{序号}_{简短描述}.py

示例:
0001_initial_schema.py
0002_add_metrics_version.py
0003_add_data_masking_rules.py
0004_add_datasource_health.py
```

命名规范：
- 使用 4 位序号前缀（`0001`, `0002`）
- 描述使用 `snake_case`
- 描述以动词开头（`add_`, `remove_`, `alter_`, `create_`, `drop_`）
- 单次迁移只做一件事（一个表或一组相关变更）

### 1.3 生成迁移文件

```bash
cd services/semantic-service

# 自动生成迁移（推荐）
uv run alembic revision --autogenerate -m "add_data_masking_rules"

# 手动创建空迁移（复杂变更）
uv run alembic revision -m "migrate_user_quotas_to_new_format"
```

## 2. 迁移编写规范

### 2.1 必须同时编写 upgrade 和 downgrade

```python
"""add data masking rules

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-27 14:30:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'data_masking_rules',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('tenant_id', sa.Uuid(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('datasource_id', sa.Uuid(), sa.ForeignKey('data_sources.id')),
        sa.Column('column_path', sa.VARCHAR(200), nullable=False),
        sa.Column('mask_type', sa.VARCHAR(20), nullable=False),
        sa.Column('mask_pattern', sa.VARCHAR(50)),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=sa.func.now()),
    )
    op.create_index(
        'ix_masking_rules_tenant_ds',
        'data_masking_rules',
        ['tenant_id', 'datasource_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_masking_rules_tenant_ds')
    op.drop_table('data_masking_rules')
```

### 2.2 编写规则

| 规则 | 说明 |
|------|------|
| 必须可回滚 | `downgrade()` 必须能完全撤销 `upgrade()` 的所有变更 |
| 不要合并迁移 | 每个 PR 独立的迁移文件，不要压缩历史 |
| 谨慎删除列 | 先标记废弃（add comment），下一版本再删除 |
| 大表加列用 `nullable` | 大表新增列必须允许 NULL 或设 DEFAULT |
| 索引并发创建 | PostgreSQL 大表用 `CREATE INDEX CONCURRENTLY` |

### 2.3 数据迁移 vs 结构迁移

**结构迁移**（推荐）：只改表结构

```python
def upgrade() -> None:
    op.add_column('users', sa.Column('display_name', sa.VARCHAR(100)))
```

**数据迁移**：需要迁移数据时，分两步提交

```python
# Step 1: 添加新列（结构迁移）
def upgrade() -> None:
    op.add_column('users', sa.Column('full_name', sa.VARCHAR(200)))

# Step 2: 填充数据（数据迁移，单独的迁移文件）
def upgrade() -> None:
    op.execute("""
        UPDATE users SET full_name = CONCAT(first_name, ' ', last_name)
        WHERE first_name IS NOT NULL AND last_name IS NOT NULL
    """)
```

## 3. 迁移执行流程

### 3.1 开发环境

```bash
# 查看当前版本
uv run alembic current

# 查看迁移历史
uv run alembic history --verbose

# 执行到最新版本
uv run alembic upgrade head

# 回滚一个版本
uv run alembic downgrade -1

# 回滚到指定版本
uv run alembic downgrade 0003

# 生成 SQL（不执行，用于审查）
uv run alembic upgrade head --sql
```

### 3.2 生产环境

```bash
# Step 1: 预审查生成的 SQL
uv run alembic upgrade head --sql > migration_review.sql

# Step 2: Review SQL 确认无误

# Step 3: 备份数据库（重要表）
pg_dump -h host -U datapilot -d datapilot -t users -t metrics > backup.sql

# Step 4: 执行迁移
uv run alembic upgrade head

# Step 5: 验证
uv run alembic current
```

## 4. PR 审查要求

### 4.1 迁移文件 Review 检查清单

- [ ] `upgrade()` 和 `downgrade()` 都已实现
- [ ] 文件命名符合规范
- [ ] 迁移不可与其他迁移冲突（检查 `down_revision`）
- [ ] 新增表/列有 `tenant_id`（业务表）
- [ ] 大表操作使用 `CONCURRENTLY`（索引创建）
- [ ] 没有数据丢失风险（或已确认可接受）
- [ ] 生成的 SQL 已审查（`alembic upgrade head --sql`）

### 4.2 禁止事项

| 禁止 | 原因 |
|------|------|
| `downgrade()` 留空 | 无法回滚 |
| 在迁移中写复杂业务逻辑 | 难以调试，应使用独立脚本 |
| 合并/压缩历史迁移 | 丢失变更记录 |
| 直接修改生产数据库 | 必须通过迁移文件 |
| 在 `downgrade` 中删除数据 | 回滚不应丢数据 |

## 5. 常见场景

### 5.1 新增业务表

```python
def upgrade() -> None:
    op.create_table(
        'nl2sql_examples',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        # ... 其他列
    )
    # tenant_id 索引（所有业务表必须）
    op.create_index('ix_nl2sql_examples_tenant', 'nl2sql_examples', ['tenant_id'])

def downgrade() -> None:
    op.drop_index('ix_nl2sql_examples_tenant')
    op.drop_table('nl2sql_examples')
```

### 5.2 新增列到现有表

```python
def upgrade() -> None:
    # 新增列必须 nullable 或有 DEFAULT
    op.add_column('messages', sa.Column('chart_spec', sa.JSONB(), nullable=True))

def downgrade() -> None:
    op.drop_column('messages', 'chart_spec')
```

### 5.3 重命名列

```python
def upgrade() -> None:
    op.alter_column('metrics', 'formula',
                    new_column_name='calculation',
                    existing_type=sa.Text())

def downgrade() -> None:
    op.alter_column('metrics', 'calculation',
                    new_column_name='formula',
                    existing_type=sa.Text())
```

### 5.4 大表添加索引

```python
def upgrade() -> None:
    # 大表（>100万行）使用 CONCURRENTLY，避免锁表
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_llm_logs_tenant_date
        ON llm_call_logs (tenant_id, created_at)
    """)

def downgrade() -> None:
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_llm_logs_tenant_date")
```

## 6. 迁移冲突处理

当多个分支同时添加迁移时可能出现 `down_revision` 冲突：

```bash
# 场景：两个分支各新增一个迁移，都指向同一个 base revision

# 方案 1（推荐）：rebase 后重新生成
git rebase main
# 解决冲突后，删除冲突的迁移文件，重新生成
uv run alembic revision --autogenerate -m "your_change"

# 方案 2：手动修改 down_revision
# 将较新的迁移的 down_revision 指向前一个迁移
```

## 7. 回滚演练

生产环境每季度执行一次回滚演练：

```bash
# 1. 记录当前版本
uv run alembic current > current_version.txt

# 2. 回滚到上一个版本
uv run alembic downgrade -1

# 3. 验证应用正常

# 4. 重新升级
uv run alembic upgrade head

# 5. 验证数据完整
```
