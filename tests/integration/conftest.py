"""集成测试共享 fixtures。

提供：
- httpx.AsyncClient fixture（模拟 FastAPI TestClient）
- 认证相关 fixtures（测试 token、测试用户）
- 共享的 mock 对象（LLM、Redis、数据库）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# 路径注册：确保 services/ 和 libs/ 的 src 目录在 sys.path 中
# ---------------------------------------------------------------------------

_project_root = Path(__file__).resolve().parent.parent.parent

_services_src = _project_root / "services"
for svc_dir in _services_src.iterdir():
    src = svc_dir / "src"
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))

_libs_src = _project_root / "libs"
for lib_dir in _libs_src.iterdir():
    src = lib_dir / "src"
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))


# ---------------------------------------------------------------------------
# 测试常量
# ---------------------------------------------------------------------------

TEST_TENANT_ID = "00000000-0000-0000-0000-000000000001"
TEST_USER_ID = "00000000-0000-0000-0000-000000000099"
TEST_USER_EMAIL = "test-admin@datapilot.local"
TEST_JWT_SECRET = "integration-test-secret-key-at-least-32-characters"


# ---------------------------------------------------------------------------
# 测试数据 fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tenant_id() -> str:
    """生成默认租户 ID。"""
    return TEST_TENANT_ID


@pytest.fixture
def user_id() -> str:
    """生成默认用户 ID。"""
    return TEST_USER_ID


@pytest.fixture
def session_id() -> str:
    """生成随机会话 ID。"""
    return str(uuid4())


@pytest.fixture
def trace_id() -> str:
    """生成随机 trace ID。"""
    return uuid4().hex[:16]


# ---------------------------------------------------------------------------
# 认证 fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_access_token() -> str:
    """生成测试用的 JWT access token。

    使用与 auth-service 相同的 JWT 编码逻辑，但使用固定密钥。
    """
    import jwt

    now = __import__("time").time()
    payload = {
        "sub": TEST_USER_ID,
        "tenant_id": TEST_TENANT_ID,
        "role": "admin",
        "type": "access",
        "jti": str(uuid4()),
        "iat": int(now),
        "exp": int(now) + 3600,
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def test_headers(test_access_token: str) -> dict[str, str]:
    """生成带 Authorization 头的请求头。"""
    return {"Authorization": f"Bearer {test_access_token}"}


@pytest.fixture
def test_user() -> dict[str, Any]:
    """生成测试用户数据。"""
    return {
        "id": TEST_USER_ID,
        "tenant_id": TEST_TENANT_ID,
        "email": TEST_USER_EMAIL,
        "display_name": "集成测试管理员",
        "role": "admin",
        "is_active": True,
    }


# ---------------------------------------------------------------------------
# Mock LLM Router
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm_generate() -> AsyncMock:
    """创建 mock LLM generate 方法，返回预定义的 NL2SQL JSON。"""
    return AsyncMock(return_value={
        "content": json.dumps(
            {
                "sql": "SELECT COUNT(*) AS total FROM orders WHERE created_at >= '2024-01-01'",
                "explanation": "查询 2024 年以来的订单总数",
                "confidence": 0.92,
            },
            ensure_ascii=False,
        ),
        "explanation": "查询 2024 年以来的订单总数",
        "confidence": 0.92,
    })


# ---------------------------------------------------------------------------
# Mock Redis
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis() -> MagicMock:
    """创建 mock Redis 客户端。"""
    redis_mock = MagicMock()
    redis_mock.ping = AsyncMock(return_value=True)
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.incr = AsyncMock(return_value=1)
    redis_mock.expire = AsyncMock(return_value=True)

    # pipeline 支持
    pipeline_mock = MagicMock()
    pipeline_mock.incr = MagicMock()
    pipeline_mock.expire = MagicMock()
    pipeline_mock.execute = AsyncMock(return_value=[1, True])
    redis_mock.pipeline = MagicMock(return_value=pipeline_mock)

    return redis_mock


# ---------------------------------------------------------------------------
# Mock 数据库
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """创建 mock 数据库 session。"""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# 示例语义上下文
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_semantic_context() -> Any:
    """生成电商场景的示例语义上下文。"""
    from datapilot_sqlgen.generator.models import (
        ColumnInfo,
        DimensionInfo,
        MetricInfo,
        SemanticContext,
        TableInfo,
        TableRelationship,
    )

    return SemanticContext(
        tables=[
            TableInfo(
                table_name="orders",
                description="订单表",
                columns=[
                    ColumnInfo(name="id", col_type="BIGINT", description="订单 ID", is_primary_key=True),
                    ColumnInfo(name="user_id", col_type="BIGINT", description="用户 ID"),
                    ColumnInfo(name="product_id", col_type="BIGINT", description="商品 ID"),
                    ColumnInfo(name="amount", col_type="DECIMAL(12,2)", description="订单金额（元）"),
                    ColumnInfo(name="quantity", col_type="INT", description="购买数量"),
                    ColumnInfo(name="status", col_type="VARCHAR(20)", description="订单状态"),
                    ColumnInfo(name="city", col_type="VARCHAR(50)", description="下单城市"),
                    ColumnInfo(name="created_at", col_type="DATETIME", description="下单时间"),
                ],
            ),
            TableInfo(
                table_name="users",
                description="用户表",
                columns=[
                    ColumnInfo(name="id", col_type="BIGINT", description="用户 ID", is_primary_key=True),
                    ColumnInfo(name="name", col_type="VARCHAR(100)", description="用户名"),
                    ColumnInfo(name="region", col_type="VARCHAR(50)", description="地区"),
                    ColumnInfo(name="segment", col_type="VARCHAR(30)", description="用户分层"),
                    ColumnInfo(name="registered_at", col_type="DATETIME", description="注册时间"),
                    ColumnInfo(name="last_login_at", col_type="DATETIME", description="最近登录时间"),
                ],
            ),
            TableInfo(
                table_name="products",
                description="商品表",
                columns=[
                    ColumnInfo(name="id", col_type="BIGINT", description="商品 ID", is_primary_key=True),
                    ColumnInfo(name="name", col_type="VARCHAR(200)", description="商品名称"),
                    ColumnInfo(name="category", col_type="VARCHAR(50)", description="商品类目"),
                    ColumnInfo(name="price", col_type="DECIMAL(10,2)", description="单价"),
                    ColumnInfo(name="stock", col_type="INT", description="库存数量"),
                ],
            ),
            TableInfo(
                table_name="inventory",
                description="库存表",
                columns=[
                    ColumnInfo(name="id", col_type="BIGINT", description="库存 ID", is_primary_key=True),
                    ColumnInfo(name="product_id", col_type="BIGINT", description="商品 ID"),
                    ColumnInfo(name="warehouse", col_type="VARCHAR(50)", description="仓库"),
                    ColumnInfo(name="stock_qty", col_type="INT", description="库存数量"),
                    ColumnInfo(name="alert_threshold", col_type="INT", description="预警阈值"),
                    ColumnInfo(name="updated_at", col_type="DATETIME", description="更新时间"),
                ],
            ),
        ],
        relationships=[
            TableRelationship(
                left_table="orders",
                right_table="users",
                join_condition="orders.user_id = users.id",
                join_type="left",
            ),
            TableRelationship(
                left_table="orders",
                right_table="products",
                join_condition="orders.product_id = products.id",
                join_type="left",
            ),
            TableRelationship(
                left_table="inventory",
                right_table="products",
                join_condition="inventory.product_id = products.id",
                join_type="left",
            ),
        ],
        metrics=[
            MetricInfo(name="GMV", calculation="SUM(orders.amount)", unit="元", description="商品交易总额"),
            MetricInfo(name="订单量", calculation="COUNT(DISTINCT orders.id)", unit="个", description="订单总数"),
            MetricInfo(name="客单价", calculation="SUM(orders.amount) / COUNT(DISTINCT orders.id)", unit="元"),
            MetricInfo(name="DAU", calculation="COUNT(DISTINCT user_id)", unit="人", description="日活跃用户数"),
        ],
        dimensions=[
            DimensionInfo(name="地区", column_name="region", table_name="users"),
            DimensionInfo(name="城市", column_name="city", table_name="orders"),
            DimensionInfo(name="时间", column_name="created_at", table_name="orders"),
            DimensionInfo(name="商品类目", column_name="category", table_name="products"),
            DimensionInfo(name="用户分层", column_name="segment", table_name="users"),
            DimensionInfo(name="仓库", column_name="warehouse", table_name="inventory"),
        ],
        dialect="mysql",
    )


# ---------------------------------------------------------------------------
# NL2SQL Pipeline Mock 构建器
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_budget_manager() -> MagicMock:
    """创建 mock TokenBudgetManager。"""
    manager = MagicMock()
    manager.estimate_tokens.return_value = 50
    return manager


@pytest.fixture
def mock_intent_router() -> MagicMock:
    """创建 mock IntentRouter。"""
    router = MagicMock()
    router.classify = MagicMock(return_value=MagicMock(
        intent_type=MagicMock(value="sql_query"),
        confidence=0.95,
    ))
    return router


@pytest.fixture
def mock_intent_parser() -> MagicMock:
    """创建 mock IntentParser。"""
    parser = MagicMock()
    parser.parse = MagicMock(return_value=MagicMock(
        raw_question="测试问题",
        query_type=MagicMock(value="aggregation"),
        filters=[],
        time_range=None,
    ))
    return parser


@pytest.fixture
def mock_schema_linker() -> MagicMock:
    """创建 mock SchemaLinker。"""
    linker = MagicMock()
    # 默认返回空的语义上下文（使用 intent 模块的模型）
    linker.link = MagicMock(return_value=MagicMock(
        selected_tables=[],
        selected_metrics=[],
        selected_dimensions=[],
        join_path=[],
    ))
    return linker


@pytest.fixture
def mock_fewshot_matcher() -> MagicMock:
    """创建 mock FewShot Matcher。"""
    matcher = MagicMock()
    matcher.match = AsyncMock(return_value=[])
    return matcher


@pytest.fixture
def nl2sql_pipeline(
    sample_semantic_context: Any,
    mock_budget_manager: MagicMock,
    mock_llm_generate: AsyncMock,
    mock_intent_router: MagicMock,
    mock_intent_parser: MagicMock,
    mock_schema_linker: MagicMock,
    mock_fewshot_matcher: MagicMock,
) -> Any:
    """构建配置完整的 NL2SQLPipeline 实例（所有依赖已 mock）。"""
    from datapilot_sqlgen.generator.models import FewShotExample
    from datapilot_sqlgen.generator.pipeline import NL2SQLPipeline
    from datapilot_sqlgen.generator.postprocess import SQLPostProcessor
    from datapilot_sqlgen.generator.prompt_builder import PromptBuilder

    prompt_builder = PromptBuilder(budget_manager=mock_budget_manager)
    postprocessor = SQLPostProcessor()

    # 构建 mock LLM Router
    llm_router = MagicMock()
    llm_router.generate = mock_llm_generate

    pipeline = NL2SQLPipeline(
        prompt_builder=prompt_builder,
        postprocessor=postprocessor,
        fewshot_matcher=mock_fewshot_matcher,
        intent_router=mock_intent_router,
        intent_parser=mock_intent_parser,
        schema_linker=mock_schema_linker,
        llm_router=llm_router,
    )
    return pipeline
