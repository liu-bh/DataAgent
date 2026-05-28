# Sprint 9: Chart Engine + Dashboard — 并行开发计划

> 目标：统一图表引擎 + LLM 智能推荐 + Dashboard 自动生成
> 依赖：Sprint 8（Tool Registry + RCA）、Sprint 4（查询执行器）

## 并行 Track 划分

### Track A: Chart Spec 统一规范

**目录隔离**: `libs/datapilot-chart/src/datapilot_chart/`
**无外部依赖**，纯数据结构和规范定义。

| # | 任务 | 产出文件 |
|---|------|----------|
| A-1 | 图表类型枚举 | `models.py` — ChartType（line/bar/pie/scatter/heatmap/table/radar/funnel/treemap/boxplot/gauge）, ChartSpec, ChartAxis, ChartSeries, ChartTheme |
| A-2 | 图表配置工厂 | `config_factory.py` — ChartConfigFactory（根据 ChartType + 数据生成 ECharts option） |
| A-3 | 图表类型推断 | `type_infer.py` — ChartTypeInferrer（根据数据列类型自动推荐图表类型） |
| A-4 | 主题定义 | `themes.py` — 内置主题（light/dark/contrast）, 色板, 全局样式 |
| A-5 | 数据适配器 | `adapter.py` — DataAdapter（将 SQL 查询结果转换为图表数据格式） |
| A-6 | 单元测试 | `tests/unit/test_chart/` |

**接口定义**:
```python
class ChartType(StrEnum):
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    TABLE = "table"
    RADAR = "radar"
    FUNNEL = "funnel"
    TREEMAP = "treemap"
    BOXPLOT = "boxplot"
    GAUGE = "gauge"

@dataclass
class ChartAxis:
    field: str
    name: str = ""
    type: str = "category"  # category / value / time

@dataclass
class ChartSeries:
    name: str
    data: list[Any]
    type: str = "bar"  # ECharts series type
    item_style: dict | None = None
    encode: dict | None = None

@dataclass
class ChartSpec:
    chart_type: ChartType
    title: str = ""
    x_axis: ChartAxis | None = None
    y_axis: ChartAxis | None = None
    series: list[ChartSeries] = field(default_factory=list)
    tooltip: dict = field(default_factory=dict)
    legend: dict = field(default_factory=dict)
    grid: dict = field(default_factory=dict)
    theme: str = "dark"
    width: int = 600
    height: int = 400

class ChartTypeInferrer:
    def infer(self, columns: list[dict], rows: list[dict]) -> list[ChartType]:
        """根据数据列类型自动推荐图表类型，返回按匹配度排序的列表。

        推理规则：
        - 1 个时间列 + 1 个数值列 → line（趋势）
        - 1 个维度列 + 1 个数值列 → bar（对比）
        - 1 个维度列 + 2 个数值列 → grouped bar
        - 1 个维度列 + 1 个数值列，维度数 ≤ 5 → pie（占比）
        - 2 个数值列 → scatter（相关性）
        - 多维度 + 多指标 → radar
        """

class DataAdapter:
    def adapt(self, result: QueryResult, x_field: str = "", y_fields: list[str] | None = None) -> list[ChartSeries]:
        """将查询执行结果适配为图表数据格式。"""

class ChartConfigFactory:
    def build_option(self, spec: ChartSpec) -> dict:
        """根据 ChartSpec 生成 ECharts option 配置。"""
```

---

### Track B: LLM 智能图表推荐

**目录隔离**: `services/agent-service/src/datapilot_agent/chart/`
**依赖**: Track A（ChartSpec）、LLM Router

| # | 任务 | 产出文件 |
|---|------|----------|
| B-1 | 图表推荐器 | `recommender.py` — ChartRecommender（结合数据特征 + LLM 推荐） |
| B-2 | 推荐 Prompt | `prompts.py` — 图表推荐 Prompt 模板 |
| B-3 | 图表描述生成 | `description.py` — ChartDescriptionGenerator（LLM 生成图表标题和描述） |
| B-4 | 图表工具注册 | 注册 chart_recommend/chart_generate 工具到 ToolRegistry |
| B-5 | 单元测试 | `tests/unit/test_chart_recommender/` |

**接口定义**:
```python
@dataclass
class ChartRecommendation:
    chart_types: list[tuple[ChartType, float]]  # [(type, confidence)]
    title: str
    description: str
    x_field: str
    y_fields: list[str]

class ChartRecommender:
    def __init__(self, llm_router=None): ...

    async def recommend(
        self,
        columns: list[dict],
        rows: list[dict],
        user_question: str = "",
    ) -> ChartRecommendation:
        """推荐图表类型和配置。

        策略：
        1. 规则推断（ChartTypeInferrer）
        2. 如果有 LLM，结合用户意图进一步优化
        3. 返回 top-3 推荐 + 自动选择 x/y 轴字段
        """

    async def generate_description(self, spec: ChartSpec, data_summary: dict) -> str:
        """生成图表的自然语言描述。"""
```

---

### Track C: Dashboard 引擎

**目录隔离**: `libs/datapilot-chart/src/datapilot_chart/dashboard/`
**依赖**: Track A（ChartSpec）

| # | 任务 | 产出文件 |
|---|------|----------|
| C-1 | Dashboard 数据模型 | `models.py` — DashboardLayout, DashboardPanel, DashboardFilter, PanelType |
| C-2 | Dashboard 构建器 | `builder.py` — DashboardBuilder（自动布局、过滤器联动） |
| C-3 | 布局算法 | `layout.py` — LayoutEngine（网格布局，响应式列数计算） |
| C-4 | 过滤器 | `filter.py` — DashboardFilter（全局时间范围过滤器、维度过滤器、联动逻辑） |
| C-5 | 序列化 | `serialization.py` — Dashboard JSON 序列化/反序列化 |
| C-6 | 单元测试 | `tests/unit/test_dashboard/` |

**接口定义**:
```python
class PanelType(StrEnum):
    CHART = "chart"
    TABLE = "table"
    METRIC = "metric"
    TEXT = "text"

@dataclass
class DashboardPanel:
    panel_id: str
    title: str
    panel_type: PanelType
    width: int = 6  # 1-12 栅格列
    height: int = 400
    chart_spec: ChartSpec | None = None
    metric_config: dict | None = None
    position: dict = field(default_factory=dict)  # {row, col}

@dataclass
class DashboardFilter:
    filter_id: str
    field: str
    label: str
    type: str  # time_range / select / multi_select
    options: list[str] = field(default_factory=list)
    default_value: Any = None

@dataclass
class DashboardLayout:
    dashboard_id: str
    title: str
    description: str = ""
    panels: list[DashboardPanel] = field(default_factory=list)
    filters: list[DashboardFilter] = field(default_factory=list)
    columns: int = 12
    created_at: str = ""
    updated_at: str = ""

class DashboardBuilder:
    def build_from_charts(self, chart_specs: list[ChartSpec]) -> DashboardLayout: ...
    def add_panel(self, layout, panel) -> None: ...
    def add_filter(self, layout, filter_def) -> None: ...
    def auto_layout(self, layout) -> None: ...
```

---

### Track D: Dashboard API + Store

**目录隔离**: `services/agent-service/src/datapilot_agent/api/routes/`
**依赖**: Track C（Dashboard 引擎）

| # | 任务 | 产出文件 |
|---|------|----------|
| D-1 | Dashboard API | `api/routes/dashboard.py` — POST /dashboard/generate, GET /dashboard/{id}, GET /dashboard/list |
| D-2 | Dashboard Store | `dashboard/store.py` — DashboardStore（内存存储） |
| D-3 | Chart API | `api/routes/chart.py` — POST /chart/recommend, POST /chart/render |
| D-4 | 单元测试 | `tests/unit/test_dashboard_api/` |

---

### Track E: 前端 Dashboard 页面

**目录隔离**: `web/packages/chat-ui/src/`
**依赖**: Track D（Dashboard API）

| # | 任务 | 产出文件 |
|---|------|----------|
| E-1 | Dashboard 页面 | `pages/Dashboard/index.tsx` — Dashboard 主页面 |
| E-2 | Dashboard 布局组件 | `components/DashboardLayout.tsx` — 网格布局 + 面板渲染 |
| E-3 | Dashboard 面板组件 | `components/DashboardPanel.tsx` — 图表/表格/指标卡片面板 |
| E-4 | Dashboard 过滤器 | `components/DashboardFilter.tsx` — 时间范围 + 维度选择器 |
| E-5 | API 层 | `api/dashboard.ts` — Dashboard API |
| E-6 | 类型定义 | `types/dashboard.ts` — Dashboard 相关类型 |
| E-7 | MSW Mock | 扩展 `mocks/handlers.ts` — Dashboard API Mock |
| E-8 | Store | `stores/dashboardStore.ts` — Dashboard 状态管理 |

---

## Track 间文件隔离矩阵

| 目录 | Track A | Track B | Track C | Track D | Track E |
|------|---------|---------|---------|---------|---------|
| `libs/datapilot-chart/` | **写**(core) | 读 | **写**(dashboard/) | 读 | - |
| `agent-service/chart/` | - | **写** | - | 读 | - |
| `agent-service/api/routes/` | - | - | - | **写** | - |
| `agent-service/dashboard/` | - | - | - | **写** | - |
| `chat-ui/src/` | - | - | - | - | **写** |
| `tests/unit/test_chart/` | **写** | - | - | - | - |
| `tests/unit/test_chart_recommender/` | - | **写** | - | - | - |
| `tests/unit/test_dashboard/` | - | - | **写** | - | - |
| `tests/unit/test_dashboard_api/` | - | - | - | **写** | - |

**冲突风险点**:
- `libs/datapilot-chart/`：Track A 写 core，Track C 写 dashboard/ 子包，无冲突。
- 无跨 Track 文件冲突。

## 验证方式

- Track A: `uv run pytest tests/unit/test_chart/ -v`
- Track B: `uv run pytest tests/unit/test_chart_recommender/ -v`
- Track C: `uv run pytest tests/unit/test_dashboard/ -v`
- Track D: `uv run pytest tests/unit/test_dashboard_api/ -v`
- Track E: TypeScript 编译通过
