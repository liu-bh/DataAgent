# Sprint 4: Execution Layer — 并行开发计划

> 目标：多数据源连接、异步执行、结果缓存、细粒度权限
> 依赖：Sprint 3a (LLM/SQL-AST) + Sprint 3b (Validation/Guardrail)

## 并行 Track 划分

### Track A: 多数据源连接器 + 重试策略

**目录隔离**: `services/query-executor-service/src/datapilot_queryexec/connectors/`
**依赖**: `datapilot-sql`（Dialect）

| # | 任务 | 产出文件 |
|---|------|----------|
| A-1 | 数据源能力矩阵 | `capabilities.py` — 各数据源 SQL 语法支持情况（方言兼容性参考表） |
| A-2 | 连接器基类 | `base.py` — BaseConnector ABC（connect/disconnect/execute/health_check） |
| A-3 | MySQL 连接器 | `mysql.py` — aiomysql 连接池（pool_size=10），支持读超时 |
| A-4 | PostgreSQL 连接器 | `postgresql.py` — asyncpg 连接池（pool_size=10） |
| A-5 | Doris/StarRocks 连接器 | `doris.py` — HTTP API / MySQL 协议连接器（pool_size=20） |
| A-6 | ClickHouse 连接器 | `clickhouse.py` — asynch 连接池（pool_size=15） |
| A-7 | 连接器工厂 | `factory.py` — ConnectorFactory 根据数据源类型创建连接器 |
| A-8 | 差异化重试 | `retry.py` — RetryPolicy（临时错误重试 3 次，语法错误直接终止） |
| A-9 | 单元测试 | `tests/unit/test_connectors/` |

**接口定义**:
```python
class BaseConnector(ABC):
    @abstractmethod
    async def connect(self) -> None: ...
    @abstractmethod
    async def disconnect(self) -> None: ...
    @abstractmethod
    async def execute(self, sql: str, params: dict | None = None) -> ExecuteResult: ...
    @abstractmethod
    async def health_check(self) -> ConnectorHealth: ...

@dataclass
class ExecuteResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_time_ms: float
    error: str = ""

@dataclass
class ConnectorHealth:
    healthy: bool
    latency_ms: float = 0.0
    pool_size: int = 0
    pool_used: int = 0
    error: str = ""

class RetryPolicy:
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        ...
    def should_retry(self, error: Exception) -> bool:
        """语法错误直接终止，连接超时/死锁等临时错误重试。"""
        ...
    async def wait(self, attempt: int) -> None:
        """指数退避等待。"""
        ...
```

---

### Track B: 异步执行 + 结果格式化 + 分页

**目录隔离**: `services/query-executor-service/src/datapilot_queryexec/executor/`
**依赖**: Track A（连接器）

| # | 任务 | 产出文件 |
|---|------|----------|
| B-1 | 执行引擎 | `engine.py` — QueryEngine（提交任务 → 异步执行 → 轮询结果） |
| B-2 | 任务状态管理 | `task_manager.py` — AsyncTaskManager（内存 task store + 状态机） |
| B-3 | 统一结果格式化 | `formatter.py` — ResultFormatter（JSON/CSV 输出格式） |
| B-4 | 大结果集分页 | `pagination.py` — CursorPaginator（游标分页 + LIMIT 1000 默认） |
| B-5 | 数据模型 | `models.py` — QueryTask, TaskStatus, QueryResult, FormatType Pydantic 模型 |
| B-6 | API 路由 | `../api/routes/execute.py` — POST /execute（同步）, POST /execute/async（异步）, GET /execute/{task_id}/status, GET /execute/{task_id}/result |
| B-7 | FastAPI 入口 | `main.py` — 挂载路由（替换现有 __init__.py 中的 app） |
| B-8 | pyproject.toml 更新 | 添加 structlog, redis 依赖 |
| B-9 | 单元测试 | `tests/unit/test_executor/` |

**接口定义**:
```python
class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class QueryTask(BaseModel):
    task_id: str
    sql: str
    dialect: str
    status: TaskStatus = TaskStatus.PENDING
    result: QueryResult | None = None
    error: str = ""
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

class QueryResult(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_time_ms: float
    format: Literal["json", "csv"] = "json"
```

---

### Track C: 结果缓存 + 数据新鲜度

**目录隔离**: `services/query-executor-service/src/datapilot_queryexec/cache/`
**依赖**: Redis（小结果）, MinIO（大结果）

| # | 任务 | 产出文件 |
|---|------|----------|
| C-1 | 分级缓存策略 | `strategy.py` — CacheStrategy（<1MB → Redis, ≥1MB → MinIO, TTL 配置） |
| C-2 | Redis 缓存 | `redis_cache.py` — RedisResultCache（JSON 序列化 + TTL） |
| C-3 | MinIO 缓存 | `minio_cache.py` — MinIOResultCache（CSV/PARQUET 序列化 + bucket 管理） |
| C-4 | 缓存管理器 | `manager.py` — ResultCacheManager（统一接口，自动选择存储后端） |
| C-5 | 数据新鲜度标注 | `freshness.py` — FreshnessChecker（实时/小时级/T+1 标注，结果附带 data_freshness） |
| C-6 | 单元测试 | `tests/unit/test_cache/` |

**接口定义**:
```python
class FreshnessLevel(StrEnum):
    REALTIME = "realtime"       # 实时
    HOURLY = "hourly"           # 小时级
    DAILY = "daily"             # T+1 日级别
    UNKNOWN = "unknown"         # 未知

@dataclass
class CacheResult:
    hit: bool
    data: bytes | None = None
    source: str = ""            # "redis" / "minio" / "miss"
    freshness: FreshnessLevel = FreshnessLevel.UNKNOWN
    data_cutoff: str = ""       # 数据截止时间
    ttl_remaining: int = 0
```

---

### Track D: RBAC 权限 + 数据脱敏

**目录隔离**: `services/query-executor-service/src/datapilot_queryexec/rbac/`
**依赖**: `datapilot-sql`（AST transformer）, `datapilot-common`（exceptions）

| # | 任务 | 产出文件 |
|---|------|----------|
| D-1 | 行级权限 | `row_filter.py` — RowFilter（通过 AST 注入 WHERE 条件实现行级权限） |
| D-2 | 列级权限 | `column_filter.py` — ColumnFilter（通过 AST 移除 SELECT 列实现列权限控制） |
| D-3 | 数据脱敏 | `masking.py` — DataMasker（手机号/身份证/银行卡/邮箱等脱敏规则） |
| D-4 | 操作权限 | `operation_guard.py` — OperationGuard（只读/可导出/可执行 DDL 操作级权限） |
| D-5 | 权限检查器 | `checker.py` — RBACChecker（组合行级+列级+操作级权限检查） |
| D-6 | Pydantic 模型 | `models.py` — PermissionRule, MaskRule, UserPermission, RBACCheckResult |
| D-7 | 单元测试 | `tests/unit/test_rbac/` |

**接口定义**:
```python
class OperationType(StrEnum):
    READ = "read"
    EXPORT = "export"
    DDL = "ddl"
    WRITE = "write"

@dataclass
class RBACCheckResult:
    allowed: bool
    filtered_sql: str              # 权限过滤后的 SQL
    masked_columns: list[str]      # 被脱敏的列
    removed_columns: list[str]     # 被移除的列（列级权限）
    injected_where: str = ""       # 注入的 WHERE 条件（行级权限）
    blocked_reason: str = ""
```

---

### Track E: 数据源健康监控 + API 集成

**目录隔离**:
- `services/query-executor-service/src/datapilot_queryexec/monitor/`
- `services/query-executor-service/src/datapilot_queryexec/api/`

| # | 任务 | 产出文件 |
|---|------|----------|
| E-1 | 健康监控 | `monitor/health.py` — DataSourceMonitor（定期 health_check，连接池使用率、平均延迟） |
| E-2 | 自动摘除 | `monitor/circuit.py` — DataSourceCircuitBreaker（不可达自动摘除，半开探测恢复） |
| E-3 | 监控指标 | `monitor/metrics.py` — Prometheus 指标（连接池、延迟、错误率） |
| E-4 | 管理端点 | `api/routes/health.py` — GET /datasources/health（所有数据源健康状态），POST /datasources/{id}/check（单数据源检查） |
| E-5 | 管理端点 | `api/routes/config.py` — GET/POST /datasources/config（数据源配置 CRUD） |
| E-6 | 单元测试 | `tests/unit/test_monitor/` |

**接口定义**:
```python
@dataclass
class DataSourceStatus:
    datasource_id: str
    name: str
    dialect: str
    healthy: bool
    latency_ms: float = 0.0
    pool_size: int = 0
    pool_used: int = 0
    circuit_state: str = "closed"   # closed / open / half_open
    last_check_at: datetime | None = None
    error_count: int = 0
```

---

## Track 间文件隔离矩阵

| 目录 | Track A | Track B | Track C | Track D | Track E |
|------|---------|---------|---------|---------|---------|
| `queryexec/connectors/` | **写** | 读 | - | - | 读 |
| `queryexec/executor/` | - | **写** | - | - | - |
| `queryexec/cache/` | - | - | **写** | - | - |
| `queryexec/rbac/` | - | - | - | **写** | - |
| `queryexec/monitor/` | - | - | - | - | **写** |
| `queryexec/api/routes/` | - | 写(execute) | - | - | 写(health/config) |
| `queryexec/main.py` | - | 写 | - | - | - |
| `queryexec/__init__.py` | - | 改 | - | - | - |
| `queryexec/pyproject.toml` | - | 改 | - | - | - |
| `tests/unit/test_connectors/` | **写** | - | - | - | - |
| `tests/unit/test_executor/` | - | **写** | - | - | - |
| `tests/unit/test_cache/` | - | - | **写** | - | - |
| `tests/unit/test_rbac/` | - | - | - | **写** | - |
| `tests/unit/test_monitor/` | - | - | - | - | **写** |

**冲突风险点**:
- `api/routes/`：Track B 和 Track E 都写。**约定：Track B 创建 execute.py，Track E 创建 health.py 和 config.py，无冲突。**
- `__init__.py` 和 `pyproject.toml`：仅 Track B 修改。

## 验证方式

- Track A: `uv run pytest tests/unit/test_connectors/ -v`
- Track B: `uv run pytest tests/unit/test_executor/ -v`
- Track C: `uv run pytest tests/unit/test_cache/ -v`
- Track D: `uv run pytest tests/unit/test_rbac/ -v`
- Track E: `uv run pytest tests/unit/test_monitor/ -v`
