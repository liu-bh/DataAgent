# 环境变量参考表

## 通用约定

- 所有环境变量通过 `.env` 文件注入，不硬编码
- 每个 .env 文件有对应的 `.env.example` 模板
- 敏感信息通过 `.gitignore` 排除，不提交到仓库
- 环境变量前缀按服务区分

## 1. Agent Service（端口 8000）

| 变量名 | 说明 | 默认值 | 是否必填 |
|--------|------|--------|---------|
| `AGENT_PORT` | 服务监听端口 | `8000` | 否 |
| `AGENT_HOST` | 服务监听地址 | `0.0.0.0` | 否 |
| `AGENT_DATABASE_URL` | PostgreSQL 连接串 | `postgresql+asyncpg://datapilot:datapilot@localhost:5432/datapilot` | 是 |
| `AGENT_REDIS_URL` | Redis 连接串 | `redis://localhost:6379/0` | 是 |
| `AGENT_LOG_LEVEL` | 日志级别 | `INFO` | 否 |
| `AGENT_DEBUG` | 调试模式 | `false` | 否 |
| `AGENT_TENANT_ID` | 默认租户 ID（Phase1） | `default` | 否 |

### LLM 配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `LLM_DEFAULT_PROVIDER` | 默认 LLM 提供商 | `deepseek` |
| `LLM_DEFAULT_MODEL` | 默认模型 | `deepseek-v3` |
| `LLM_TIMEOUT` | LLM 调用超时（秒） | `30` |
| `LLM_MAX_RETRIES` | 最大重试次数 | `3` |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | - |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 | `https://api.deepseek.com/v1` |
| `QWEN_API_KEY` | 通义千问 API Key | - |
| `QWEN_BASE_URL` | 通义千问 API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `EMBEDDING_PROVIDER` | Embedding 提供商 | `qwen` |
| `EMBEDDING_MODEL` | Embedding 模型 | `text-embedding-v3` |
| `EMBEDDING_DIMENSIONS` | 向量维度 | `1536` |

### LLM 成本预算（Phase1 可选）

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `LLM_MONTHLY_BUDGET` | 月度成本上限（元） | `50000` |
| `LLM_BUDGET_ALERT_THRESHOLD` | 告警阈值比例 | `0.8` |
| `LLM_MAX_TOKENS_PER_QUERY` | 单次查询 Token 上限 | `12000` |

## 2. Semantic Service（端口 8001）

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `SEMANTIC_PORT` | 服务端口 | `8001` |
| `SEMANTIC_DATABASE_URL` | PostgreSQL 连接串 | 同上 |
| `SEMANTIC_REDIS_URL` | Redis 连接串 | 同上 |
| `PGVECTOR_INDEX_TYPE` | 向量索引类型 | `ivfflat` |
| `PGVECTOR_INDEX_LISTS` | IVFFlat lists 参数 | `100` |
| `SEMANTIC_CACHE_TTL` | 语义缓存过期时间（秒） | `3600` |

## 3. SQL Generator Service（端口 8002）

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `SQLGEN_PORT` | 服务端口 | `8002` |
| `SQLGEN_DATABASE_URL` | PostgreSQL 连接串 | 同上 |
| `SQLGEN_REDIS_URL` | Redis 连接串 | 同上 |
| `SQLGEN_DEFAULT_DIALECT` | 默认 SQL 方言 | `mysql` |
| `SQLGEN_MAX_CORRECTION_ROUNDS` | Self-Correction 最大轮数 | `3` |
| `SQLGEN_COST_ESTIMATE_ENABLED` | 是否启用 EXPLAIN 成本预估 | `true` |
| `SQLGEN_DRYRUN_ENABLED` | 是否启用 Dry-run 预执行 | `true` |
| `SQLGEN_SCAN_ROW_LIMIT` | 扫描行数上限 | `1000000` |
| `SQLGEN_LARGE_RESULT_THRESHOLD` | 大结果集阈值（字节） | `1048576` (1MB) |

## 4. Query Executor Service（端口 8003）

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `QUERYEXEC_PORT` | 服务端口 | `8003` |
| `QUERYEXEC_REDIS_URL` | Redis 连接串 | 同上 |
| `QUERYEXEC_MINIO_ENDPOINT` | MinIO 地址 | `localhost:9000` |
| `QUERYEXEC_MINIO_BUCKET` | 大结果存储桶 | `query-results` |
| `QUERYEXEC_DEFAULT_LIMIT` | 默认 LIMIT | `1000` |
| `QUERYEXEC_MAX_EXPORT_ROWS` | 最大导出行数 | `100000` |

### 数据源连接池配置

数据源连接参数在 `data_sources` 表中配置，此处是客户端默认值：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `POOL_SIZE_MYSQL` | MySQL 连接池大小 | `10` |
| `POOL_SIZE_POSTGRESQL` | PostgreSQL 连接池大小 | `10` |
| `POOL_SIZE_DORIS` | Doris/StarRocks 连接池大小 | `20` |
| `POOL_SIZE_CLICKHOUSE` | ClickHouse 连接池大小 | `15` |
| `QUERY_TIMEOUT` | 查询超时（秒） | `30` |

## 5. Auth Service（端口 8004）

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `AUTH_PORT` | 服务端口 | `8004` |
| `AUTH_DATABASE_URL` | PostgreSQL 连接串 | 同上 |
| `JWT_SECRET_KEY` | JWT 签名密钥 | **必须设置，至少 32 字符** |
| `JWT_ACCESS_TOKEN_EXPIRE` | Access Token 过期时间 | `900` (15分钟) |
| `JWT_REFRESH_TOKEN_EXPIRE` | Refresh Token 过期时间 | `604800` (7天) |
| `AUTH_LDAP_ENABLED` | 是否启用 LDAP | `false` |

## 6. Guardrail Service（端口 8005）

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `GUARDRAIL_PORT` | 服务端口 | `8005` |
| `GUARDRAIL_DATABASE_URL` | PostgreSQL 连接串 | 同上 |
| `SQL_RISK_THRESHOLD` | SQL 风险等级阈值 | `medium` |
| `USER_DAILY_QUERY_LIMIT` | 用户日查询次数上限 | `100` |
| `USER_HOURLY_SCAN_LIMIT` | 用户小时扫描行数上限 | `500000` |

## 7. Session Service（端口 8006）

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `SESSION_PORT` | 服务端口 | `8006` |
| `SESSION_DATABASE_URL` | PostgreSQL 连接串 | 同上 |
| `SESSION_REDIS_URL` | Redis 连接串 | 同上 |
| `SESSION_TIMEOUT_SECONDS` | 会话超时（秒） | `1800` (30分钟) |
| `SESSION_MAX_MESSAGES` | 单会话最大消息数 | `50` |
| `SESSION_RETENTION_DAYS` | 会话保留天数 | `90` |

## 8. 前端

在 `web/.env` 中配置：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `VITE_API_BASE_URL` | API 基础地址 | `http://localhost:8000` |
| `VITE_WS_URL` | WebSocket 地址 | `ws://localhost:8000` |
| `VITE_SENTRY_DSN` | Sentry DSN | 空（可选） |
| `VITE_APP_TITLE` | 应用标题 | `DataPilot` |

## 9. 产品授权

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `LICENSE_FILE_PATH` | 授权文件路径 | `./license.json` |
| `LICENSE_SIGNING_KEY` | 签名密钥（仅 CLI 生成时使用） | - |

## 10. 基础设施（docker-compose.dev.yml）

| 服务 | 端口 | 说明 |
|------|------|------|
| PostgreSQL | 5432 | 用户/密码 `datapilot/datapilot`，数据库 `datapilot` |
| Redis | 6379 | 无密码（开发环境） |
| RocketMQ NameServer | 9876 | - |
| RocketMQ Broker | 10911/10909 | - |
| MinIO Console | 9001 | `minioadmin/minioadmin` |
| MinIO API | 9000 | S3 兼容 |
| Jaeger | 16686 | 链路追踪 UI |
| Prometheus | 9090 | 监控指标 |
| Grafana | 3000 | 监控大盘（默认 admin/admin） |
| APISIX | 9180/9443 | API 网关 |

## 11. LLM API Key 获取

### DeepSeek
1. 注册 https://platform.deepseek.com
2. 创建 API Key
3. 设置环境变量 `DEEPSEEK_API_KEY`

### 通义千问
1. 注册 https://dashscope.console.aliyun.com
2. 创建 API Key
3. 设置环境变量 `QWEN_API_KEY`

### Embedding
- 通义：与通义千问共用 Key，使用 `text-embedding-v3` 模型
- BGE-M3（自部署）：需要额外部署 Embedding 服务，修改 `EMBEDDING_BASE_URL`
