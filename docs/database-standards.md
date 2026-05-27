# 数据库开发规范

## 1. 通用约定

- **数据库**：PostgreSQL 16（元数据存储） + pgvector 扩展
- **ORM**：SQLAlchemy 2.0 async
- **迁移工具**：Alembic
- **连接池**：asyncpg，pool_size=10, max_overflow=20
- **字符集**：UTF-8
- **排序规则**：zh_CN.UTF-8（中文排序）

## 2. 命名规范

### 2.1 表名

- 使用 `snake_case` 复数形式：`metrics`, `data_sources`, `audit_logs`
- 关联表使用双方表名：`metric_dimensions`, `user_policy_bindings`
- 禁止使用数据库保留字
- 禁止使用缩写（除非团队公认：`src` → `source`, `auth` → `authentication` 除外）
- 添加前缀区分微服务（如有共享库）：`sem_metrics`, `meta_tables`

### 2.2 字段名

- `snake_case`：`created_at`, `user_id`, `is_active`
- 主键统一 `id`（UUID 类型）
- 外键 `{referenced_table}_id`：`metric_id`, `user_id`
- 布尔字段 `is_` / `has_` 前缀：`is_active`, `has_embedding`
- 时间字段 `_at` 后缀：`created_at`, `updated_at`, `deleted_at`
- 数量字段 `_count` 后缀：`retry_count`, `scan_row_count`

### 2.3 索引名

- 格式：`idx_{表名}_{字段名}`
- 联合索引：`idx_{表名}_{字段1}_{字段2}`
- 唯一索引：`uidx_{表名}_{字段名}`
- 示例：`idx_metrics_name`, `uidx_users_email`, `idx_audit_logs_created_at`

## 3. 字段类型规范

| 业务含义 | PostgreSQL 类型 | 说明 |
|---------|----------------|------|
| 主键 | `UUID` | 默认 `uuid_generate_v4()` |
| 外键 | `UUID` | 与主键类型一致 |
| 短文本 | `VARCHAR(n)` | 名称、标题等，指定长度 |
| 长文本 | `TEXT` | 描述、SQL、配置等 |
| 金额 | `NUMERIC(18,4)` | 精确小数 |
| 布尔 | `BOOLEAN` | 不用 INT |
| 时间 | `TIMESTAMPTZ` | 带时区时间戳 |
| JSON | `JSONB` | 结构化数据，支持索引查询 |
| 向量 | `VECTOR(1536)` | pgvector 扩展 |
| 枚举 | `VARCHAR` + CHECK | 不用 PostgreSQL ENUM（迁移困难） |
| 状态 | `VARCHAR(20)` + CHECK | 如 `status VARCHAR(20) CHECK (status IN ('active','disabled'))` |
| 数据新鲜度 | `VARCHAR(10)` + CHECK | `freshness VARCHAR(10) CHECK (freshness IN ('realtime','hourly','daily','custom'))` |
| 难度等级 | `VARCHAR(10)` + CHECK | `difficulty VARCHAR(10) CHECK (difficulty IN ('simple','medium','complex'))` |

## 4. 表结构强制要求

每张**业务表**必须包含以下字段：

```sql
CREATE TABLE {table_name} (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   UUID NOT NULL,          -- 多租户隔离（Phase1 单租户 hardcode，Phase2 完整支持）
    -- ... 业务字段 ...

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ              -- 软删除，NULL 表示未删除
);

-- 软删除索引
CREATE INDEX idx_{table}_deleted_at ON {table} (deleted_at) WHERE deleted_at IS NULL;
```

## 5. 索引规范

### 5.1 基本规则

- 主键自动创建索引
- 所有外键必须建索引
- 高频查询条件的 WHERE 字段建索引
- 禁止在低基数列（< 100 个不同值）建普通索引，考虑部分索引
- 单表索引数量不超过 10 个

### 5.2 pgvector 索引

```sql
-- IVFFlat 索引（推荐，适合 10 万条以内）
CREATE INDEX idx_metrics_embedding
ON metrics USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- HNSW 索引（Phase 2，适合更大规模）
CREATE INDEX idx_metrics_embedding_hnsw
ON metrics USING hnsw (embedding vector_cosine_ops);
```

### 5.3 部分索引

```sql
-- 只索引活跃记录
CREATE INDEX idx_sessions_active
ON sessions (user_id, updated_at)
WHERE deleted_at IS NULL;

-- 只索引特定状态
CREATE INDEX idx_audit_logs_risk
ON audit_logs (created_at)
WHERE risk_level IN ('high', 'critical');

-- 租户隔离索引（所有业务表）
CREATE INDEX idx_{table}_tenant ON {table_name} (tenant_id);

-- 数据源健康状态索引
CREATE INDEX idx_datasource_health_status ON datasource_health (status, last_heartbeat);

-- LLM 调用日志按租户聚合
CREATE INDEX idx_llm_call_logs_tenant_date ON llm_call_logs (tenant_id, created_at);
```

## 6. 迁移规范

### 6.1 迁移文件命名

```
alembic/versions/
├── 20260527_001_create_data_sources.py
├── 20260527_002_create_metrics.py
├── 20260527_003_add_embedding_to_metrics.py
└── 20260528_001_create_audit_logs.py
```

格式：`{YYYYMMDD}_{序号}_{描述}.py`

### 6.2 迁移规则

- **只做加法**：禁止删除列/表，标记 `deprecated_at`
- **禁止修改已有列类型**（除非无害转换如 `VARCHAR` 扩长）
- **每次迁移一个逻辑变更**，不混合多个无关变更
- **迁移必须可逆**（`upgrade` + `downgrade`）
- **大数据量操作**用批处理 + `CONCURRENTLY` 建索引
- 禁止在迁移中写业务逻辑

```python
# 正确的迁移示例
def upgrade() -> None:
    op.add_column("metrics", sa.Column(
        "embedding", Vector(1536), nullable=True
    ))
    # CONCURRENTLY 不能在事务中
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_metrics_embedding
        ON metrics USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

def downgrade() -> None:
    op.drop_index("idx_metrics_embedding")
    op.drop_column("metrics", "embedding")
```

## 7. SQL 编写规范

### 7.1 查询规则

```sql
-- 正确：用 CTE 替代子查询
WITH monthly_revenue AS (
    SELECT
        DATE_TRUNC('month', order_date) AS month,
        SUM(amount) AS revenue
    FROM orders
    WHERE deleted_at IS NULL
    GROUP BY 1
)
SELECT month, revenue
FROM monthly_revenue
WHERE revenue > 10000
ORDER BY month;

-- 错误：嵌套子查询
SELECT * FROM (
    SELECT month, SUM(amount) AS revenue FROM (
        SELECT DATE_TRUNC('month', order_date) AS month, amount
        FROM orders
    ) t GROUP BY month
) t2 WHERE revenue > 10000;
```

### 7.2 禁止操作

```sql
-- 禁止：SELECT *
SELECT id, name, calculation FROM metrics;  -- 显式列出字段

-- 禁止：无 WHERE 的 UPDATE/DELETE
UPDATE metrics SET is_active = false WHERE id = $1;

-- 禁止：硬编码值，用参数化
-- 错误：WHERE name = 'GMV'
-- 正确：WHERE name = :name
```

### 7.3 性能规则

- 查询必须使用索引（`EXPLAIN ANALYZE` 验证）
- `LIMIT` 必须配合 `ORDER BY`
- 大表关联用 `JOIN` 替代子查询
- 避免 `%keyword%` 前缀模糊匹配，使用全文检索或 pgvector
- 分页使用 keyset pagination（游标分页）替代 `OFFSET`

```sql
-- 游标分页（推荐）
SELECT id, name, created_at
FROM metrics
WHERE created_at < $last_created_at  -- 上一页最后一条的时间
ORDER BY created_at DESC
LIMIT 20;
```

## 8. 数据库连接管理

```python
# 通过 SQLAlchemy async engine 管理
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,       # 自动检测断开连接
    pool_recycle=3600,        # 1小时回收
    echo=settings.debug,      # DEBUG 模式打印 SQL
)

async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,    # async 必须
    class_=AsyncSession,
)
```

## 9. 备份与恢复

- 每日全量备份（凌晨 2:00，pg_dump）
- 每小时 WAL 归档（增量备份）
- 备份保留 30 天
- 每季度进行一次恢复演练
- pgvector 数据单独备份（`pg_dump -t metrics -t dimensions`）
