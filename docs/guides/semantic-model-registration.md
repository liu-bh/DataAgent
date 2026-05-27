# 语义模型注册指南

> 本文档说明如何创建和管理语义模型（Semantic Model），包括注册数据源、定义指标/维度、建立表关系。
> 语义模型是 NL2SQL 的核心知识库，直接决定了 SQL 生成质量。

## 1. 概念关系

```
语义模型 (Semantic Model)
├── 数据源 (Data Source) ─── 物理数据库连接
│   └── 表 (Source Table) ─── 同步的物理表/视图
│       └── 列 (Column) ─── 物理列定义
├── 指标 (Metric) ─── 可量化的业务度量
│   ├── 计算表达式 (Calculation) ─── 如 SUM(amount)
│   └── 关联维度 (MetricDimensions) ─── 可按哪些维度分析
├── 维度 (Dimension) ─── 分析角度
│   ├── 物理维度 (is_virtual=false) ─── 直接映射到物理列
│   └── 虚拟维度 (is_virtual=true) ─── CASE WHEN 表达式
└── 表关系 (Table Relationship) ─── JOIN 规则
```

## 2. 注册流程总览

```
注册数据源 → 同步元数据 → 创建语义模型 → 定义指标 → 定义维度 → 建立表关系 → 验证 → 激活
```

### 2.1 通过 API 注册

#### 步骤 1: 注册数据源

```bash
POST /api/v1/data-sources
{
  "name": "电商业务库",
  "type": "mysql",
  "host": "10.0.1.100",
  "port": 3306,
  "database": "ecommerce",
  "username": "readonly_user",
  "password": "******",
  "freshness_level": "daily",
  "freshness_cron": "0 6 * * *"
}
```

#### 步骤 2: 触发元数据同步

```bash
POST /api/v1/data-sources/{datasource_id}/sync
```

同步后查看已注册的表：

```bash
GET /api/v1/data-sources/{datasource_id}/tables
```

#### 步骤 3: 创建语义模型

```bash
POST /api/v1/semantic-models
{
  "name": "电商分析视图",
  "description": "电商核心业务数据，覆盖订单、商品、用户三大域",
  "domain": "电商",
  "data_source_ids": ["datasource-uuid-1"]
}
```

#### 步骤 4: 定义指标

```bash
POST /api/v1/metrics
{
  "semantic_model_id": "model-uuid",
  "name": "GMV",
  "description": "商品交易总额，包含已支付和已发货订单",
  "calculation": "SUM(order_items.payment_amount)",
  "unit": "元",
  "tags": ["核心", "财务"]
}
```

**嵌套指标示例**（指标引用指标）：

```bash
POST /api/v1/metrics
{
  "name": "客单价",
  "description": "平均每笔订单金额",
  "calculation": "GMV / COUNT(DISTINCT orders.id)",
  "parent_metric_id": "gmv-metric-uuid",
  "unit": "元"
}
```

#### 步骤 5: 定义维度

**物理维度**（直接映射列）：

```bash
POST /api/v1/dimensions
{
  "semantic_model_id": "model-uuid",
  "name": "商品类目",
  "column_name": "category_name",
  "table_id": "products-table-uuid",
  "synonyms": ["品类", "分类", "商品类型"],
  "is_virtual": false
}
```

**虚拟维度**（计算列）：

```bash
POST /api/v1/dimensions
{
  "name": "价格区间",
  "is_virtual": true,
  "virtual_expression": "CASE WHEN price < 100 THEN '低价' WHEN price < 1000 THEN '中价' ELSE '高价' END",
  "semantic_model_id": "model-uuid",
  "synonyms": ["价位", "价格段", "消费档次"]
}
```

**层级维度**（带层级关系）：

```bash
POST /api/v1/dimensions
{
  "name": "地区",
  "column_name": "region_name",
  "table_id": "orders-table-uuid",
  "synonyms": ["区域", "大区", "省份"],
  "hierarchy": {
    "level": "province",
    "children": ["city", "district"]
  },
  "semantic_model_id": "model-uuid"
}
```

#### 步骤 6: 关联指标与维度

```bash
# 批量关联 GMV 的分析维度
# 通过 PATCH /api/v1/metrics/{metric_id} 更新
PATCH /api/v1/metrics/{metric_id}
{
  "dimension_ids": ["dim-category-uuid", "dim-region-uuid", "dim-time-uuid"]
}
```

#### 步骤 7: 建立表关系

```bash
# 在语义模型中定义表 JOIN 规则
# 通过 PUT /api/v1/semantic-models/{id} 更新关系
PUT /api/v1/semantic-models/{model_id}
{
  "relationships": [
    {
      "left_table_id": "orders-table-uuid",
      "right_table_id": "users-table-uuid",
      "join_type": "left",
      "join_condition": "orders.user_id = users.id"
    },
    {
      "left_table_id": "orders-table-uuid",
      "right_table_id": "order_items-table-uuid",
      "join_type": "inner",
      "join_condition": "orders.id = order_items.order_id"
    }
  ]
}
```

### 2.2 通过管理界面注册

管理界面（Admin Dashboard）提供可视化操作：

1. 进入 **数据管理 → 语义模型**
2. 点击 **新建语义模型**，填写名称、描述、业务域
3. 关联数据源 → 触发元数据同步
4. 在表列表中勾选需要的表
5. 进入 **指标管理** → 定义指标和维度
6. 在 **关系图** 中拖拽建立表关系
7. 点击 **验证** → 检查配置完整性
8. 点击 **激活** → 语义模型生效

## 3. 指标定义最佳实践

### 3.1 命名规范

| 规则 | 示例 |
|------|------|
| 使用业务术语 | `GMV` > `sum_amount` |
| 包含单位说明 | `客单价（元）` |
| 嵌套指标用"率/比/均"结尾 | `转化率`、`同比增长率`、`客单价` |

### 3.2 计算表达式规则

```sql
-- 正确：明确聚合函数 + 字段
SUM(payment_amount)

-- 正确：嵌套引用
GMV / COUNT(DISTINCT orders.id)

-- 错误：裸列名（缺少聚合）
payment_amount

-- 错误：子查询（复杂计算应拆为多个指标）
SUM(amount) / (SELECT COUNT(*) FROM users)
```

### 3.3 版本管理

指标支持版本控制，修改后自动递增版本号：

```bash
PUT /api/v1/metrics/{metric_id}
{
  "calculation": "SUM(COALESCE(payment_amount, 0))",  # 修复 NULL 问题
  "description": "GMV，已修复空值处理"
}
# 自动 version += 1
```

历史查询仍使用旧版本的计算逻辑（通过 `effective_time` 判断）。

## 4. 维度定义最佳实践

### 4.1 同义词配置

同义词直接影响 Schema Linking 的匹配准确率，务必完整填写：

| 维度名称 | 必须配置的同义词 |
|----------|-----------------|
| 时间 | 日期、月份、年份、季度、周 |
| 地区 | 区域、大区、省份、城市 |
| 商品类目 | 品类、分类、商品类型、类目 |
| 渠道 | 来源、渠道、入口、平台 |

### 4.2 层级维度

地区等有层级的维度必须配置 hierarchy，影响查询时的自动钻取：

```json
{
  "name": "地区",
  "hierarchy": {
    "level": "province",
    "children": ["city", "district"]
  }
}
```

用户问"按地区统计"时，默认返回省级数据，可下钻到市级。

### 4.3 虚拟维度

适合以下场景：

- 数据分桶（价格区间、年龄区间）
- 标志转换（0/1 → 是/否）
- 时间提取（日期 → 星期几/月份）

```sql
-- 虚拟维度示例
CASE
  WHEN DATEDIFF(order_date, NOW()) <= 7 THEN '最近7天'
  WHEN DATEDIFF(order_date, NOW()) <= 30 THEN '最近30天'
  ELSE '30天前'
END
```

## 5. 向量化与语义搜索

### 5.1 自动向量化

以下字段在创建/更新时自动生成 Embedding 向量：

- `source_tables.description` + 列信息
- `metrics.description` + 计算表达式
- `dimensions.description` + 同义词

### 5.2 向量配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `EMBEDDING_PROVIDER` | Embedding 提供商 | `qwen` |
| `EMBEDDING_MODEL` | 模型名称 | `text-embedding-v3` |
| `EMBEDDING_DIMENSIONS` | 向量维度 | `1536` |
| `PGVECTOR_INDEX_TYPE` | 索引类型 | `ivfflat` |
| `PGVECTOR_INDEX_LISTS` | IVFFlat lists 参数 | `100` |

### 5.3 搜索工作原理

当用户提问时，系统将问题向量化，与语义库中的向量做相似度匹配：

```
用户问题 → Embedding → 与 metrics/dimensions/tables 向量做 Cosine Similarity
         → Top-K 匹配 → 组装为 SemanticContext → 传递给 SQL Generator
```

## 6. 验证检查清单

创建/修改语义模型后，执行以下验证：

| 检查项 | 说明 |
|--------|------|
| 表完整性 | 所有需要的表已同步且列信息完整 |
| 关系完整性 | 需要关联的表之间有 JOIN 条件 |
| 指标有效性 | 计算表达式语法正确，嵌套引用的目标存在 |
| 维度覆盖率 | 核心分析维度均已定义且同义词完整 |
| 向量化状态 | 新增的指标/维度已生成 Embedding |
| NL2SQL 测试 | 用 5-10 个典型问题测试 SQL 生成质量 |

```bash
# 验证语义模型完整性
GET /api/v1/semantic-models/{id}?include_validation=true

# 测试 NL2SQL 效果
POST /api/v1/chat/message
{
  "session_id": "test-session",
  "content": "按商品类目统计上个月 GMV TOP 10"
}
```

## 7. 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| SQL 生成的表名不对 | 语义匹配相似度不够 | 补充表描述和列描述 |
| SQL 缺少 JOIN | 未配置表关系 | 添加 `table_relationships` |
| 维度名被错误识别 | 同义词冲突 | 精简同义词，避免歧义 |
| 嵌套指标生成失败 | 依赖的指标 ID 不存在 | 先创建基础指标 |
| 旧查询结果不对 | 指标版本变更 | 检查 `effective_time` |
