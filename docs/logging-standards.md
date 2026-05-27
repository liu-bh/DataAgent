# 日志与监控规范

## 1. 日志规范

### 1.1 日志框架

- Python：`structlog`（结构化 JSON 日志）
- 前端：`pino` 或 `consola`

### 1.2 日志格式

```json
{
  "timestamp": "2026-05-27T14:30:00.123+08:00",
  "level": "INFO",
  "service": "sql-generator-service",
  "trace_id": "abc123def456",
  "span_id": "789ghi",
  "user_id": "uuid-of-user",
  "session_id": "uuid-of-session",
  "message": "SQL generated successfully",
  "sql": "SELECT SUM(amount) FROM orders WHERE month='2026-04'",
  "duration_ms": 1250,
  "model": "deepseek-v3",
  "retry_count": 0
}
```

### 1.3 日志级别

| 级别 | 使用场景 | 示例 |
|------|---------|------|
| `DEBUG` | 开发调试信息 | 变量值、函数入口/出口 |
| `INFO` | 正常业务流程 | 请求处理完成、任务调度、SQL 生成成功 |
| `WARNING` | 异常但可恢复 | LLM 返回格式异常已重试、缓存未命中降级 |
| `ERROR` | 业务异常 | 查询失败、SQL 风险拦截、权限不足 |
| `CRITICAL` | 系统故障 | 数据库连接丢失、服务不可用 |

**原则：**
- 生产环境默认 `INFO` 级别
- `DEBUG` 日志仅在需要时动态开启
- `ERROR` 必须包含足够上下文排查问题
- 禁止使用 `print()`

### 1.4 结构化日志配置

```python
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
)

# 使用
logger = structlog.get_logger()

logger.info(
    "sql_generated",
    query_id=query_id,
    sql=sql,
    duration_ms=duration,
    model=model_name,
)
```

### 1.5 链路追踪上下文

```python
from contextvars import ContextVar

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")

# 在请求入口设置
@app.middleware("http")
async def set_trace_context(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
    trace_id_var.set(trace_id)
    user_id_var.set(request.state.user_id)
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response
```

### 1.6 日志记录规则

```python
# 正确：结构化字段
logger.info("query_completed", query_id=id, duration_ms=123, row_count=5000)

# 错误：字符串拼接
logger.info(f"Query {id} completed in 123ms with 5000 rows")

# 错误：日志过多（循环内）
for row in results:
    logger.info("processing row", row=row)  # 会产生海量日志

# 正确：循环外记录统计
logger.info("batch_processed", total=len(results), duration_ms=total_time)
```

**敏感信息：**
- 禁止记录密码、Token、API Key
- SQL 记录需脱敏（不记录用户数据，仅记录结构）
- 数据库连接字符串用脱敏格式

## 2. 监控指标 (Prometheus)

### 2.1 核心指标

每个微服务暴露 `/metrics` 端点：

```python
from prometheus_client import Counter, Histogram, Gauge

# 请求计数
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "endpoint", "status"],
)

# 请求延迟
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["service", "method", "endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# LLM 调用
LLM_REQUEST_COUNT = Counter(
    "llm_requests_total",
    "LLM API calls",
    ["provider", "model", "status"],
)

LLM_REQUEST_DURATION = Histogram(
    "llm_request_duration_seconds",
    "LLM API call duration",
    ["provider", "model"],
    buckets=[1, 2, 5, 10, 20, 30, 60],
)

# 查询执行
QUERY_DURATION = Histogram(
    "query_execution_duration_seconds",
    "Query execution duration",
    ["datasource_type"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60],
)

# 活跃会话
ACTIVE_SESSIONS = Gauge(
    "active_sessions",
    "Number of active sessions",
)
```

### 2.2 业务指标

| 指标 | 类型 | 标签 | 说明 |
|------|------|------|------|
| NL2SQL 准确率 | Gauge | difficulty | simple/medium/complex |
| SQL 风险拦截率 | Counter | risk_level | low/medium/high |
| 查询缓存命中率 | Gauge | datasource | 缓存命中/未命中 |
| 沙箱执行成功率 | Counter | status | success/failed/timeout |
| 向量检索延迟 | Histogram | - | 检索耗时 |
| DAG 执行时长 | Histogram | task_type | SQL/Python/Search |
| **LLM 调用次数** | Counter | model, status, tenant_id | 按模型/租户统计 |
| **LLM 调用延迟** | Histogram | model, tenant_id | 按模型/租户分布 |
| **LLM Token 消耗** | Counter | model, type(prompt/completion), tenant_id | Token 用量 |
| **LLM 调用成本** | Counter | model, tenant_id | 累计成本（元） |
| **LLM 月度预算使用率** | Gauge | tenant_id | 已用/预算百分比，>80% 告警 |
| **用户 SQL 编辑率** | Gauge | tenant_id | 编辑次数/总次数，衡量 NL2SQL 质量 |
| **用户满意度** | Counter | tenant_id, satisfaction | positive/negative 计数 |
| **查询配额使用率** | Gauge | tenant_id, user_id | 已用/配额百分比 |
| **数据源健康度** | Gauge | datasource, status | healthy/degraded/down 计数 |

## 3. 告警规则

### 3.1 P0 告警（立即响应）

| 告警 | 条件 | 响应 |
|------|------|------|
| 服务不可用 | 任意核心服务 down | 5 分钟内响应 |
| 错误率飙升 | 5xx 错误率 > 5%（持续 2 分钟） | 10 分钟内响应 |
| 数据库连接池耗尽 | active connections > 90% pool | 10 分钟内响应 |
| LLM API 全部不可用 | 所有 provider 错误率 > 50% | 10 分钟内响应 |

### 3.2 P1 告警（工作时间内响应）

| 告警 | 条件 | 响应 |
|------|------|------|
| 延迟升高 | P95 > 5s（持续 5 分钟） | 当日内 |
| 沙箱执行失败率 | 失败率 > 20% | 当日内 |
| 队列积压 | 待消费消息 > 10000 | 当日内 |
| 磁盘空间 | > 80% 使用率 | 当日内 |

### 3.3 P2 告警（日常关注）

| 告警 | 条件 |
|------|------|
| 缓存命中率下降 | < 50% |
| 慢查询增多 | > 10 条/分钟 |
| Pod 重启 | 任意 Pod restart |
| SSL 证书即将过期 | < 30 天 |

### 3.4 告警配置示例 (Prometheus)

```yaml
groups:
  - name: datapilot-critical
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[2m]))
          / sum(rate(http_requests_total[2m])) > 0.05
        for: 2m
        labels:
          severity: P0
        annotations:
          summary: "服务 {{ $labels.service }} 错误率 > 5%"

      - alert: LLMTimeoutHigh
        expr: |
          sum(rate(llm_requests_total{status="timeout"}[5m]))
          / sum(rate(llm_requests_total[5m])) > 0.2
        for: 5m
        labels:
          severity: P1
        annotations:
          summary: "LLM 超时率 > 20%"
```

## 4. Grafana 看板

每个微服务至少包含以下面板：

1. **Overview**：请求 QPS、错误率、P50/P95/P99 延迟
2. **Dependencies**：下游服务调用延迟和错误率
3. **Resources**：CPU、内存、连接池、线程池
4. **Business**：业务指标（查询量、缓存命中率等）

## 5. 链路追踪 (OpenTelemetry + Jaeger)

### 5.1 Span 命名

```
{service}.{operation}

示例：
agent-gateway.process_query
sql-generator.generate_sql
query-executor.execute
llm-provider.call_deepseek
```

### 5.2 关键 Span

NL2SQL 完整链路的 Span 层级：

```
agent-gateway.process_query (root)
├── session-service.load_context
├── agent-gateway.parse_intent
│   └── llm-provider.call_deepseek
├── semantic-service.resolve
│   ├── pgvector.search
│   └── retrieval.rerank
├── sql-generator.generate
│   ├── sql-generator.schema_linking
│   ├── llm-provider.call_deepseek
│   └── sql-validator.validate
└── query-executor.execute
    ├── datasource.connect
    └── datasource.query
```

### 5.3 Trace 传播

```python
from opentelemetry import propagate

# gRPC 元数据传播
metadata = propagate.inject({})
```

- 使用 W3C Trace Context 标准（`traceparent` Header）
- 跨服务调用自动传播 trace_id
- 所有日志自动关联当前 trace_id
