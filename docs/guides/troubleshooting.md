# 常见问题排查指南

> 本文档汇总 DataPilot 开发和运维中的常见问题及解决方案。

## 1. 基础设施问题

### Docker 服务启动失败

```bash
# 检查容器状态
docker compose -f docker-compose.dev.yml ps

# 查看日志
docker compose -f docker-compose.dev.yml logs postgres
docker compose -f docker-compose.dev.yml logs redis

# 常见原因
# 1. 端口被占用
lsof -i :5432   # PostgreSQL
lsof -i :6379   # Redis

# 2. 磁盘空间不足
df -h

# 3. 重新创建
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d
```

### PostgreSQL 连接失败

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| `Connection refused` | PG 未启动 | `docker compose up -d postgres` |
| `FATAL: database "datapilot" does not exist` | 数据库未创建 | 检查初始化脚本是否执行 |
| `FATAL: password authentication failed` | 密码错误 | 检查 `.env` 中的 `DATABASE_URL` |
| `too many connections` | 连接池满 | 增大 PG `max_connections` 或减小应用连接池 |

### Redis 连接失败

```bash
# 测试连接
redis-cli -h localhost -p 6379 ping

# 检查是否在运行
docker compose -f docker-compose.dev.yml ps redis

# 清除缓存（开发环境）
redis-cli FLUSHALL
```

## 2. 后端问题

### 服务启动失败

```bash
# 查看详细错误
cd services/agent-service
uv run python -m datapilot_agent.main --log-level DEBUG

# 常见原因
# 1. 依赖缺失
uv sync

# 2. 数据库迁移未执行
uv run alembic upgrade head

# 3. 环境变量缺失
cat .env | grep -v "^#" | sort
```

### LLM 调用超时

```
错误：LLM_TIMEOUT - 模型响应超时
```

排查步骤：

```bash
# 1. 检查 API Key 是否正确
echo $DEEPSEEK_API_KEY

# 2. 检查网络连通性
curl https://api.deepseek.com/v1/models -H "Authorization: Bearer $DEEPSEEK_API_KEY"

# 3. 检查超时配置
# 默认 30 秒，可在 .env 中调整
LLM_TIMEOUT=60

# 4. 检查熔断器状态
# 如果熔断器打开，等待 recovery_timeout 后重试
# 或手动重置
```

### LLM 生成 SQL 质量差

| 问题 | 排查方向 | 解决方案 |
|------|---------|---------|
| SQL 表名不对 | 语义匹配相似度低 | 补充表描述，优化 `source_tables.description` |
| 缺少 JOIN | 未配置表关系 | 检查 `table_relationships` |
| 时间过滤错误 | 时间解析问题 | 检查 Prompt 中的时间处理说明 |
| 列名不对 | 列描述不清晰 | 补充 `columns.description` |
| 生成空 SQL | Token 超限或 LLM 拒绝 | 检查 Token 预算，查看 LLM 返回 |

### 数据库迁移报错

```bash
# 查看当前版本
uv run alembic current

# 查看迁移历史
uv run alembic history

# 回滚一个版本
uv run alembic downgrade -1

# 强制标记为已执行（慎用）
uv run alembic stamp head

# 迁移冲突解决
# 1. 备份数据库
# 2. 手动执行冲突的 SQL
# 3. alembic stamp head
```

### 熔断器频繁触发

```python
# 查看熔断器状态（日志中搜索）
# circuitbreaker state=CLOSED/OPEN/HALF_OPEN

# 调整熔断参数（代码中）
@circuitbreaker.protect(
    failure_threshold=5,       # 默认 5 次失败触发
    recovery_timeout=60,        # 默认 60 秒恢复
    fallback_function=xxx,     # 必须配置降级函数
)
```

## 3. 前端问题

### pnpm install 失败

```bash
# 清除缓存重试
rm -rf node_modules/.cache
pnpm store prune
pnpm install

# 配置镜像源
pnpm config set registry https://registry.npmmirror.com

# Node.js 版本检查
node -v  # >= 20
```

### 开发服务器启动失败

```bash
# 端口占用
lsof -i :5173
kill -9 <PID>

# 类型错误
cd web && pnpm type-check

# 依赖版本不兼容
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

### SSE 流式响应中断

```javascript
// 检查 EventSource 连接状态
// 常见原因：
// 1. Token 过期 → 重新登录
// 2. 网关超时 → 检查 APISIX 配置
// 3. 后端异常 → 查看后端日志

// 前端自动重连
const eventSource = new EventSource('/api/v1/chat/stream', {
  withCredentials: true,
});
```

### 图表不渲染

```
1. 检查 chart_spec 格式是否正确
2. ECharts 是否正确初始化
3. 数据格式是否匹配图表类型
4. 查看浏览器 Console 错误
```

## 4. NL2SQL 问题

### SQL 执行报错

| 错误类型 | 常见原因 | 解决方案 |
|---------|---------|---------|
| `Table doesn't exist` | 表名拼写错误 | 检查语义模型配置 |
| `Unknown column` | 列名不存在 | 检查表元数据同步 |
| `Syntax error` | SQL 语法问题 | 检查 SQL 方言设置 |
| `Timeout` | 查询太慢 | 添加 LIMIT，优化索引 |
| `Permission denied` | 数据源权限不足 | 检查只读账号权限 |

### Self-Correction 不生效

```bash
# 检查自校验配置
SQLGEN_MAX_CORRECTION_ROUNDS=3  # 默认 3 轮

# 检查 Dry-run 是否启用
SQLGEN_DRYRUN_ENABLED=true

# 排查：查看 LLM Call Log 中的 correction 请求
# 如果 correction 请求未发出，可能是 Dry-run 失败
```

### 幻觉检测误报

```
1. 数值范围检查 → 调整阈值（默认：与历史值偏差 > 50% 触发）
2. 时间一致性检查 → 确认 data_cutoff 配置正确
3. SQL-结果一致性 → 检查 SQL 执行是否返回了正确数据
```

## 5. 安全问题

### JWT Token 过期

```
Access Token 有效期：15 分钟
Refresh Token 有效期：7 天

前端应自动使用 Refresh Token 刷新：
POST /api/v1/auth/refresh
{"refresh_token": "xxx"}
```

### RBAC 权限不生效

```bash
# 检查策略配置
GET /api/v1/rbac/policies

# 检查用户角色
GET /api/v1/auth/me

# 常见问题：
# 1. 策略优先级冲突 → 调整 priority 字段
# 2. row_filter SQL 语法错误 → 在目标数据库上测试过滤条件
# 3. column_mask 配置错误 → 检查 JSON 格式
```

### 数据脱敏不生效

```
1. 检查 masking_rules 配置
2. 确认 column_path 格式正确（如 "users.phone"）
3. 确认查询涉及被脱敏的列
```

## 6. 性能问题

### 查询慢

```sql
-- 在目标数据源上执行 EXPLAIN
EXPLAIN SELECT ...;

-- 常见优化方向：
-- 1. 缺少索引 → 添加合适的索引
-- 2. 全表扫描 → 添加 WHERE 条件
-- 3. JOIN 太多 → 优化 JOIN 顺序或减少关联表
-- 4. 子查询 → 改为 JOIN
```

### SSE 响应延迟

```
1. LLM 响应慢 → 检查 LLM 提供商延迟
2. SQL 执行慢 → 优化查询或添加索引
3. 后端处理慢 → 查看 trace_id 链路追踪
```

### 内存占用高

```
1. 大结果集未分页 → 启用游标分页
2. 连接池泄漏 → 检查连接是否正确归还
3. 向量索引内存 → 调整 IVFFlat lists 参数
```

## 7. 日志排查

### 查看服务日志

```bash
# 开发环境直接看控制台输出

# 生产环境
# 日志格式（structlog）
{
  "timestamp": "2026-05-27T14:30:00+08:00",
  "level": "ERROR",
  "event": "llm_call_failed",
  "trace_id": "abc123",
  "tenant_id": "tenant-uuid",
  "model": "deepseek-v3",
  "latency_ms": 30000,
  "error": "timeout"
}
```

### 链路追踪

```bash
# Jaeger UI
# http://localhost:16686

# 按 trace_id 查询完整调用链
# 关键标签：trace_id, tenant_id, user_id
```

### Prometheus 指标

```bash
# 常用查询
# LLM 调用延迟
histogram_quantile(0.95, rate(llm_call_duration_seconds_bucket[5m]))

# 错误率
rate(llm_call_errors_total[5m]) / rate(llm_call_total[5m])

# 查询 QPS
rate(chat_queries_total[5m])
```

## 8. 紧急恢复

| 场景 | 操作 |
|------|------|
| 服务崩溃 | `docker compose restart <service>` |
| 数据库宕机 | `docker compose restart postgres`，检查磁盘 |
| Redis 宕机 | `docker compose restart redis`，缓存丢失不影响核心功能 |
| LLM 不可用 | 熔断器自动降级到缓存/历史查询 |
| 全部服务不可用 | `docker compose down && docker compose up -d` |
