# Sprint 6: 服务拆分 + DAG Runtime — 并行开发计划

> 目标：Agent 服务拆分 + DAG Builder/Executor 运行时
> 依赖：Phase1 全部产出

## 并行 Track 划分

### Track A: DAG 核心模型 + Builder

**目录隔离**: `libs/datapilot-dag/src/datapilot_dag/`
**无外部依赖**，纯数据结构和算法。

| # | 任务 | 产出文件 |
|---|------|----------|
| A-1 | DAG 数据模型 | `models.py` — DAGNode, DAGEdge, DAGraph, TaskType 枚举, TaskStatus 枚举 |
| A-2 | DAG Builder | `builder.py` — DAGBuilder（添加节点、添加边、拓扑排序、循环检测） |
| A-3 | 执行计划 | `plan.py` — ExecutionPlan（执行顺序、并行分组、依赖关系） |
| A-4 | 序列化 | `serialization.py` — DAG 的 JSON 序列化/反序列化 |
| A-5 | 单元测试 | `tests/unit/test_dag/` |

**接口定义**:
```python
class TaskType(StrEnum):
    SQL = "sql"
    PYTHON = "python"
    SEARCH = "search"
    ACTION = "action"
    LLM = "llm"

class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"

@dataclass
class DAGNode:
    node_id: str
    task_type: TaskType
    config: dict[str, Any]       # 任务配置
    inputs: list[str]            # 输入节点 ID
    outputs: list[str]           # 输出节点 ID
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class DAGEdge:
    source_id: str
    target_id: str
    condition: str = ""          # 条件表达式（可选，Phase2 支持条件分支）

class DAGraph:
    nodes: dict[str, DAGNode]
    edges: list[DAGEdge]

    def topological_sort(self) -> list[list[str]]:
        """拓扑排序，返回并行分组（同一层级可并行执行）。"""

    def detect_cycle(self) -> bool: ...

    def add_node(self, node: DAGNode) -> None: ...

    def add_edge(self, edge: DAGEdge) -> None: ...

    def validate(self) -> list[str]:  # 返回错误列表 ...

class DAGBuilder:
    @staticmethod
    def build(nodes: list[DAGNode], edges: list[DAGEdge]) -> DAGraph: ...

    @staticmethod
    def from_json(data: dict) -> DAGraph: ...
```

### Track B: DAG Executor + 调度器

**目录隔离**: `libs/datapilot-dag/src/datapilot_dag/executor/`
**依赖**: Track A（DAG 模型）

| # | 任务 | 产出文件 |
|---|------|----------|
| B-1 | 任务执行器基类 | `base.py` — BaseTaskExecutor ABC（execute/cancel/get_status） |
| B-2 | SQL 任务执行器 | `sql_executor.py` — SQLTaskExecutor（调用 query-executor-service） |
| B-3 | LLM 任务执行器 | `llm_executor.py` — LLMTaskExecutor（调用 LLM Router） |
| B-4 | Python 任务执行器（Stub） | `python_executor.py` — PythonTaskExecutor（Sprint 7 实现，这里 stub） |
| B-5 | 执行调度器 | `scheduler.py` — DAGScheduler（异步并行调度 + 重试 + 超时控制） |
| B-6 | 执行结果 | `result.py` — TaskResult, DAGResult 数据模型 |
| B-7 | 单元测试 | `tests/unit/test_executor/` |

**接口定义**:
```python
@dataclass
class TaskResult:
    node_id: str
    status: TaskStatus
    output: Any = None
    error: str = ""
    execution_time_ms: float = 0.0
    retries: int = 0

@dataclass
class DAGResult:
    dag_id: str
    status: TaskStatus
    task_results: dict[str, TaskResult]
    total_time_ms: float = 0.0
    error: str = ""

class DAGScheduler:
    def __init__(
        self,
        max_depth: int = 5,
        max_retry: int = 3,
        task_timeout: float = 30.0,
    ): ...

    async def execute(self, dag: DAGraph, context: dict[str, Any] | None = None) -> DAGResult:
        """执行 DAG，按拓扑排序并行调度各层级任务。"""

    async def _execute_level(self, level: list[str], dag: DAGraph, context: dict, results: dict) -> None:
        """并行执行同一层级的所有任务。"""

    async def _execute_task_with_retry(self, node: DAGNode, context: dict) -> TaskResult:
        """执行单个任务，带重试逻辑（指数退避）。"""
```

### Track C: Agent Service 拆分

**目录隔离**: `services/agent-service/src/datapilot_agent/`
**依赖**: Track A/B（DAG runtime）

| # | 任务 | 产出文件 |
|---|------|----------|
| C-1 | Agent Gateway 入口 | `gateway.py` — FastAPI app（从现有 main.py 拆分，添加 DAG 路由） |
| C-2 | Chat Service | `chat_service.py` — 聊天服务（从现有 chat.py 抽取业务逻辑） |
| C-3 | DAG API 路由 | `api/routes/dag.py` — POST /dag/execute, GET /dag/{dag_id}/status |
| C-4 | NL2SQL DAG 构建 | `dag/nl2sql_dag.py` — 将 NL2SQL Pipeline 构建为 DAG（10 步编排） |
| C-5 | DAG 持久化 | `dag/store.py` — DAG 执行记录存储（内存，后续接 DB） |
| C-6 | 单元测试 | `tests/unit/test_agent_dag/` |

**NL2SQL DAG 构建**:
```python
class NL2SQLDAGBuilder:
    """将 NL2SQL Pipeline 步骤构建为 DAG。"""

    def build(self, question: str, context: dict) -> DAGraph:
        """
        节点:
        1. intent_route (LLM) — 意图路由
        2. intent_parse (LLM) — 意图解析（依赖 1）
        3. schema_link (计算) — Schema Linking（依赖 2）
        4. prompt_build (计算) — Prompt 组装（依赖 3）
        5. sql_generate (LLM) — SQL 生成（依赖 4）
        6. sql_validate (计算) — SQL 验证（依赖 5）
        7. sql_correct (LLM, conditional) — 自纠错（依赖 6, 条件: 验证失败）
        8. sql_explain (LLM) — SQL 解释（依赖 5 或 7）
        """
```

### Track D: Semantic Service 拆分

**目录隔离**: `services/semantic-service/src/datapilot_semantic/`
**依赖**: 无新依赖，纯重构

| # | 任务 | 产出文件 |
|---|------|----------|
| D-1 | Semantic Service 入口重构 | 重构 `main.py` — 分离 Semantic CRUD 和 Metadata 管理 |
| D-2 | 元数据服务抽取 | `metadata/service.py` — MetadataService（数据源管理逻辑抽取） |
| D-3 | 语义模型服务抽取 | `models/service.py` — SemanticModelService（语义模型 CRUD 逻辑抽取） |
| D-4 | 向量检索服务抽取 | `retrieval/service.py` — RetrievalService（向量搜索逻辑抽取） |
| D-5 | 单元测试 | `tests/unit/test_semantic_service/` — 服务层测试 |

### Track E: DAG 执行进度可视化

**目录隔离**: `web/packages/chat-ui/src/`
**依赖**: Track C（DAG API）

| # | 任务 | 产出文件 |
|---|------|----------|
| E-1 | DAG 进度组件 | `components/DAGProgress.tsx` — DAG 节点状态可视化（流程图样式） |
| E-2 | DAG 执行状态 Store | `stores/dagStore.ts` — DAG 执行状态管理 |
| E-3 | API 层 | `api/dag.ts` — DAG 执行 API |
| E-4 | 类型定义 | `types/dag.ts` — DAG 相关类型 |
| E-5 | MessageBubble 集成 | 扩展 `MessageBubble.tsx` — 查询中显示 DAG 执行进度 |
| E-6 | MSW Mock | 扩展 `mocks/handlers.ts` — DAG API Mock |

**DAG 进度组件设计**:
- 垂直流程图样式，每个节点显示：任务名 + 状态图标（pending/running/done/failed）
- 同一层级节点水平排列（并行）
- 连接线带箭头
- 运行中节点显示脉冲动画
- 失败节点显示红色错误标记

---

## Track 间文件隔离矩阵

| 目录 | Track A | Track B | Track C | Track D | Track E |
|------|---------|---------|---------|---------|---------|
| `libs/datapilot-dag/` | 写(models/builder) | 写(executor/) | 读 | - | - |
| `agent-service/src/` | - | - | 写 | - | - |
| `semantic-service/src/` | - | - | - | 写 | - |
| `chat-ui/src/` | - | - | - | - | 写 |
| `tests/unit/test_dag/` | 写 | - | - | - | - |
| `tests/unit/test_executor/` | - | 写 | - | - | - |
| `tests/unit/test_agent_dag/` | - | - | 写 | - | - |
| `tests/unit/test_semantic_service/` | - | - | - | 写 | - |

**无跨 Track 文件冲突。**

## 验证方式

- Track A: `uv run pytest tests/unit/test_dag/ -v`
- Track B: `uv run pytest tests/unit/test_executor/ -v`
- Track C: `uv run pytest tests/unit/test_agent_dag/ -v`
- Track D: `uv run pytest tests/unit/test_semantic_service/ -v`
- Track E: TypeScript 编译通过
