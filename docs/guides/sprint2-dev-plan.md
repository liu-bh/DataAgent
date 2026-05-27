# Sprint 2 并行开发计划：Semantic Layer

> Sprint 1 已完成（骨架+授权+Auth+Session+前端+基础设施），本文档为 Sprint 2 并行开发执行计划。

## 1. Sprint 2 目标

语义层核心，元数据管理和语义检索可用：
- 数据源注册与元数据自动同步
- 指标/维度/语义模型完整 CRUD
- 向量检索 + 混合搜索 + RRF 重排
- Prompt 模板版本管理 + A/B 测试框架
- Admin Dashboard 语义模型管理页

## 2. 并行 Track 设计

### Track A：数据源注册与元数据同步
**负责目录**: `services/semantic-service/src/datapilot_semantic/metadata/`
**无外部依赖**（直接连 PostgreSQL + 目标数据库）

| # | 任务 | 产出 |
|---|------|------|
| A-1 | 数据源连接池管理 | `datasource_pool.py`（MySQL/PG/Doris/ClickHouse 连接工厂） |
| A-2 | Schema Extractor | `schema_extractor.py`（读取 information_schema，提取表/列/类型/主键） |
| A-3 | 数据源 CRUD API | `api/routes/data_sources.py`（注册/列表/详情/更新/删除/健康检查） |
| A-4 | 元数据同步 API | `api/routes/data_sources.py`（触发同步、查看已同步表） |
| A-5 | 同步后台任务 | `sync_worker.py`（增量同步变更表、更新向量） |
| A-6 | 单元测试 | `tests/unit/test_metadata/` |

### Track B：语义模型与指标维度
**负责目录**: `services/semantic-service/src/datapilot_semantic/models/`
**依赖**: Track A 的 source_tables 表

| # | 任务 | 产出 |
|---|------|------|
| B-1 | SemanticModel 模型 | `semantic_model.py`（SQLAlchemy） |
| B-2 | Metric 模型 | `metric.py`（含 version、parent_metric_id、嵌套引用） |
| B-3 | Dimension 模型 | `dimension.py`（含 synonyms、hierarchy、is_virtual） |
| B-4 | TableRelationship 模型 | `table_relationship.py`（JOIN 路径定义） |
| B-5 | MetricDimension 关联模型 | `metric_dimension.py`（多对多） |
| B-6 | 语义模型 CRUD API | `api/routes/semantic_models.py` |
| B-7 | 指标 CRUD API | `api/routes/metrics.py`（列表/创建/更新/删除、版本管理） |
| B-8 | 维度 CRUD API | `api/routes/dimensions.py` |
| B-9 | Alembic 迁移 | 语义层全部表的迁移文件 |
| B-10 | 单元测试 | `tests/unit/test_semantic/` |

### Track C：向量检索与语义搜索
**负责目录**: `services/semantic-service/src/datapilot_semantic/retrieval/`
**依赖**: Track B 的 metrics/dimensions 数据（需要向量才能搜索）

| # | 任务 | 产出 |
|---|------|------|
| C-1 | Embedding 客户端 | `embedding.py`（text-embedding-v3 调用，批量向量化） |
| C-2 | 向量存储操作 | `vector_store.py`（pgvector CRUD，IVFFlat 索引创建） |
| C-3 | 语义搜索 API | `api/routes/search.py`（混合检索 + RRF 重排） |
| C-4 | 语义缓存 | `cache.py`（Metric/Dimension 元数据→Redis，TTL 配置） |
| C-5 | 单元测试 | `tests/unit/test_retrieval/` |

### Track D：Prompt 模板管理
**负责目录**: `libs/datapilot-prompt/src/datapilot_prompt/`
**完全独立**

| # | 任务 | 产出 |
|---|------|------|
| D-1 | PromptVersion 模型 | `models.py`（SQLAlchemy：scene, version, content, is_active, ab_test_traffic） |
| D-2 | Prompt CRUD API | `api/routes/prompts.py`（列表/创建、按 scene 查询、激活指定版本） |
| D-3 | A/B 测试分流 | `ab_testing.py`（流量分配、效果评分收集） |
| D-4 | Token 预算管理 | `budget.py`（Few-shot + 表结构 + 历史对话超窗口裁剪） |
| D-5 | Alembic 迁移 | prompt_versions 表 |
| D-6 | CLI + 单元测试 | |

### Track E：前端语义管理
**负责目录**: `web/packages/chat-ui/src/pages/` + `web/packages/admin-dashboard/`
**依赖**: Track B 的 API（使用 MSW Mock 独立开发）

| # | 任务 | 产出 |
|---|------|------|
| E-1 | Admin Dashboard 骨架 | `web/packages/admin-dashboard/`（Vite + React + Tailwind） |
| E-2 | 数据源管理页 | 列表、注册弹窗、健康状态展示 |
| E-3 | 语义模型管理页 | 列表、详情、指标/维度管理 |
| E-4 | 指标管理页 | 列表、创建/编辑、版本历史 |
| E-5 | 维度管理页 | 列表、创建/编辑、同义词管理 |
| E-6 | MSW Mock 更新 | 新增语义层全部 API Mock |

## 3. 文件隔离矩阵

| 目录 | Track A | Track B | Track C | Track D | Track E |
|------|---------|---------|---------|---------|---------|
| `libs/datapilot-prompt/` | - | - | - | **写** | - |
| `libs/datapilot-llm/` | - | - | - | 读 | - |
| `services/semantic-service/` | **写** | **写** | **写** | - | 读 |
| `web/packages/chat-ui/` | - | - | - | - | **写** |
| `web/packages/admin-dashboard/` | - | - | - | - | **写** |
| `tests/unit/test_metadata/` | **写** | - | - | - | - |
| `tests/unit/test_semantic/` | - | **写** | - | - | - |
| `tests/unit/test_retrieval/` | - | - | **写** | - | - |

**无冲突**。

## 4. 跨 Track 依赖

```
Track A (数据源) ──→ Track B (语义模型) ──→ Track C (向量检索)
Track D (Prompt) ── 独立
Track E (前端) ─── 通过 MSW Mock 独立
```

### 解耦策略
- Track C 依赖 Track B 的 Metric/Dimension 数据（需要向量才能搜索）
- Track B 可先定义模型和 API，Track C 后续接入
- 如果 Track B 未完成，Track C 可先用硬编码测试数据

## 5. 验证清单

- [ ] 注册 MySQL 数据源 → `POST /api/v1/data-sources` 成功
- [ ] 触发元数据同步 → `POST /api/v1/data-sources/{id}/sync` 提取表结构
- [ ] 创建语义模型 + 指标 + 维度 → CRUD API 正常
- [ ] 向量搜索 → `GET /api/v1/search?q=xxx` 返回匹配的指标/维度
- [ ] Prompt 版本管理 → CRUD + 激活/回滚
- [ ] Admin Dashboard 可管理语义模型
- [ ] 3 个业务域样例数据注册完成
