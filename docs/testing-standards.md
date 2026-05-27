# 测试规范

## 1. 测试分层

| 层级 | 框架 | 覆盖范围 | 要求 |
|------|------|---------|------|
| 单元测试 | pytest | 业务逻辑、工具函数 | CI 门禁，覆盖率 >= 70% |
| 集成测试 | pytest + testcontainers | 服务间交互、数据库操作 | PR 检查 |
| E2E 测试 | Playwright | 前端完整用户流程 | 每日构建 |
| NL2SQL 评估 | 自研评测框架 | SQL 生成准确率 | 每个迭代 |
| 性能测试 | k6 / Locust | 接口吞吐、延迟 | 每个里程碑 |

## 2. 单元测试 (pytest)

### 2.1 文件组织

```
tests/
├── unit/
│   ├── test_semantic/
│   │   ├── test_retrieval.py
│   │   ├── test_translation.py
│   │   └── conftest.py          # 共享 fixtures
│   ├── test_sqlgen/
│   │   ├── test_ast_builder.py
│   │   └── test_nl2sql.py
│   └── test_common/
│       └── test_exceptions.py
├── integration/
│   ├── test_api/
│   ├── test_grpc/
│   └── conftest.py              # testcontainers 启动
├── e2e/
│   ├── chat_flow.spec.ts        # Playwright
│   └── admin_flow.spec.ts
└── benchmarks/
    └── nl2sql_eval.py
```

### 2.2 测试命名

```python
# 格式：test_<被测方法>_<场景>_<预期结果>
def test_resolve_schema_with_empty_intent_returns_none():
    ...

def test_build_sql_ast_with_join_produces_valid_sql():
    ...

def test_nl2sql_simple_aggregation_generates_correct_query():
    ...
```

### 2.3 AAA 模式

```python
def test_retrieve_metrics_by_keyword_returns_matches():
    # Arrange
    repo = MetricRepository(session)
    await repo.create(Metric(name="GMV", tags=["电商", "核心"]))
    await repo.create(Metric(name="客单价", tags=["电商"]))

    # Act
    results = await repo.search(keyword="电商")

    # Assert
    assert len(results) == 2
    assert results[0].name == "GMV"
```

### 2.4 Fixture 使用

```python
# conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

@pytest.fixture
async def db_session():
    """每个测试独立的数据库 session"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine)
    async with session_factory() as session:
        yield session
    await engine.dispose()

@pytest.fixture
def mock_llm_response():
    """模拟 LLM 返回"""
    return {
        "intent": "query",
        "metrics": ["GMV"],
        "dimensions": ["month"],
    }
```

### 2.5 Mock 策略

```python
# 外部依赖用 mock
from unittest.mock import AsyncMock, patch

async def test_chat_with_llm_failure_returns_error():
    mock_provider = AsyncMock()
    mock_provider.generate.side_effect = LLMError("deepseek", "timeout")

    service = ChatService(llm=mock_provider)

    result = await service.chat("查询营收")
    assert result.error.code == "LLM_TIMEOUT"

# 数据库操作用真实内存库（SQLite），不 mock
# HTTP 外部调用用 respx（httpx mock）
import respx

@respx.mock
async def test_call_embedding_api_returns_vector():
    respx.post("https://dashscope.aliyuncs.com/api/v1/embeddings").mock(
        return_value=Response(200, json={"output": {"embeddings": [[0.1, 0.2]]}})
    )
    result = await embed_text("营收")
    assert len(result) == 2
```

**Mock 原则：**
- 外部服务（LLM API、第三方 API）用 mock
- 数据库用内存 SQLite（单测）或 testcontainers（集成测试）
- 禁止 mock 被测对象本身的核心方法
- 同步 mock 用 `unittest.mock`，异步 mock 用 `AsyncMock`

## 3. 集成测试

### 3.1 Testcontainers

```python
# conftest.py
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres():
    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        yield pg

@pytest.fixture(scope="session")
async def pg_session(postgres):
    engine = create_async_engine(postgres.get_connection_url())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine)
    async with session_factory() as session:
        yield session
```

### 3.2 API 集成测试

```python
from httpx import AsyncClient, ASGITransport

async def test_create_metric_returns_201():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/metrics", json={
            "name": "GMV",
            "calculation": "SUM(amount)",
        })
    assert resp.status_code == 201
    assert resp.json()["data"]["name"] == "GMV"
```

## 4. NL2SQL 评估

### 4.1 评测数据集

```yaml
# tests/benchmarks/nl2sql_cases.yaml
cases:
  - id: simple_001
    difficulty: simple
    input: "上个月的总订单量是多少"
    expected_sql: "SELECT COUNT(*) FROM orders WHERE order_date >= '2026-04-01'"
    expected_tables: ["orders"]
    expected_metrics: ["订单量"]

  - id: medium_001
    difficulty: medium
    input: "按产品类别统计今年每个季度的营收趋势"
    expected_sql: "SELECT category, QUARTER(order_date), SUM(amount) FROM orders WHERE order_date >= '2026-01-01' GROUP BY category, QUARTER(order_date)"
    expected_tables: ["orders"]
    expected_metrics: ["营收"]
    expected_dimensions: ["产品类别", "季度"]

  - id: complex_001
    difficulty: complex
    input: "各区域本月环比上月销量增长率超过10%的商品有哪些"
    expected_sql: "SELECT region, product, (curr.cnt - prev.cnt) * 1.0 / prev.cnt AS growth_rate FROM (...) curr JOIN (...) prev ON ..."
    expected_tables: ["orders", "products"]
    expected_metrics: ["销量"]
    expected_dimensions: ["区域", "商品", "环比"]
```

### 4.2 评估指标

| 指标 | 计算 | Phase1 目标 | Phase2 目标 |
|------|------|------------|------------|
| 简单查询准确率 | SQL 等价匹配 | >= 70% | >= 85% |
| 中等查询准确率 | SQL 等价匹配 | >= 50% | >= 75% |
| 复杂查询准确率 | SQL 等价匹配 | >= 30% | >= 60% |
| 表选择准确率 | 命中正确的表 | >= 90% | >= 95% |
| 指标识别准确率 | 命中正确的指标 | >= 85% | >= 90% |
| SQL 可执行率 | 语法正确可执行 | >= 95% | >= 98% |
| 用户 SQL 编辑率 | 用户需手动编辑的比例 | < 30% | < 15% |

## 5. E2E 测试 (Playwright)

```typescript
// tests/e2e/chat_flow.spec.ts
import { test, expect } from "@playwright/test";

test("用户可以完成一次 NL2SQL 查询", async ({ page }) => {
  await page.goto("/login");
  await page.fill("[name=email]", "admin@datapilot.com");
  await page.fill("[name=password]", "password");
  await page.click("button[type=submit]");

  await page.goto("/chat");
  await page.fill("[placeholder=输入你的问题]", "上月总营收");
  await page.press("[placeholder=输入你的问题]", "Enter");

  // 等待流式响应完成
  await expect(page.locator(".chat-message.assistant")).toBeVisible();
  await expect(page.locator(".sql-block")).toBeVisible();
  await expect(page.locator(".chart-container")).toBeVisible({ timeout: 30000 });
});
```

## 6. 性能测试

### 6.1 基准指标

| 指标 | 目标 |
|------|------|
| P50 延迟 | < 500ms（纯 SQL 生成） |
| P95 延迟 | < 2s（含 LLM 调用） |
| 吞吐量 | > 100 QPS |
| LLM 超时率 | < 5% |

### 6.2 k6 脚本示例

```javascript
import http from "k6/http";

export const options = {
  stages: [
    { duration: "1m", target: 50 },
    { duration: "3m", target: 100 },
    { duration: "1m", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<2000"],
    http_req_failed: ["rate<0.05"],
  },
};

export default function () {
  const payload = JSON.stringify({
    session_id: __ENV.SESSION_ID,
    content: "上月订单量",
  });
  http.post(`${__ENV.BASE_URL}/api/v1/chat`, payload, {
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${__ENV.TOKEN}` },
  });
}
```

## 7. CI 测试流程

```yaml
# GitHub Actions
test:
  runs-on: ubuntu-latest
  steps:
    - run: ruff check .
    - run: ruff format --check .
    - run: mypy src/
    - run: pytest tests/unit/ --cov=src --cov-fail-under=70
    - run: pytest tests/integration/
```

**CI 门禁规则：**
- ruff check 失败 → 阻断
- mypy 错误 → 阻断（逐步开启 strict）
- 单测覆盖率 < 70% → 阻断
- 集成测试失败 → 阻断
- E2E 测试失败 → 不阻断但发通知

## 8. 额外测试场景（Phase1）

| 测试场景 | 验证点 |
|---------|--------|
| 熔断降级 | 模拟 LLM 不可用，验证返回历史相似查询 |
| 数据脱敏 | 查询包含手机号字段，验证返回值已脱敏 |
| 列级权限 | 普通用户查询，验证敏感字段不出现在 SQL 和结果中 |
| 查询配额 | 用户超过日查询次数上限，验证返回 `QUOTA_EXCEEDED` |
| 大结果集分页 | 查询返回 > 1000 行，验证默认 LIMIT + 游标分页 |
| 数据新鲜度 | 查询 T+1 数据源，验证结果附带数据截止时间 |
| 意图路由 | 输入闲聊/超出范围问题，验证不走 NL2SQL 流程 |
| 用户反馈 | 编辑 SQL 后验证自动进入 Few-shot 候选库 |
| 会话管理 | 30min 无操作验证会话过期，50 条消息验证上限提示 |
