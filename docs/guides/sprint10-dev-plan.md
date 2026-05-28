# Sprint 10: Memory + 优化 + 生产就绪 — 并行开发计划

> 目标：对话记忆系统 + 查询缓存 + 生产级可观测性 + 错误恢复 + 前端收尾
> 依赖：Sprint 1-9 全部完成
> 本 Sprint 为 Phase2 最终 Sprint

## 并行 Track 划分

### Track A: 对话记忆系统

**目录隔离**: `libs/datapilot-memory/src/datapilot_memory/`
**无外部依赖**，纯数据结构和存储接口。

| # | 任务 | 产出文件 |
|---|------|----------|
| A-1 | 记忆数据模型 | `models.py` — MemoryType(StrEnum), MemoryEntry, ConversationContext, ConversationTurn |
| A-2 | 记忆管理器 | `manager.py` — MemoryManager（添加/检索/摘要/过期清理） |
| A-3 | 上下文窗口 | `context_window.py` — ContextWindowManager（Token 计数、滑动窗口、重要记忆优先保留） |
| A-4 | 记忆存储 | `store.py` — MemoryStore（内存存储 + Redis 可选后端） |
| A-5 | 对话摘要 | `summarizer.py` — ConversationSummarizer（规则摘要 + LLM 摘要） |
| A-6 | 单元测试 | `tests/unit/test_memory/` |

**接口定义**:
```python
class MemoryType(StrEnum):
    EPHEMERAL = "ephemeral"   # 临时记忆（当前对话轮次）
    SHORT_TERM = "short_term" # 短期记忆（当前会话）
    LONG_TERM = "long_term"   # 长期记忆（跨会话持久化）

@dataclass
class ConversationTurn:
    role: str  # "user" / "assistant" / "system"
    content: str
    timestamp: str = ""
    tokens: int = 0
    metadata: dict = field(default_factory=dict)

@dataclass
class MemoryEntry:
    entry_id: str
    memory_type: MemoryType
    content: str
    summary: str = ""
    session_id: str = ""
    created_at: str = ""
    expires_at: str = ""
    relevance_score: float = 0.0
    metadata: dict = field(default_factory=dict)

@dataclass
class ConversationContext:
    session_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    memories: list[MemoryEntry] = field(default_factory=list)
    summary: str = ""
    total_tokens: int = 0
    max_tokens: int = 8000

class ContextWindowManager:
    def __init__(self, max_tokens: int = 8000): ...

    def build_context(
        self,
        turns: list[ConversationTurn],
        system_prompt: str = "",
        memories: list[MemoryEntry] | None = None,
    ) -> list[dict]:
        """构建上下文消息列表，自动裁剪以适应 token 窗口。
        策略：system_prompt > 最新对话 > 重要记忆 > 早期对话
        """

    def estimate_tokens(self, text: str) -> int:
        """估算文本 token 数（按字符数/4 粗略估算）。"""

class MemoryManager:
    def __init__(self, store: MemoryStore | None = None): ...

    def add_turn(self, session_id: str, role: str, content: str, metadata: dict | None = None) -> ConversationTurn: ...
    def add_memory(self, entry: MemoryEntry) -> str: ...
    def get_context(self, session_id: str) -> ConversationContext: ...
    def search_memories(self, query: str, limit: int = 5) -> list[MemoryEntry]: ...
    def summarize_conversation(self, session_id: str) -> str: ...
    def cleanup_expired(self) -> int: ...
```

---

### Track B: 查询缓存层

**目录隔离**: `libs/datapilot-cache/src/datapilot_cache/`
**无外部依赖**，纯缓存抽象。

| # | 任务 | 产出文件 |
|---|------|----------|
| B-1 | 缓存数据模型 | `models.py` — CacheKey, CacheEntry, CacheStats, TTLStrategy |
| B-2 | 缓存管理器 | `cache.py` — CacheManager（内存 LRU + 可选 Redis 后端） |
| B-3 | 查询结果缓存 | `query_cache.py` — QueryResultCache（SQL 结果缓存、语义键生成、自动失效） |
| B-4 | 语义缓存 | `semantic_cache.py` — SemanticCache（相似问题命中、余弦相似度） |
| B-5 | 单元测试 | `tests/unit/test_cache/` |

**接口定义**:
```python
@dataclass
class CacheKey:
    namespace: str
    key: str
    version: str = "v1"

@dataclass
class CacheEntry:
    key: CacheKey
    value: Any
    created_at: float  # time.time()
    ttl: float  # 秒
    hit_count: int = 0
    size_bytes: int = 0
    tags: list[str] = field(default_factory=list)

@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_size_bytes: int = 0
    entry_count: int = 0

class CacheManager:
    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0): ...

    def get(self, key: CacheKey) -> Any | None: ...
    def set(self, key: CacheKey, value: Any, ttl: float | None = None) -> None: ...
    def delete(self, key: CacheKey) -> bool: ...
    def clear(self, namespace: str | None = None) -> int: ...
    def get_stats(self) -> CacheStats: ...
    def cleanup_expired(self) -> int: ...

class QueryResultCache:
    def __init__(self, cache: CacheManager): ...

    def generate_key(self, sql: str, params: tuple = (), datasource_id: str = "") -> CacheKey: ...
    def get(self, sql: str, params: tuple = (), datasource_id: str = "") -> Any | None: ...
    def set(self, sql: str, result: Any, ttl: float = 60.0, datasource_id: str = "") -> None: ...
    def invalidate_datasource(self, datasource_id: str) -> int: ...

class SemanticCache:
    def __init__(self, cache: CacheManager, similarity_threshold: float = 0.85): ...

    def get(self, question: str, session_id: str = "") -> Any | None: ...
    def set(self, question: str, result: Any, ttl: float = 300.0, session_id: str = "") -> None: ...
```

---

### Track C: 生产级可观测性

**目录隔离**: `services/agent-service/src/datapilot_agent/observability/`
**依赖**: datapilot-common（日志、指标）

| # | 任务 | 产出文件 |
|---|------|----------|
| C-1 | 健康检查增强 | `health.py` — HealthChecker（数据库/Redis/LLM/存储多组件健康检查） |
| C-2 | 请求指标 | `metrics.py` — RequestMetrics（请求计数、延迟直方图、错误率、活跃会话数） |
| C-3 | 中间件 | `middleware.py` — RequestTraceMiddleware（请求ID注入、耗时记录、结构化日志） |
| C-4 | 电路断路器 | `circuit_breaker.py` — CircuitBreaker（三态：CLOSED/OPEN/HALF_OPEN，失败计数，自动恢复） |
| C-5 | 重试器 | `retry.py` — RetryExecutor（指数退避、最大重试、可重试异常判断） |
| C-6 | 单元测试 | `tests/unit/test_observability/` |

**接口定义**:
```python
class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class HealthCheckResult:
    component: str
    status: HealthStatus
    latency_ms: float = 0.0
    message: str = ""
    details: dict = field(default_factory=dict)

class HealthChecker:
    def check_all(self) -> dict[str, HealthCheckResult]: ...
    def check_database(self) -> HealthCheckResult: ...
    def check_redis(self) -> HealthCheckResult: ...
    def check_llm(self) -> HealthCheckResult: ...

class CircuitState(StrEnum):
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断状态
    HALF_OPEN = "half_open" # 半开状态

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ): ...

    async def call(self, func: Callable, *args, **kwargs) -> Any: ...
    def get_state(self) -> CircuitState: ...
    def get_stats(self) -> dict: ...
    def reset(self) -> None: ...

class RetryExecutor:
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
    ): ...

    async def execute(self, func: Callable, *args, **kwargs) -> Any: ...
```

---

### Track D: Agent Service 集成

**目录隔离**: `services/agent-service/src/datapilot_agent/`
**依赖**: Track A（Memory）、Track B（Cache）、Track C（Observability）

| # | 任务 | 产出文件 |
|---|------|----------|
| D-1 | Agent 对话集成 | 修改 `api/routes/chat.py` — 集成 MemoryManager，对话上下文注入 |
| D-2 | 查询缓存集成 | 修改 SQL 执行流程 — 集成 QueryResultCache |
| D-3 | 健康检查 API | 修改 `main.py` — 增强 /health 端点，返回多组件状态 |
| D-4 | 中间件注册 | 修改 `main.py` — 注册 RequestTraceMiddleware |
| D-5 | LLM 降级 | `llm_fallback.py` — LLM 调用失败时的降级策略 |
| D-6 | 单元测试 | `tests/unit/test_agent_integration/` |

---

### Track E: 前端收尾 + Error Boundary

**目录隔离**: `web/packages/chat-ui/src/`
**无后端依赖**。

| # | 任务 | 产出文件 |
|---|------|----------|
| E-1 | Error Boundary | `components/ErrorBoundary.tsx` — 全局错误边界 |
| E-2 | 会话持久化 | 修改 `stores/chatStore.ts` — localStorage 会话恢复 |
| E-3 | 加载骨架屏 | `components/Skeleton.tsx` — 聊天/仪表板骨架屏 |
| E-4 | 404 页面 | `pages/NotFound.tsx` |
| E-5 | 性能优化 | `hooks/useDebounce.ts`、`hooks/useThrottle.ts` |
| E-6 | 单元测试 | 扩展前端测试（如已有框架） |

---

## Track 间文件隔离矩阵

| 目录 | Track A | Track B | Track C | Track D | Track E |
|------|---------|---------|---------|---------|---------|
| `libs/datapilot-memory/` | **写** | - | - | 读 | - |
| `libs/datapilot-cache/` | - | **写** | - | 读 | - |
| `agent-service/observability/` | - | - | **写** | 读 | - |
| `agent-service/api/routes/chat.py` | - | - | - | 改 | - |
| `agent-service/main.py` | - | - | - | 改 | - |
| `agent-service/llm_fallback.py` | - | - | - | **写** | - |
| `chat-ui/src/` | - | - | - | - | **写** |
| `tests/unit/test_memory/` | **写** | - | - | - | - |
| `tests/unit/test_cache/` | - | **写** | - | - | - |
| `tests/unit/test_observability/` | - | - | **写** | - | - |
| `tests/unit/test_agent_integration/` | - | - | - | **写** | - |

**冲突风险点**:
- `chat.py`：仅 Track D 修改。
- `main.py`：仅 Track D 修改。
- 无跨 Track 文件冲突。

## 验证方式

- Track A: `uv run pytest tests/unit/test_memory/ -v`
- Track B: `uv run pytest tests/unit/test_cache/ -v`
- Track C: `uv run pytest tests/unit/test_observability/ -v`
- Track D: `uv run pytest tests/unit/test_agent_integration/ -v`
- Track E: TypeScript 编译通过
