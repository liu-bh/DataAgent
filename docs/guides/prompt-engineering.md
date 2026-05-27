# Prompt 工程指南

> 本文档说明 DataPilot 中 Prompt 的编写规范、版本管理、A/B 测试和 Token 预算控制。
> Prompt 是 NL2SQL 的核心，直接影响 SQL 生成质量。

## 1. Prompt 架构

```
PromptManager（libs/datapilot-prompt）
├── 场景注册（scene）：nl2sql / intent / explanation / correction
├── 版本管理：每个 Prompt 多版本，支持激活/回滚
├── Token 预算：自动计算 Prompt + Context Token 数
├── A/B 测试：流量分配 + 效果评分
└── Few-shot 管理：动态选择示例

Prompt 组装流程：
  System Prompt（固定）+ SemanticContext（动态）+ Few-shot Examples（动态）+ User Question
```

## 2. 场景定义

| 场景 | 场景标识 | 用途 | Token 预算 |
|------|---------|------|-----------|
| NL2SQL | `nl2sql` | 自然语言转 SQL | ≤ 8000 tokens |
| 意图识别 | `intent` | 识别用户查询类型 | ≤ 2000 tokens |
| SQL 解释 | `explanation` | SQL 自然语言解释 | ≤ 2000 tokens |
| 自校验 | `correction` | SQL 错误修复 | ≤ 4000 tokens |

## 3. NL2SQL Prompt 编写规范

### 3.1 System Prompt 结构

```markdown
你是一个专业的 SQL 生成助手。根据用户的自然语言问题和提供的数据库结构信息，生成准确的 SQL 查询。

## 规则
1. 只使用提供的表和列，不要编造不存在的表名或列名
2. 时间范围需要明确指定 WHERE 条件
3. 聚合查询必须包含 GROUP BY
4. TOP N 查询必须包含 ORDER BY 和 LIMIT
5. JOIN 时必须使用正确的关联条件
6. 不要使用 SELECT *，明确列出需要的列

## SQL 方言
{dialect}

## 数据库结构
{semantic_context}

## 参考 SQL 示例
{few_shot_examples}

## 用户问题
{question}
```

### 3.2 编写规则

| 规则 | 说明 | 示例 |
|------|------|------|
| 角色明确 | 第一句说明助手角色和能力边界 | "你是一个专业的 SQL 生成助手" |
| 规则量化 | 规则具体可执行，避免模糊 | "TOP N 必须带 ORDER BY" > "注意排序" |
| 结构化 | 使用 Markdown 分节 | ## 规则 / ## 数据库结构 / ## 示例 |
| 方言说明 | 明确目标 SQL 方言 | "使用 MySQL 语法" |
| 禁止事项 | 明确列出不允许的操作 | "不要编造表名" |

### 3.3 SemanticContext 注入

`{semantic_context}` 部分由系统动态生成：

```markdown
## 可用表

### orders（订单表）
| 列名 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 订单 ID |
| user_id | BIGINT | 用户 ID |
| amount | DECIMAL(12,2) | 订单金额（元） |
| status | VARCHAR(20) | 订单状态：pending/paid/shipped/delivered |
| created_at | DATETIME | 下单时间 |

### products（商品表）
| 列名 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 商品 ID |
| name | VARCHAR(200) | 商品名称 |
| category_id | INT | 类目 ID |
| price | DECIMAL(10,2) | 商品单价 |

## 表关联关系
- orders.user_id = users.id（LEFT JOIN）
- order_items.order_id = orders.id（INNER JOIN）
- order_items.product_id = products.id（INNER JOIN）

## 可用指标
- GMV = SUM(orders.amount)
- 订单量 = COUNT(DISTINCT orders.id)
- 客单价 = GMV / COUNT(DISTINCT orders.id)

## 可用维度
- 时间（orders.created_at）
- 地区（users.region）
- 商品类目（products.category_name）
```

### 3.4 Few-shot 示例选择

Few-shot 示例从 `nl2sql_examples` 表动态选择：

1. 将用户问题向量化
2. 与历史示例做相似度匹配
3. 选择 Top-3 最相似的示例
4. 控制示例总 Token ≤ 2000

示例格式：

```markdown
## 示例

### 示例 1
问题：上个月各地区的销售额是多少？
SQL：
SELECT u.region, SUM(o.amount) AS revenue
FROM orders o
LEFT JOIN users u ON o.user_id = u.id
WHERE o.created_at >= DATE_FORMAT(CURRENT_DATE - INTERVAL 1 MONTH, '%Y-%m-01')
  AND o.created_at < DATE_FORMAT(CURRENT_DATE, '%Y-%m-01')
GROUP BY u.region
ORDER BY revenue DESC

### 示例 2
问题：客单价最高的前5个商品
SQL：
SELECT p.name, SUM(oi.quantity * oi.price) / COUNT(DISTINCT o.id) AS avg_order_value
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
JOIN products p ON oi.product_id = p.id
GROUP BY p.id, p.name
ORDER BY avg_order_value DESC
LIMIT 5
```

## 4. 意图识别 Prompt

```markdown
你是一个意图识别助手。判断用户的查询意图，只返回 JSON。

## 意图类型
- sql_query: 用户要查询数据，可以转换为 SQL
- chitchat: 闲聊、打招呼
- out_of_scope: 超出系统范围的问题
- escalate_to_human: 无法处理，需要人工介入

## 判断规则
1. 包含数据查询关键词（"多少"、"统计"、"排名"、"趋势"）→ sql_query
2. 问候语、无关话题 → chitchat
3. 涉及系统外知识（如"天气怎样"）→ out_of_scope
4. 用户明确要求人工服务 → escalate_to_human

## 用户问题
{question}

请返回 JSON: {"intent": "sql_query", "confidence": 0.95, "reason": "包含数据查询关键词"}
```

## 5. 自校验 Prompt

```markdown
你是一个 SQL 校验专家。以下 SQL 执行出错，请修复。

## 原始问题
{question}

## 当前 SQL
{sql}

## 错误信息
{error_message}

## 数据库结构
{semantic_context}

## 修复要求
1. 只修复导致错误的部分，不要重写整个 SQL
2. 确保修复后的 SQL 语法正确
3. 保持原始查询逻辑不变

请返回 JSON: {"sql": "修复后的 SQL", "fix_explanation": "修复说明"}
```

## 6. 版本管理

### 6.1 创建新版本

```bash
POST /api/v1/prompts
{
  "scene": "nl2sql",
  "content": "# 更新后的 NL2SQL Prompt\n...",
  "version_description": "优化 JOIN 提示词，增加表关联关系说明"
}
```

系统自动递增版本号。

### 6.2 激活版本

```bash
PUT /api/v1/prompts/{prompt_id}/activate
```

激活后，新请求使用新版本，正在进行的请求不受影响。

### 6.3 版本回滚

```bash
# 查看历史版本
GET /api/v1/prompts?scene=nl2sql

# 激活旧版本
PUT /api/v1/prompts/{old_prompt_id}/activate
```

## 7. A/B 测试

### 7.1 配置流量分配

```bash
POST /api/v1/prompts
{
  "scene": "nl2sql",
  "content": "# 实验版本 Prompt\n...",
  "ab_test_traffic": 0.2,  # 20% 流量
  "version_description": "A/B 测试：增加 Few-shot 示例数量"
}
```

### 7.2 查看测试结果

```bash
GET /api/v1/prompts/{prompt_id}/ab-results
```

```json
{
  "version_a": {
    "prompt_id": "v1-uuid",
    "traffic": 0.8,
    "metrics": {
      "execution_accuracy": 0.75,
      "avg_latency_ms": 1200,
      "user_edit_rate": 0.15,
      "satisfaction_rate": 0.82
    }
  },
  "version_b": {
    "prompt_id": "v2-uuid",
    "traffic": 0.2,
    "metrics": {
      "execution_accuracy": 0.78,
      "avg_latency_ms": 1400,
      "user_edit_rate": 0.12,
      "satisfaction_rate": 0.85
    }
  },
  "recommendation": "version_b",
  "confidence": 0.92
}
```

### 7.3 A/B 测试规则

- 最少运行 1000 次请求后才可得出结论
- 置信度阈值 0.95（p < 0.05）
- 测试周期不超过 2 周
- 效果提升 < 2% 可视为无显著差异

## 8. Token 预算控制

### 8.1 预算分配

| 场景 | System Prompt | Context | Few-shot | Question | 最大总计 |
|------|--------------|---------|----------|----------|---------|
| NL2SQL | ~1500 | ~3000 | ~2000 | ~500 | ≤ 8000 |
| Intent | ~500 | 0 | 0 | ~500 | ≤ 2000 |
| Explanation | ~500 | ~1000 | 0 | ~300 | ≤ 2000 |
| Correction | ~800 | ~2000 | ~500 | ~500 | ≤ 4000 |

### 8.2 超预算处理

当 Context + Few-shot 超过预算时，按优先级裁剪：

1. 减少 Few-shot 示例数量（3 → 2 → 1）
2. 裁剪 SemanticContext（移除低相关度表的详细信息）
3. 如果仍超预算，返回降级提示

```python
def assemble_prompt(scene: str, context: SemanticContext, question: str) -> str:
    template = prompt_manager.get_active(scene)
    budget = TOKEN_BUDGETS[scene]

    context_tokens = count_tokens(context.to_prompt_text())
    question_tokens = count_tokens(question)
    remaining = budget - count_tokens(template) - question_tokens - context_tokens

    if remaining < 0:
        context = context.truncate_to_token_budget(budget * 0.4)

    examples = select_few_shots(question, max_tokens=min(remaining, 2000), max_count=3)
    return template.format(context=context, examples=examples, question=question)
```

## 9. Prompt 编写 Checklist

- [ ] 角色定义清晰，能力边界明确
- [ ] 规则具体可执行，无歧义
- [ ] SQL 方言明确指定
- [ ] 禁止事项完整列出
- [ ] Token 总量在预算范围内
- [ ] Few-shot 示例覆盖主要查询模式
- [ ] 已通过 10+ 测试用例验证
- [ ] A/B 测试评估效果提升
