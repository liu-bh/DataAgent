# 核心数据模型详细设计

## ER 关系概览

```
tenants ──┬── data_sources ── datasource_capabilities
         │        └── datasource_health
         │
         ├── users ── user_quotas ── rbac_policies ── user_policy_bindings
         │    │                                     └── data_masking_rules
         │    │
         │    ├── sessions ── messages
         │    ├── query_history (is_favorited)
         │    └── user_feedbacks ── nl2sql_examples (用户贡献)
         │
         ├── semantic_models ── source_tables ── table_relationships
         │                        (pgvector)
         ├── metrics ── metric_dimensions ── dimensions
         │    (version,嵌套)
         │
         ├── prompt_versions (A/B 测试)
         ├── llm_call_logs (成本追踪)
         └── audit_logs (MinIO 归档)
```

## 1. 租户表 `tenants`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | VARCHAR(100) | NOT NULL | 租户名称 |
| domain | VARCHAR(200) | UNIQUE | 域名（可选） |
| llm_monthly_budget | NUMERIC(12,2) | DEFAULT 50000 | 月度 LLM 成本预算 |
| status | VARCHAR(20) | CHECK | active/disabled |
| created_at | TIMESTAMPTZ | NOT NULL | |

## 2. 用户与权限

### `users`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| tenant_id | UUID | FK→tenants, NOT NULL | 多租户 |
| email | VARCHAR(255) | UNIQUE NOT NULL | |
| password_hash | VARCHAR(255) | NOT NULL | bcrypt |
| display_name | VARCHAR(100) | NOT NULL | |
| role | VARCHAR(20) | CHECK (admin/analyst/viewer) | |
| is_active | BOOLEAN | DEFAULT true | |

### `user_quotas`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| tenant_id | UUID | FK→tenants |
| user_id | UUID | FK→users |
| daily_query_limit | INTEGER | DEFAULT 100 |
| hourly_scan_limit | BIGINT | DEFAULT 500000 |
| effective_at | DATE | 生效日期 |

### `rbac_policies`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| tenant_id | UUID | FK→tenants |
| name | VARCHAR(100) | 策略名称 |
| resource_type | VARCHAR(50) | table/metric/dashboard |
| resource_id | UUID | 资源 ID |
| operation | VARCHAR(20) | read/export/ddl |
| column_mask | JSONB | 列级权限：`{"hide": ["phone","id_card"]}` |
| row_filter | TEXT | 行级权限：`region IN ('华东','华南')` |
| priority | INTEGER | 优先级（数值越小越优先） |
| created_at | TIMESTAMPTZ | |

## 3. 语义模型

### `semantic_models`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| tenant_id | UUID | FK→tenants |
| name | VARCHAR(100) | 业务语义视图名称 |
| description | TEXT | 视图描述 |
| domain | VARCHAR(50) | 业务域（电商/运营/财务） |
| data_source_ids | UUID[] | 关联的数据源（GIN 索引） |

### `source_tables`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| tenant_id | UUID | FK→tenants |
| data_source_id | UUID | FK→data_sources |
| schema_name | VARCHAR(100) | Schema 名 |
| table_name | VARCHAR(100) | 表名 |
| columns | JSONB | 列定义 `[{name, type, description, is_primary_key}]` |
| row_count | BIGINT | 估算行数 |
| description | TEXT | 表描述 |
| embedding | VECTOR(1536) | 表级语义向量 |
| last_synced_at | TIMESTAMPTZ | 最后同步时间 |

### `metrics`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| tenant_id | UUID | FK→tenants |
| semantic_model_id | UUID | FK→semantic_models |
| name | VARCHAR(100) | 指标名称，如 "GMV" |
| description | TEXT | 指标描述 |
| calculation | TEXT | 计算表达式 `SUM(amount)` |
| unit | VARCHAR(20) | 单位：元/个/率 |
| version | INTEGER | 版本号 |
| effective_time | TIMESTAMPTZ | 版本生效时间 |
| parent_metric_id | UUID | FK→metrics（嵌套引用） |
| embedding | VECTOR(1536) | 指标语义向量 |
| tags | VARCHAR(50)[] | 标签 |

### `dimensions`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| tenant_id | UUID | FK→tenants |
| semantic_model_id | UUID | FK→semantic_models |
| name | VARCHAR(100) | 维度名称，如 "地区" |
| column_name | VARCHAR(200) | 对应物理列 |
| table_id | UUID | FK→source_tables |
| synonyms | VARCHAR(50)[] | 同义词：`["区域","大区","省份"]` |
| hierarchy | JSONB | 层级：`{"level": "province", "children": ["city", "district"]}` |
| is_virtual | BOOLEAN | 是否虚拟维度（CASE WHEN 计算） |
| virtual_expression | TEXT | 虚拟维度表达式（is_virtual=true 时） |
| embedding | VECTOR(1536) | 维度语义向量 |

### `metric_dimensions`

| 字段 | 类型 | 说明 |
|------|------|------|
| metric_id | UUID | FK→metrics |
| dimension_id | UUID | FK→dimensions |
| PRIMARY KEY | (metric_id, dimension_id) | 复合主键 |

### `table_relationships`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| tenant_id | UUID | FK→tenants |
| semantic_model_id | UUID | FK→semantic_models |
| left_table_id | UUID | FK→source_tables |
| right_table_id | UUID | FK→source_tables |
| join_type | VARCHAR(20) | inner/left/right/full |
| join_condition | TEXT | `orders.user_id = users.id` |

## 4. 会话与查询

### `sessions`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| tenant_id | UUID | FK→tenants |
| user_id | UUID | FK→users |
| title | VARCHAR(200) | 会话标题（自动生成） |
| message_count | INTEGER | 消息数（上限 50） |
| expires_at | TIMESTAMPTZ | 过期时间（30 min 无操作） |
| is_archived | BOOLEAN | 是否已归档 |

### `messages`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| session_id | UUID | FK→sessions |
| role | VARCHAR(20) | user/assistant/system |
| content | TEXT | 消息内容 |
| sql | TEXT | 生成的 SQL（assistant 角色时） |
| sql_dialect | VARCHAR(20) | SQL 方言 |
| chart_spec | JSONB | 图表配置 |
| created_at | TIMESTAMPTZ | |

### `query_history`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| tenant_id | UUID | FK→tenants |
| user_id | UUID | FK→users |
| session_id | UUID | FK→sessions |
| question | TEXT | 用户问题 |
| sql | TEXT | 生成的 SQL |
| datasource_id | UUID | FK→data_sources |
| row_count | INTEGER | 返回行数 |
| latency_ms | INTEGER | 执行耗时 |
| is_favorited | BOOLEAN | 是否收藏 |
| created_at | TIMESTAMPTZ | |

## 5. Prompt 与 LLM

### `prompt_versions`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| scene | VARCHAR(50) | 场景：nl2sql/intent/explanation |
| version | INTEGER | 版本号 |
| content | TEXT | Prompt 模板内容 |
| is_active | BOOLEAN | 是否为当前激活版本 |
| effectiveness_score | NUMERIC(5,4) | A/B 测试效果评分 |
| ab_test_traffic | NUMERIC(3,2) | A/B 测试流量比例 |
| created_at | TIMESTAMPTZ | |

### `nl2sql_examples`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| tenant_id | UUID | FK→tenants |
| question | TEXT | 用户问题 |
| sql | TEXT | 对应 SQL |
| domain | VARCHAR(50) | 业务域 |
| difficulty | VARCHAR(10) | simple/medium/complex |
| source | VARCHAR(20) | builtin/user_contributed |
| is_verified | BOOLEAN | 是否经过验证 |
| embedding | VECTOR(1536) | 问题向量（用于相似度匹配） |
| usage_count | INTEGER | 被引用次数 |
| success_rate | NUMERIC(5,4) | 实际使用成功率 |
| created_at | TIMESTAMPTZ | |

### `llm_call_logs`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| tenant_id | UUID | FK→tenants |
| user_id | UUID | FK→users |
| trace_id | VARCHAR(32) | 链路追踪 ID |
| model | VARCHAR(50) | 模型名称 |
| prompt_tokens | INTEGER | 输入 Token 数 |
| completion_tokens | INTEGER | 输出 Token 数 |
| latency_ms | INTEGER | 耗时（毫秒） |
| cost | NUMERIC(10,6) | 调用成本（元） |
| success | BOOLEAN | 是否成功 |
| error_message | TEXT | 失败原因 |
| created_at | TIMESTAMPTZ | |

## 6. 安全与审计

### `audit_logs`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| tenant_id | UUID | FK→tenants |
| user_id | UUID | FK→users |
| action | VARCHAR(50) | query/export/configure |
| sql_text | TEXT | 执行的 SQL（脱敏后的） |
| datasource_id | UUID | FK→data_sources |
| scan_rows | BIGINT | 扫描行数 |
| duration_ms | INTEGER | 执行耗时 |
| risk_level | VARCHAR(20) | none/low/medium/high/critical |
| ip_address | VARCHAR(45) | 客户端 IP |
| created_at | TIMESTAMPTZ | |

### `data_masking_rules`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| tenant_id | UUID | FK→tenants |
| datasource_id | UUID | FK→data_sources |
| column_path | VARCHAR(200) | 字段路径 `users.phone` |
| mask_type | VARCHAR(20) | phone/id_card/bank_card/email/name |
| mask_pattern | VARCHAR(50) | 脱敏模式 `***` |
| created_at | TIMESTAMPTZ | |

## 7. 数据源

### `data_sources`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| tenant_id | UUID | FK→tenants |
| name | VARCHAR(100) | 数据源名称 |
| type | VARCHAR(20) | mysql/postgresql/doris/starrocks/clickhouse/api |
| host | VARCHAR(255) | 连接地址 |
| port | INTEGER | 端口 |
| database | VARCHAR(100) | 数据库名 |
| username | VARCHAR(100) | 用户名 |
| password | TEXT | 加密存储的密码 |
| pool_size | INTEGER | 连接池大小 |
| freshness_level | VARCHAR(10) | realtime/hourly/daily/custom |
| freshness_cron | VARCHAR(100) | 数据新鲜度同步频率（仅 custom） |
| status | VARCHAR(20) | active/disabled |
| last_health_check | TIMESTAMPTZ | 最后健康检查时间 |

### `datasource_health`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| datasource_id | UUID | FK→data_sources |
| pool_usage | NUMERIC(5,2) | 连接池使用率 |
| avg_latency_ms | INTEGER | 平均查询延迟 |
| status | VARCHAR(20) | healthy/degraded/down |
| last_heartbeat | TIMESTAMPTZ | 最后心跳时间 |

## 8. 用户反馈

### `user_feedbacks`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| tenant_id | UUID | FK→tenants |
| query_id | UUID | FK→query_history |
| user_id | UUID | FK→users |
| satisfaction | VARCHAR(10) | positive/negative |
| edited_sql | TEXT | 用户修改后的 SQL |
| feedback_text | TEXT | 文字反馈 |
| created_at | TIMESTAMPTZ | |
