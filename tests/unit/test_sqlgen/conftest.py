"""NL2SQL 单元测试配置和共享 fixtures。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

# 确保项目源码路径可被导入
project_root = Path(__file__).resolve().parent.parent.parent.parent / "services" / "sql-generator-service" / "src"
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 同时确保 libs 路径可被导入
libs_root = Path(__file__).resolve().parent.parent.parent.parent / "libs"
for lib_dir in libs_root.iterdir():
    if lib_dir.is_dir():
        lib_src = lib_dir / "src"
        if lib_src.exists() and str(lib_src) not in sys.path:
            sys.path.insert(0, str(lib_src))


@pytest.fixture
def tenant_id() -> str:
    """生成默认租户 ID。"""
    return "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def session_id() -> str:
    """生成默认会话 ID。"""
    return str(uuid4())


@pytest.fixture
def sample_semantic_context() -> Any:
    """生成示例语义上下文。"""
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
                    ColumnInfo(name="amount", col_type="DECIMAL(12,2)", description="订单金额（元）"),
                    ColumnInfo(name="status", col_type="VARCHAR(20)", description="订单状态"),
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
        ],
        metrics=[
            MetricInfo(name="GMV", calculation="SUM(orders.amount)", unit="元", description="商品交易总额"),
            MetricInfo(name="订单量", calculation="COUNT(DISTINCT orders.id)", unit="个", description="订单总数"),
        ],
        dimensions=[
            DimensionInfo(name="地区", column_name="region", table_name="users"),
            DimensionInfo(name="时间", column_name="created_at", table_name="orders"),
        ],
        dialect="mysql",
    )


@pytest.fixture
def sample_few_shots() -> list[Any]:
    """生成示例 Few-shot 列表。"""
    from datapilot_sqlgen.generator.models import FewShotExample

    return [
        FewShotExample(
            question="上个月各地区的销售额是多少？",
            sql="SELECT u.region, SUM(o.amount) AS revenue FROM orders o LEFT JOIN users u ON o.user_id = u.id WHERE o.created_at >= DATE_FORMAT(CURRENT_DATE - INTERVAL 1 MONTH, '%Y-%m-01') GROUP BY u.region ORDER BY revenue DESC",
            domain="电商",
            difficulty="medium",
            similarity_score=0.85,
        ),
        FewShotExample(
            question="今天的订单量是多少？",
            sql="SELECT COUNT(*) AS order_count FROM orders WHERE DATE(created_at) = CURRENT_DATE",
            domain="电商",
            difficulty="simple",
            similarity_score=0.78,
        ),
        FewShotExample(
            question="客单价最高的前5个用户",
            sql="SELECT u.name, SUM(o.amount) / COUNT(DISTINCT o.id) AS avg_order_value FROM orders o LEFT JOIN users u ON o.user_id = u.id GROUP BY u.id, u.name ORDER BY avg_order_value DESC LIMIT 5",
            domain="电商",
            difficulty="medium",
            similarity_score=0.65,
        ),
    ]


@pytest.fixture
def mock_budget_manager() -> MagicMock:
    """创建 mock TokenBudgetManager。"""
    manager = MagicMock()
    manager.estimate_tokens.return_value = 50
    return manager


@pytest.fixture
def mock_llm_router() -> MagicMock:
    """创建 mock LLM Router。"""
    router = MagicMock()
    router.generate = MagicMock(return_value={
        "content": '{"sql": "SELECT COUNT(*) FROM orders", "explanation": "统计订单数量", "confidence": 0.9}',
        "explanation": "统计订单数量",
        "confidence": 0.9,
    })
    return router


@pytest.fixture
def mock_intent_router() -> MagicMock:
    """创建 mock Intent Router。"""
    router = MagicMock()
    router.route = MagicMock(return_value={
        "intent": "sql_query",
        "confidence": 0.95,
    })
    return router


@pytest.fixture
def mock_intent_parser() -> MagicMock:
    """创建 mock Intent Parser。"""
    parser = MagicMock()
    parser.parse = MagicMock(return_value={
        "raw_question": "测试问题",
        "intent_type": "sql_query",
        "filters": [],
        "metrics": ["GMV"],
        "dimensions": ["时间"],
        "time_range": None,
    })
    return parser


@pytest.fixture
def mock_schema_linker() -> MagicMock:
    """创建 mock Schema Linker。"""
    linker = MagicMock()
    linker.link = MagicMock(side_effect=lambda q, ctx, tid: ctx)
    return linker


@pytest.fixture
def mock_fewshot_matcher() -> MagicMock:
    """创建 mock FewShot Matcher。"""
    matcher = MagicMock()
    matcher.match = MagicMock(return_value=[])
    return matcher
