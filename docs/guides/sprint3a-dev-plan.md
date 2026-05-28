# Sprint 3a: NL2SQL 核心 — 并行开发计划

> 目标：LLM 接入和 SQL 生成链路可用
> 依赖：Sprint 1 (auth/session/agent) + Sprint 2 (semantic/prompt/retrieval)

## 并行 Track 划分

### Track A: LLM 基础设施 (libs/datapilot-llm/)

**目录隔离**: `libs/datapilot-llm/src/datapilot_llm/`
**无外部依赖**，可立即开始。

| # | 任务 | 产出文件 |
|---|------|----------|
| A-1 | LLM Provider 协议接口 | `provider.py` — BaseProvider ABC (generate/generate_stream) |
| A-2 | OpenAI 兼容客户端 | `client.py` — httpx async client，统一 OpenAI 协议 |
| A-3 | Qwen Provider | `providers/qwen.py` — 通义千问 Turbo/Plus/Max |
| A-4 | DeepSeek Provider | `providers/deepseek.py` — DeepSeek-V3 |
| A-5 | Model Router + 熔断器 | `router.py` — 分级模型选择 + 降级 + 熔断 |
| A-6 | LLM 调用日志 | `logger.py` — token 追踪 + 成本计算 |
| A-7 | 单元测试 | `tests/unit/test_llm/` |

### Track B: SQL AST 封装 (libs/datapilot-sql/)

**目录隔离**: `libs/datapilot-sql/src/datapilot_sql/`
**无外部依赖**，可立即开始。

| # | 任务 | 产出文件 |
|---|------|----------|
| B-1 | sqlglot 方言工厂 | `dialect.py` — MySQL/PG/Doris/StarRocks/ClickHouse 方言 |
| B-2 | AST Builder | `builder.py` — SELECT/JOIN/WHERE/GROUP BY/ORDER BY/LIMIT 构建 |
| B-3 | AST 验证器 | `validator.py` — 表/列存在性、语法校验 |
| B-4 | AST 转换器 | `transformer.py` — 方言转换 + RBAC WHERE 注入 + 列级权限 |
| B-5 | SQL 渲染 | `renderer.py` — AST → SQL 字符串 |
| B-6 | 单元测试 | `tests/unit/test_sql/` |

### Track C: 意图识别 (sql-generator-service/intent/)

**目录隔离**: `services/sql-generator-service/src/datapilot_sqlgen/intent/`
**依赖**: Track A (LLM 调用)，通过 import 占位解决。

| # | 任务 | 产出文件 |
|---|------|----------|
| C-1 | 意图路由规则 | `router.py` — SQL/闲聊/超出范围分类 |
| C-2 | Intent Parser | `parser.py` — LLM 结构化输出 (JSON mode) |
| C-3 | Schema Linker | `schema_linker.py` — 意图→表/字段/指标/维度匹配 |
| C-4 | Semantic Resolver | `resolver.py` — 时间/过滤/聚合语义解析 |
| C-5 | 单元测试 | `tests/unit/test_intent/` |

### Track D: NL2SQL 主流程 (sql-generator-service/generator/)

**目录隔离**: `services/sql-generator-service/src/datapilot_sqlgen/generator/`
**依赖**: Track A (LLM) + Track B (AST) + Track C (Intent) + Sprint 2 (Prompt)。使用 import 占位。

| # | 任务 | 产出文件 |
|---|------|----------|
| D-1 | NL2SQL 编排器 | `pipeline.py` — Intent→Semantic→Schema→SQL 流程编排 |
| D-2 | Prompt 组装 | `prompt_builder.py` — 系统模板 + 语义上下文 + Few-shot + 用户问题 |
| D-3 | Few-shot 引擎 | `fewshot/matcher.py` — 向量相似度匹配 + 难度/领域筛选 |
| D-4 | NL2SQL API | `api/routes/sqlgen.py` — POST /api/v1/chat/message |
| D-5 | 单元测试 | `tests/unit/test_sqlgen/` |

### Track E: 前端 Chat UI 集成 (web/packages/chat-ui/)

**目录隔离**: `web/packages/chat-ui/src/`
**使用 MSW Mock**，完全独立开发。

| # | 任务 | 产出文件 |
|---|------|----------|
| E-1 | SQL 预览面板 | `src/components/SqlPanel.tsx` — SQL 展示 + 编辑 |
| E-2 | NL2SQL 状态指示 | `src/components/QueryStatus.tsx` — 意图分析→SQL 生成进度 |
| E-3 | 消息气泡增强 | 更新 `MessageBubble.tsx` — 支持 SQL/sqlExplanation/chartSpec |
| E-4 | MSW Mock 更新 | `src/mocks/handlers.ts` — NL2SQL API Mock |
| E-5 | 单元测试 | `tests/` |

## 文件隔离矩阵

| 目录 | Track A | Track B | Track C | Track D | Track E |
|------|---------|---------|---------|---------|---------|
| `libs/datapilot-llm/` | ✅ 写入 | — | — | — | — |
| `libs/datapilot-sql/` | — | ✅ 写入 | — | — | — |
| `sqlgen/intent/` | — | — | ✅ 写入 | — | — |
| `sqlgen/generator/` | — | — | — | ✅ 写入 | — |
| `sqlgen/fewshot/` | — | — | — | ✅ 写入 | — |
| `sqlgen/api/` | — | — | — | ✅ 写入 | — |
| `web/packages/chat-ui/src/` | — | — | — | — | ✅ 写入 |

## 跨 Track 接口契约

### Track D 依赖 Track A
```python
from datapilot_llm import LLMRouter, LLMResponse

llm = LLMRouter()
response: LLMResponse = await llm.generate(
    prompt="...",
    scene="nl2sql",
    temperature=0.1,
)
```

### Track D 依赖 Track B
```python
from datapilot_sql import ASTBuilder, SQLRenderer, Dialect

builder = ASTBuilder()
ast = builder.select(columns=["SUM(amount)"], from_table="orders").where(...)
sql = SQLRenderer.render(ast, dialect=Dialect.MYSQL)
```

### Track D 依赖 Track C
```python
from datapilot_sqlgen.intent import IntentParser, SchemaLinker

intent = await IntentParser.parse(question="上月 GMV")
schema = await SchemaLinker.link(intent, tenant_id=tenant_id)
```

## 关键设计约束

1. LLM 统一走 OpenAI 兼容协议 (Qwen/DeepSeek 都支持)
2. SQL 必须走 AST (sqlglot)，不拼接字符串
3. 意图识别使用 JSON mode 结构化输出
4. Few-shot 选择使用向量相似度 + token 预算控制
5. 分级模型：简单意图→Qwen-Turbo，复杂 NL2SQL→DeepSeek-V3
