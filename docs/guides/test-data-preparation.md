# 测试数据与 NL2SQL 评测指南

> 本文档说明如何准备测试数据集、编写 NL2SQL 测试用例、执行评测。

## 1. 测试数据架构

```
tests/
├── fixtures/
│   ├── sql/
│   │   ├── seed_data.sql              # 基础种子数据
│   │   ├── ecommerce_orders.sql       # 电商订单数据（10万行）
│   │   ├── ecommerce_products.sql     # 商品数据
│   │   └── ecommerce_users.sql        # 用户数据
│   ├── nl2sql/
│   │   ├── simple_cases.json          # 简单查询用例（50+）
│   │   ├── medium_cases.json          # 中等复杂度用例（30+）
│   │   ├── complex_cases.json         # 高复杂度用例（20+）
│   │   ├── edge_cases.json            # 边界用例
│   │   └── domain/
│   │       ├── ecommerce.json         # 电商领域
│   │       ├── finance.json           # 财务领域
│   │       └── operations.json        # 运营领域
│   └── mocks/
│       ├── semantic_context.json      # Mock 语义上下文
│       └── llm_responses.json         # Mock LLM 响应
└── evaluation/
    ├── run_evaluation.py              # 评测执行脚本
    ├── accuracy_report.json           # 评测报告
    └── baseline_scores.json           # 基线分数
```

## 2. 种子数据规范

### 2.1 数据生成原则

| 原则 | 说明 |
|------|------|
| 真实性 | 数据分布符合真实业务场景（二八定律、长尾分布） |
| 覆盖性 | 覆盖各种数据类型（NULL、空值、边界值、特殊字符） |
| 规模适中 | 单表 1-10 万行，既能测试性能又不至于测试太慢 |
| 可重现 | 使用固定种子生成，每次运行结果一致 |

### 2.2 电商示例数据

```sql
-- tests/fixtures/sql/ecommerce_orders.sql

-- 订单表：10 万行
-- 分布：80% 普通订单，15% 大额订单，5% 退款订单
-- 时间跨度：2025-01-01 至 2026-05-27
-- 金额分布：10-50000 元，均值 280 元

-- 关键测试点：
-- 1. NULL 值：部分字段允许 NULL（如 discount_amount）
-- 2. 特殊值：金额为 0、负数（退款）、极大值
-- 3. 时区：所有时间字段使用 +08:00 时区
-- 4. 多状态：待支付、已支付、已发货、已签收、已退款、已取消
```

### 2.3 数据生成脚本

```python
# tests/fixtures/generate_ecommerce_data.py
"""
使用 Faker 生成电商测试数据。
运行：python -m tests.fixtures.generate_ecommerce_data --rows 100000
"""
import argparse
from faker import Faker
import random
import json

fake = Faker('zh_CN')

ORDER_STATUSES = ['pending', 'paid', 'shipped', 'delivered', 'refunded', 'cancelled']
STATUS_WEIGHTS = [0.05, 0.15, 0.20, 0.40, 0.05, 0.15]

def generate_orders(rows: int, output_path: str):
    orders = []
    for i in range(rows):
        status = random.choices(ORDER_STATUSES, weights=STATUS_WEIGHTS)[0]
        amount = round(random.lognormvariate(5.5, 1.2), 2)
        if status == 'refunded':
            amount = -abs(amount)

        orders.append({
            'id': i + 1,
            'user_id': random.randint(1, 10000),
            'product_id': random.randint(1, 500),
            'amount': amount,
            'discount_amount': random.choice([0, 0, 0, round(amount * 0.1, 2)]),
            'status': status,
            'created_at': fake.date_time_between(
                start_date='-18months', end_date='now'
            ).isoformat(),
            'payment_method': random.choice(['alipay', 'wechat', 'card', 'cod']),
        })

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--rows', type=int, default=100000)
    parser.add_argument('--output', type=str, default='tests/fixtures/sql/ecommerce_orders.json')
    args = parser.parse_args()
    generate_orders(args.rows, args.output)
```

## 3. NL2SQL 测试用例编写

### 3.1 用例格式

```json
{
  "id": "EC-001",
  "domain": "ecommerce",
  "difficulty": "simple",
  "question": "上个月的总营收是多少？",
  "expected_sql_patterns": [
    "SELECT.*SUM\\s*\\(.*amount.*\\).*FROM.*orders.*WHERE.*created_at.*BETWEEN",
    "SELECT.*SUM\\s*\\(.*amount.*\\).*FROM.*orders.*WHERE.*month"
  ],
  "expected_tables": ["orders"],
  "expected_metrics": ["GMV"],
  "tags": ["聚合", "时间过滤"],
  "notes": "测试基本的 SUM 聚合和时间范围过滤"
}
```

### 3.2 难度分级

| 难度 | 说明 | 典型特征 | Phase1 目标准确率 |
|------|------|---------|------------------|
| **simple** | 单表 + 单指标 + 简单过滤 | SUM/COUNT + WHERE | ≥ 90% |
| **medium** | 多表 JOIN + 多维度 + GROUP BY | JOIN + GROUP BY + HAVING | ≥ 70% |
| **complex** | 子查询 + 窗口函数 + 嵌套指标 | CTE + RANK + 嵌套计算 | ≥ 50% |

### 3.3 用例编写指南

#### Simple 用例（≥ 50 条）

```json
{
  "id": "EC-001",
  "difficulty": "simple",
  "question": "上个月的总营收是多少",
  "expected_sql_patterns": ["SUM.*amount.*orders"]
},
{
  "id": "EC-002",
  "difficulty": "simple",
  "question": "今天有多少笔订单",
  "expected_sql_patterns": ["COUNT.*orders.*created_at"]
},
{
  "id": "EC-003",
  "difficulty": "simple",
  "question": "订单金额最高的前10个用户",
  "expected_sql_patterns": ["ORDER BY.*DESC.*LIMIT 10"]
},
{
  "id": "EC-004",
  "difficulty": "simple",
  "question": "已发货的订单有多少",
  "expected_sql_patterns": ["COUNT.*status.*shipped"]
},
{
  "id": "EC-005",
  "difficulty": "simple",
  "question": "平均客单价是多少",
  "expected_sql_patterns": ["AVG.*amount"]
}
```

#### Medium 用例（≥ 30 条）

```json
{
  "id": "EC-M01",
  "difficulty": "medium",
  "question": "按商品类目统计上个月的销售额 TOP 10",
  "expected_sql_patterns": ["GROUP BY.*category.*ORDER BY.*DESC.*LIMIT"],
  "expected_tables": ["orders", "products", "order_items"]
},
{
  "id": "EC-M02",
  "difficulty": "medium",
  "question": "每个月的退款率趋势",
  "expected_sql_patterns": ["GROUP BY.*month.*refunded"],
  "expected_tables": ["orders"]
},
{
  "id": "EC-M03",
  "difficulty": "medium",
  "question": "各地区的订单量和平均金额",
  "expected_sql_patterns": ["GROUP BY.*region.*COUNT.*AVG"],
  "expected_tables": ["orders", "users"]
}
```

#### Complex 用例（≥ 20 条）

```json
{
  "id": "EC-C01",
  "difficulty": "complex",
  "question": "与上月相比，哪些商品类目的销售额下降超过10%",
  "expected_sql_patterns": ["CTE|WITH.*LAG|LEAD.*percentage|ratio"],
  "expected_tables": ["orders", "products", "order_items"]
},
{
  "id": "EC-C02",
  "difficulty": "complex",
  "question": "每个月购买金额排名前10%的用户，他们的消费金额占总营收的比例",
  "expected_sql_patterns": ["PERCENT_RANK|NTILE.*SUM.*CASE"],
  "expected_tables": ["orders", "users"]
}
```

### 3.4 用例编写规则

1. **问题自然性**：使用真实用户会问的自然语言，不要写成 SQL 的直译
2. **口语化变体**：每个场景至少 2 种问法（"上个月营收" vs "上个月卖了多少钱"）
3. **业务同义词**：覆盖业务术语的不同表达
4. **不要假设用户懂表结构**：问题中不应出现表名/列名
5. **边界值测试**：包含时间边界（"昨天"、"上个月"）、空结果、极大/极小值

## 4. 评测执行

### 4.1 运行评测

```bash
# 运行全部评测
cd services/sql-generator-service
uv run python -m tests.evaluation.run_evaluation \
  --cases tests/fixtures/nl2sql/ \
  --output tests/evaluation/accuracy_report.json

# 按难度运行
uv run python -m tests.evaluation.run_evaluation \
  --cases tests/fixtures/nl2sql/simple_cases.json \
  --difficulty simple

# 按领域运行
uv run python -m tests.evaluation.run_evaluation \
  --cases tests/fixtures/nl2sql/domain/ecommerce.json
```

### 4.2 评测指标

| 指标 | 说明 | 计算方式 |
|------|------|---------|
| **Execution Accuracy (EX)** | 生成 SQL 执行后结果是否正确 | 对比实际结果与预期结果 |
| **Exact Match (EM)** | 生成的 SQL 与预期 SQL 是否完全一致 | 字符串/AST 完全匹配 |
| **Pattern Match (PM)** | 生成 SQL 是否匹配预期的 SQL 模式 | 正则表达式匹配 |
| **Table Match (TM)** | 涉及的表是否正确 | 集合比较 |
| **User Edit Rate (UER)** | 用户需要编辑 SQL 的比例 | 实际用户反馈统计 |

### 4.3 评测报告格式

```json
{
  "run_at": "2026-05-27T14:30:00+08:00",
  "model": "deepseek-v3",
  "overall": {
    "total_cases": 100,
    "execution_accuracy": 0.72,
    "pattern_match": 0.85,
    "table_match": 0.92
  },
  "by_difficulty": {
    "simple": {"total": 50, "execution_accuracy": 0.90, "pattern_match": 0.95},
    "medium": {"total": 30, "execution_accuracy": 0.67, "pattern_match": 0.80},
    "complex": {"total": 20, "execution_accuracy": 0.45, "pattern_match": 0.70}
  },
  "by_domain": {
    "ecommerce": {"total": 40, "execution_accuracy": 0.75},
    "finance": {"total": 35, "execution_accuracy": 0.69},
    "operations": {"total": 25, "execution_accuracy": 0.72}
  },
  "failure_analysis": {
    "most_common_errors": [
      {"error_type": "wrong_join", "count": 8},
      {"error_type": "missing_filter", "count": 5},
      {"error_type": "wrong_aggregation", "count": 3}
    ]
  }
}
```

### 4.4 基线分数（Phase1 目标）

| 指标 | Simple | Medium | Complex | 整体 |
|------|--------|--------|---------|------|
| EX | ≥ 90% | ≥ 70% | ≥ 50% | ≥ 75% |
| PM | ≥ 95% | ≥ 80% | ≥ 65% | ≥ 85% |
| TM | ≥ 98% | ≥ 95% | ≥ 90% | ≥ 95% |

## 5. Mock 数据

### 5.1 Mock LLM 响应

```python
# tests/fixtures/mocks/llm_responses.json
{
  "nl2sql_simple": {
    "response": "SELECT SUM(amount) FROM orders WHERE created_at >= '2026-04-01' AND created_at < '2026-05-01'",
    "tokens": {"prompt": 1200, "completion": 85}
  },
  "nl2sql_with_join": {
    "response": "SELECT p.category_name, SUM(oi.quantity * oi.price) AS revenue FROM orders o JOIN order_items oi ON o.id = oi.order_id JOIN products p ON oi.product_id = p.id WHERE o.created_at >= '2026-04-01' GROUP BY p.category_name ORDER BY revenue DESC LIMIT 10",
    "tokens": {"prompt": 2500, "completion": 200}
  }
}
```

### 5.2 Mock 语义上下文

```json
{
  "tables": [
    {
      "table_id": "orders",
      "table_name": "orders",
      "description": "订单表",
      "columns": [
        {"name": "id", "type": "BIGINT"},
        {"name": "amount", "type": "DECIMAL(12,2)", "description": "订单金额"}
      ]
    }
  ],
  "metrics": [
    {"name": "GMV", "calculation": "SUM(amount)"}
  ],
  "dimensions": [
    {"name": "时间", "column_name": "created_at"}
  ]
}
```

## 6. 持续维护

### 6.1 用例管理

- **新增用例**：每次发现新的用户查询模式，添加到对应难度/领域的 JSON 文件
- **淘汰用例**：准确率持续 100% 的简单用例可降级为冒烟测试
- **用例评审**：每两周评审一次用例集，确保覆盖真实用户场景

### 6.2 回归测试

每次 Prompt 修改、模型切换、或代码变更后，必须运行全量评测：

```bash
# CI 中自动运行
uv run pytest tests/evaluation/ -v --tb=short

# 对比上次报告，准确率下降超过 2% 则阻断合并
```
