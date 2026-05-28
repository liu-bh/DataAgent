# Sprint 8: Tool Registry + RCA — 并行开发计划

> 目标：工具注册中心 + Function Calling 集成 + 根因分析（RCA）+ 数据解释
> 依赖：Sprint 7（Python Sandbox）、Sprint 6（DAG Runtime）

## 并行 Track 划分

### Track A: Tool Registry 核心库

**目录隔离**: `libs/datapilot-tools/src/datapilot_tools/`
**无外部依赖**，纯抽象层 + 注册表。

| # | 任务 | 产出文件 |
|---|------|----------|
| A-1 | 工具数据模型 | `models.py` — ToolDefinition, ToolParameter, ToolCapability, ToolCategory 枚举 |
| A-2 | 工具注册表 | `registry.py` — ToolRegistry（register/unregister/discover/search_by_capability/get_by_name） |
| A-3 | 工具描述生成 | `description.py` — ToolDescriptionBuilder（从 ToolDefinition 生成 LLM Function Calling JSON Schema） |
| A-4 | 参数校验 | `validator.py` — ToolParameterValidator（参数类型/必填/枚举/范围校验） |
| A-5 | 工具执行器基类 | `executor.py` — BaseToolExecutor ABC（execute/validate/get_info） |
| A-6 | 内置工具注册 | `builtin.py` — 注册内置工具（SQL 查询、Python 执行、数据源健康检查、语义模型搜索） |
| A-7 | 单元测试 | `tests/unit/test_tools/` |

**接口定义**:
```python
class ToolCategory(StrEnum):
    SQL = "sql"
    PYTHON = "python"
    SEARCH = "search"
    ANALYSIS = "analysis"
    SYSTEM = "system"

@dataclass
class ToolParameter:
    name: str
    type: str                   # string / integer / float / boolean / array / object
    description: str
    required: bool = True
    default: Any = None
    enum: list[str] | None = None
    minimum: float | None = None
    maximum: float | None = None

@dataclass
class ToolDefinition:
    name: str
    description: str
    category: ToolCategory
    parameters: list[ToolParameter] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)
    version: str = "1.0.0"
    timeout_seconds: float = 30.0
    required_permissions: list[str] = field(default_factory=list)

class ToolRegistry:
    def register(self, tool: ToolDefinition, executor: BaseToolExecutor) -> None: ...
    def unregister(self, name: str) -> bool: ...
    def discover(self) -> list[ToolDefinition]: ...
    def get(self, name: str) -> ToolDefinition | None: ...
    def get_executor(self, name: str) -> BaseToolExecutor | None: ...
    def search_by_category(self, category: ToolCategory) -> list[ToolDefinition]: ...
    def search_by_capability(self, keyword: str) -> list[ToolDefinition]: ...
    def to_function_schemas(self) -> list[dict]: ...  # 生成 OpenAI Function Calling 格式

class BaseToolExecutor(ABC):
    @abstractmethod
    async def execute(self, name: str, params: dict[str, Any]) -> dict[str, Any]: ...
    @abstractmethod
    async def validate(self, name: str, params: dict[str, Any]) -> list[str]: ...
```

---

### Track B: Function Calling 集成

**目录隔离**: `libs/datapilot-llm/src/datapilot_llm/`
**依赖**: Track A（ToolRegistry）

| # | 任务 | 产出文件 |
|---|------|----------|
| B-1 | Function Calling 协议 | `function_calling.py` — FunctionCallRequest, FunctionCallResult, ToolCall 数据模型 |
| B-2 | 工具选择器 | `tool_selector.py` — ToolSelector（根据用户意图选择工具，支持多工具组合） |
| B-3 | Function Calling 执行器 | `tool_executor.py` — FunctionCallingExecutor（编排：解析调用→执行→返回结果→可选多轮） |
| B-4 | Prompt 适配 | `prompts.py` — 工具调用相关 Prompt 模板（系统角色描述、工具使用说明） |
| B-5 | 集成到 LLM Router | 修改 `router.py` — 添加 tools 参数和 function_call 响应处理 |
| B-6 | 单元测试 | `tests/unit/test_function_calling/` |

**接口定义**:
```python
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

@dataclass
class FunctionCallResult:
    tool_calls: list[ToolCall]
    results: list[dict[str, Any]]
    total_time_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

class FunctionCallingExecutor:
    def __init__(self, registry: ToolRegistry, llm_router: LLMRouter): ...

    async def execute(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
        max_rounds: int = 5,
    ) -> FunctionCallResult:
        """执行 Function Calling 循环。

        流程：
        1. 构建 messages（系统角色 + 工具定义 + 用户消息）
        2. 调用 LLM（带 tools 参数）
        3. 如果 LLM 返回 tool_calls → 执行工具 → 将结果追加到 messages → 重新调用
        4. 最多 max_rounds 轮
        5. 返回最终结果
        """
```

---

### Track C: RCA 根因分析引擎

**目录隔离**: `services/agent-service/src/datapilot_agent/rca/`
**依赖**: Track A（ToolRegistry）、Sprint 3a（LLM Router）、Sprint 4（查询执行器）

| # | 任务 | 产出文件 |
|---|------|----------|
| C-1 | 异常检测器 | `anomaly_detector.py` — AnomalyDetector（统计异常检测：Z-score / IQR / 同比环比） |
| C-2 | 维度下钻 | `drill_down.py` — DimensionDrillDown（按维度逐层拆解数据，找出异常贡献最大的维度） |
| C-3 | 归因分析 | `attribution.py` — AttributionAnalyzer（计算各维度对异常的贡献度百分比） |
| C-4 | RCA 编排器 | `orchestrator.py` — RCAOrchestrator（异常检测→维度下钻→归因分析的 DAG 编排） |
| C-5 | 数据解释 | `interpreter.py` — DataInterpreter（趋势分析、Key Driver 标注、自然语言总结） |
| C-6 | RCA 工具注册 | 注册 RCA 相关工具到 ToolRegistry（作为 Agent 可调用的工具） |
| C-7 | 单元测试 | `tests/unit/test_rca/` |

**RCA 分析流程**:
```
用户查询："为什么上月销售额下降了？"
    ↓
1. AnomalyDetector: 对比上月/上上月销售额，检测到 -15% 异常
    ↓
2. DimensionDrillDown: 按 城市/品类/渠道 逐层拆解
    ↓
3. AttributionAnalyzer: 计算各维度贡献度
    → 城市维度: 上海 -8%, 北京 -5%, 其他 -2%
    → 品类维度: 电子产品 -10%, 其他 -5%
    ↓
4. DataInterpreter: 生成自然语言总结
    → "上月销售额同比下降 15%，主要受上海地区电子产品品类影响（贡献 -8%）"
```

**接口定义**:
```python
@dataclass
class AnomalyResult:
    metric_name: str
    current_value: float
    baseline_value: float
    change_percent: float
    is_anomaly: bool
    anomaly_type: str  # "drop" / "spike" / "trend_change"
    confidence: float  # 0.0 ~ 1.0

@dataclass
class DrillDownResult:
    dimension_name: str
    values: list[dict[str, Any]]  # [{value: "上海", contribution: -8.5, percent: -56.7}]
    top_contributors: list[dict[str, Any]]

@dataclass
class AttributionResult:
    total_change: float
    dimensions: list[dict[str, Any]]  # [{dimension: "城市", contribution: -8.0, percent: 53.3}]
    key_drivers: list[str]

@dataclass
class RCAReport:
    anomaly: AnomalyResult
    drill_downs: list[DrillDownResult]
    attribution: AttributionResult
    summary: str  # 自然语言总结
    confidence: float = 0.0

class RCAOrchestrator:
    async def analyze(
        self,
        question: str,
        metric_name: str,
        data_source_id: str,
        time_range: tuple[str, str],
    ) -> RCAReport: ...
```

---

### Track D: RCA API + Agent 集成

**目录隔离**: `services/agent-service/src/datapilot_agent/api/routes/`
**依赖**: Track C（RCA 引擎）

| # | 任务 | 产出文件 |
|---|------|----------|
| D-1 | RCA API 路由 | `api/routes/rca.py` — POST /rca/analyze, GET /rca/{analysis_id}/result |
| D-2 | Agent Chat 增强 | 修改 `api/routes/chat.py` — 意图识别支持 RCA 意图，路由到 RCA 引擎 |
| D-3 | RCA 持久化 | `rca/store.py` — RCA 分析记录存储（内存） |
| D-4 | Tool Registry API | `api/routes/tools.py` — GET /tools（发现）、GET /tools/{name}（详情）、POST /tools/execute |
| D-5 | 集成测试 | `tests/unit/test_rca_api/` |

**RCA API 接口**:
```python
# POST /api/v1/rca/analyze
class RCAAnalyzeRequest(BaseModel):
    question: str               # "为什么上月销售额下降了？"
    metric_name: str            # "销售额"
    data_source_id: str         # 数据源 ID
    time_range: tuple[str, str] # ("2025-04-01", "2025-04-30")
    compare_range: tuple[str, str] | None = None  # 对比时间段

class RCAAnalyzeResponse(BaseModel):
    analysis_id: str
    report: RCAReport
    execution_time_ms: float
```

---

### Track E: 前端 RCA 可视化 + 工具面板

**目录隔离**: `web/packages/chat-ui/src/`
**依赖**: Track D（RCA API）

| # | 任务 | 产出文件 |
|---|------|----------|
| E-1 | RCA 结果组件 | `components/RCAReport.tsx` — 异常概览 + 维度下钻 + 归因展示 |
| E-2 | 维度下钻图表 | `components/DrillDownChart.tsx` — 水平柱状图展示各维度贡献度 |
| E-3 | API 层 | `api/rca.ts` — RCA 分析 API |
| E-4 | 类型定义 | `types/rca.ts` — RCA 相关类型 |
| E-5 | MSW Mock | 扩展 `mocks/handlers.ts` — RCA API Mock |
| E-6 | MessageBubble 集成 | 扩展 `MessageBubble.tsx` — RCA 结果展示 |
| E-7 | Store 扩展 | 扩展 `dagStore.ts` — RCA 分析状态 |

**RCA 结果可视化设计**:
- 顶部：异常概览卡片（指标名、当前值、基线值、变化百分比、趋势箭头）
- 中部：维度贡献度水平柱状图（正/负值双方向，颜色区分）
- 底部：Key Drivers 列表（自然语言描述 + 贡献度百分比）
- 展开/收起维度下钻详情

---

## Track 间文件隔离矩阵

| 目录 | Track A | Track B | Track C | Track D | Track E |
|------|---------|---------|---------|---------|---------|
| `libs/datapilot-tools/` | **写** | 读 | 读 | 读 | - |
| `libs/datapilot-llm/` | - | **写** | - | - | - |
| `agent-service/rca/` | - | - | **写** | 读 | - |
| `agent-service/api/routes/rca.py` | - | - | - | **写** | - |
| `agent-service/api/routes/tools.py` | - | - | - | **写** | - |
| `agent-service/api/routes/chat.py` | - | - | - | 改(仅追加) | - |
| `chat-ui/src/components/` | - | - | - | - | **写** |
| `chat-ui/src/api/` | - | - | - | - | **写** |
| `chat-ui/src/types/` | - | - | - | - | **写** |
| `tests/unit/test_tools/` | **写** | - | - | - | - |
| `tests/unit/test_function_calling/` | - | **写** | - | - | - |
| `tests/unit/test_rca/` | - | - | **写** | - | - |
| `tests/unit/test_rca_api/` | - | - | - | **写** | - |

**冲突风险点**:
- `chat.py`：仅 Track D 修改，在末尾追加新端点。
- `router.py`：仅 Track B 修改。
- `dagStore.ts`：仅 Track E 修改。
- `handlers.ts`：仅 Track E 在末尾追加。

## 验证方式

- Track A: `uv run pytest tests/unit/test_tools/ -v`
- Track B: `uv run pytest tests/unit/test_function_calling/ -v`
- Track C: `uv run pytest tests/unit/test_rca/ -v`
- Track D: `uv run pytest tests/unit/test_rca_api/ -v`
- Track E: TypeScript 编译通过
