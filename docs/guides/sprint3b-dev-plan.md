# Sprint 3b: 验证与集成 — 并行开发计划

> 目标：验证体系完善，端到端链路可用
> 依赖：Sprint 1 (auth/session/agent) + Sprint 2 (semantic/prompt/retrieval) + Sprint 3a (LLM/SQL-AST/intent/pipeline)

## 并行 Track 划分

### Track A: SQL 验证 + Dry-run + 成本预估

**目录隔离**: `services/sql-generator-service/src/datapilot_sqlgen/validation/`
**依赖**: Sprint 3a 的 `datapilot-sql`（SQLValidator/transformer）

| # | 任务 | 产出文件 |
|---|------|----------|
| A-1 | SQL Dry-run 预执行 | `dryrun.py` — 只读连接验证表存在/列类型/权限，返回 DryRunResult |
| A-2 | SQL 成本预估 | `cost_estimator.py` — EXPLAIN ANALYZE 预计算扫描行数/预估执行时间/成本等级(low/medium/high) |
| A-3 | 验证编排器 | `validator.py` — 组合 AST 验证 + Dry-run + 成本预估，输出 ValidationResult |
| A-4 | Pydantic 模型 | `models.py` — DryRunResult, CostEstimate, ValidationResult 数据模型 |
| A-5 | 单元测试 | `tests/unit/test_validation/` |

**接口定义**:
```python
@dataclass
class DryRunResult:
    success: bool
    error: str = ""
    checked_tables: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

@dataclass
class CostEstimate:
    estimated_rows: int
    estimated_time_ms: float
    cost_level: Literal["low", "medium", "high"]
    explain_output: str = ""

@dataclass
class ValidationResult:
    is_valid: bool
    ast_valid: bool
    dryrun_passed: bool
    cost_estimate: CostEstimate | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
```

---

### Track B: Self-Correction（自纠错机制）

**目录隔离**: `services/sql-generator-service/src/datapilot_sqlgen/correction/`
**依赖**: Sprint 3a 的 Pipeline 和 LLM Router

| # | 任务 | 产出文件 |
|---|------|----------|
| B-1 | 错误分类器 | `error_classifier.py` — 将执行错误分为 syntax_error/table_not_found/column_not_found/empty_result/timeout/other |
| B-2 | 场景化纠错 Prompt | `prompts.py` — 6 种错误场景的纠错 Prompt 模板 |
| B-3 | Self-Correction 引擎 | `engine.py` — 最多 3 轮纠错循环，每轮包含错误分析→Prompt 组装→LLM 修复→验证 |
| B-4 | 融入 Pipeline | 修改 `generator/pipeline.py` — 在步骤 7（后处理）之后增加 Self-Correction 步骤 |
| B-5 | 单元测试 | `tests/unit/test_correction/` |

**接口定义**:
```python
class ErrorCategory(StrEnum):
    SYNTAX_ERROR = "syntax_error"
    TABLE_NOT_FOUND = "table_not_found"
    COLUMN_NOT_FOUND = "column_not_found"
    EMPTY_RESULT = "empty_result"
    TIMEOUT = "timeout"
    OTHER = "other"

@dataclass
class CorrectionResult:
    success: bool
    corrected_sql: str
    attempts: int
    error_category: str
    original_error: str = ""
    corrections_history: list[str] = field(default_factory=list)
```

**注意**: 修改 `generator/pipeline.py` 时仅新增可选参数和方法，不改动现有流程逻辑。在 `__init__` 中增加 `max_correction_rounds: int = 3` 参数，在 `generate()` 末尾新增 `_step_self_correction()` 调用（仅在 `self._llm_router` 存在时才触发）。

---

### Track C: Guardrail Service 基础

**目录隔离**: `services/guardrail-service/src/datapilot_guardrail/`
**依赖**: `datapilot-common`、`datapilot-sql`

| # | 任务 | 产出文件 |
|---|------|----------|
| C-1 | SQL 风险检测 | `sql_risk.py` — 检测 DDL/DML/DROP/TRUNCATE 等危险操作，AST 级别检查 |
| C-2 | 行数限制 | `row_limit.py` — 根据租户配置限制最大返回行数，默认 10000 |
| C-3 | 查询配额 | `quota.py` — Redis 计数器实现日/小时级查询次数配额，滑动窗口 |
| C-4 | Guardrail 检查器 | `checker.py` — 组合风险检测+行数限制+配额检查，返回 GuardrailResult |
| C-5 | Pydantic 模型 | `models.py` — RiskLevel, GuardrailResult, QuotaConfig |
| C-6 | API 路由 | `api/routes/guardrail.py` — POST /check-sql（SQL 预检）, GET /quota/{tenant_id}（配额查询） |
| C-7 | FastAPI 入口 | `main.py` — 挂载路由、健康检查 |
| C-8 | pyproject.toml 补充 | 添加 structlog, redis 依赖 |
| C-9 | 单元测试 | `tests/unit/test_guardrail/` |

**接口定义**:
```python
class RiskLevel(StrEnum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"

@dataclass
class GuardrailResult:
    passed: bool
    risk_level: str
    blocked_reason: str = ""
    max_rows: int = 10000
    quota_remaining: int = -1
    warnings: list[str] = field(default_factory=list)
```

---

### Track D: 端到端集成 + SQL 解释 + Token 预算增强

**目录隔离**:
- `services/sql-generator-service/src/datapilot_sqlgen/explanation/`
- `services/sql-generator-service/src/datapilot_sqlgen/generator/pipeline.py`（仅新增方法）
- `services/sql-generator-service/src/datapilot_sqlgen/api/routes/sqlgen.py`（扩展）
- `services/agent-service/src/datapilot_agent/api/routes/chat.py`（扩展）

**依赖**: Sprint 3a 全部 Track + Sprint 3b Track A/B/C

| # | 任务 | 产出文件 |
|---|------|----------|
| D-1 | SQL 自然语言解释 | `explanation/interpreter.py` — LLM 生成 SQL 的自然语言描述（"这个查询统计了..."） |
| D-2 | 解释 Prompt 模板 | `explanation/prompts.py` — 解释场景专用 Prompt |
| D-3 | 端到端集成编排 | 扩展 `api/routes/sqlgen.py` — 添加 POST /chat/execute（端到端：NL→SQL→Validate→Guardrail→执行） |
| D-4 | 用户编辑 SQL 重执行 | 扩展 `api/routes/sqlgen.py` — POST /chat/re-execute（接受用户编辑后的 SQL） |
| D-5 | 用户反馈闭环 | 扩展 `api/routes/sqlgen.py` — POST /chat/feedback（👍/👎 + 编辑SQL自动收录Few-shot） |
| D-6 | Agent Service Chat 路由增强 | 扩展 `agent-service/api/routes/chat.py` — 对接 sqlgen-service 的端到端 API |
| D-7 | 单元测试 | `tests/unit/test_explanation/` |

**接口定义**:
```python
@dataclass
class SQLExplanation:
    summary: str  # "这个查询统计了上个月各城市的销售额合计..."
    key_points: list[str]  # ["筛选条件: 上月", "聚合方式: SUM", "分组维度: 城市"]
    potential_issues: list[str]  # ["未限制数据范围，可能返回大量数据"]
```

**注意**:
- 扩展 `sqlgen.py` 时在现有路由之后追加新路由，不修改已有路由
- 扩展 `chat.py` 时在现有 SSE stub 之后追加新端点
- 端到端 API 内部调用 Pipeline → Validation → Guardrail（均为可选，缺失时跳过）

---

### Track E: 前端 SQL 编辑执行 + 反馈闭环

**目录隔离**: `web/packages/chat-ui/src/`
**依赖**: Sprint 3a 前端 Track E 的组件

| # | 任务 | 产出文件 |
|---|------|----------|
| E-1 | SQL 编辑器组件 | `components/SqlEditor.tsx` — 可编辑 textarea + 语法高亮 + 执行按钮 |
| E-2 | 反馈组件 | `components/FeedbackButtons.tsx` — 👍/👎 按钮组 + 评论输入框 |
| E-3 | 结果表格增强 | `components/ResultTable.tsx` — 排序/筛选/分页 + 导出 CSV |
| E-4 | 聊天 Store 增强 | `stores/chatStore.ts` — 添加 editSql/reExecute/submitFeedback actions |
| E-5 | API 层扩展 | `api/sqlgen.ts` — execute/reExecute/feedback API 调用 |
| E-6 | MSW Mock 更新 | `mocks/handlers.ts` — 添加 execute/reExecute/feedback 的 Mock |
| E-7 | MessageBubble 集成 | `components/MessageBubble.tsx` — 集成 SqlEditor + FeedbackButtons + ResultTable |
| E-8 | 类型定义扩展 | `types/api.ts` — 新增 execute/reExecute/feedback 相关类型 |

**注意**:
- 新增组件，不修改已有组件的 props 接口（通过 composition 扩展）
- Store 中仅新增 action，不修改已有 state 结构
- MSW handlers 在现有 handlers.ts 末尾追加

---

## Track 间文件隔离矩阵

| 目录 | Track A | Track B | Track C | Track D | Track E |
|------|---------|---------|---------|---------|---------|
| `sqlgen/validation/` | **写** | - | - | 读 | - |
| `sqlgen/correction/` | - | **写** | - | 读 | - |
| `sqlgen/explanation/` | - | - | - | **写** | - |
| `sqlgen/generator/pipeline.py` | - | 改（仅追加） | - | 改（仅追加） | - |
| `sqlgen/api/routes/sqlgen.py` | - | - | - | 改（仅追加） | - |
| `agent-service/api/routes/chat.py` | - | - | - | 改（仅追加） | - |
| `guardrail-service/src/` | - | - | **写** | 读 | - |
| `web/packages/chat-ui/src/` | - | - | - | - | **写** |
| `tests/unit/test_validation/` | **写** | - | - | - | - |
| `tests/unit/test_correction/` | - | **写** | - | - | - |
| `tests/unit/test_guardrail/` | - | - | **写** | - | - |
| `tests/unit/test_explanation/` | - | - | - | **写** | - |

**冲突风险点**:
- `pipeline.py`：Track B 和 Track D 都需要修改。**约定：Track B 在 `generate()` 末尾新增 `_step_self_correction()` 调用点，Track D 不再改动 `generate()` 流程，而是通过扩展 API 层调用。**
- `sqlgen.py` 路由：仅 Track D 修改。
- `chat.py`：仅 Track D 修改。

## 跨 Track 接口约定

### Track D → Track A（validation）
```python
from datapilot_sqlgen.validation.validator import SQLValidationOrchestrator
result = await validator.validate(sql, dialect, db_url_optional)
```

### Track D → Track B（correction）
```python
from datapilot_sqlgen.correction.engine import SelfCorrectionEngine
result = await corrector.correct(sql, error_msg, context)
```

### Track D → Track C（guardrail）
```python
from datapilot_guardrail.checker import GuardrailChecker
result = await checker.check(sql, tenant_id, dialect)
```

## 验证方式

- Track A: `uv run pytest tests/unit/test_validation/ -v`
- Track B: `uv run pytest tests/unit/test_correction/ -v`
- Track C: `uv run pytest tests/unit/test_guardrail/ -v`
- Track D: `uv run pytest tests/unit/test_explanation/ -v`
- Track E: `cd web && pnpm --filter chat-ui build`（TypeScript 编译通过）

集成验证:
- [ ] SQL 验证链路：AST → Dry-run → 成本预估 → ValidationResult
- [ ] Self-Correction：语法错误 SQL → 3 轮纠错 → 修正 SQL
- [ ] Guardrail：危险 SQL → BLOCKED / 正常 SQL → SAFE
- [ ] 端到端：自然语言 → SQL → 验证 → 执行 → 解释 → 展示
- [ ] 前端：编辑 SQL → 重执行 → 反馈
