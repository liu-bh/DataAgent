"""test_chart_recommender 测试配置与共享 fixtures。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 确保项目源码路径可被导入
project_root = Path(__file__).resolve().parent.parent.parent.parent
agent_service_path = project_root / "services" / "agent-service" / "src"
llm_lib_path = project_root / "libs" / "datapilot-llm" / "src"
common_lib_path = project_root / "libs" / "datapilot-common" / "src"
for p in (agent_service_path, llm_lib_path, common_lib_path):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)


# ---------- 共享测试数据 ----------

SAMPLE_COLUMNS_TIME_NUMERIC = [
    {"name": "date", "type": "date"},
    {"name": "sales", "type": "float"},
    {"name": "profit", "type": "float"},
]

SAMPLE_ROWS_TIME_NUMERIC = [
    {"date": "2024-01", "sales": 1000.0, "profit": 200.0},
    {"date": "2024-02", "sales": 1200.0, "profit": 250.0},
    {"date": "2024-03", "sales": 1500.0, "profit": 300.0},
]

SAMPLE_COLUMNS_DIMENSION_NUMERIC = [
    {"name": "region", "type": "varchar"},
    {"name": "sales", "type": "float"},
    {"name": "count", "type": "int"},
]

SAMPLE_ROWS_DIMENSION_NUMERIC = [
    {"region": "华东", "sales": 5000.0, "count": 120},
    {"region": "华南", "sales": 4200.0, "count": 98},
    {"region": "华北", "sales": 3800.0, "count": 85},
    {"region": "西部", "sales": 2900.0, "count": 67},
]

SAMPLE_COLUMNS_FEW_CATEGORIES = [
    {"name": "status", "type": "varchar"},
    {"name": "amount", "type": "float"},
]

SAMPLE_ROWS_FEW_CATEGORIES = [
    {"status": "已完成", "amount": 5000.0},
    {"status": "进行中", "amount": 3000.0},
    {"status": "已取消", "amount": 1000.0},
]

SAMPLE_COLUMNS_DUAL_NUMERIC = [
    {"name": "price", "type": "float"},
    {"name": "quantity", "type": "int"},
    {"name": "category", "type": "varchar"},
]

SAMPLE_ROWS_DUAL_NUMERIC = [
    {"price": 100.0, "quantity": 5, "category": "A"},
    {"price": 200.0, "quantity": 3, "category": "B"},
    {"price": 150.0, "quantity": 8, "category": "C"},
]


@pytest.fixture
def sample_columns_time_numeric():
    """时间+数值列。"""
    return SAMPLE_COLUMNS_TIME_NUMERIC


@pytest.fixture
def sample_rows_time_numeric():
    """时间+数值行。"""
    return SAMPLE_ROWS_TIME_NUMERIC


@pytest.fixture
def sample_columns_dim_numeric():
    """维度+数值列。"""
    return SAMPLE_COLUMNS_DIMENSION_NUMERIC


@pytest.fixture
def sample_rows_dim_numeric():
    """维度+数值行。"""
    return SAMPLE_ROWS_DIMENSION_NUMERIC


@pytest.fixture
def sample_columns_few_categories():
    """少量分类+数值列。"""
    return SAMPLE_COLUMNS_FEW_CATEGORIES


@pytest.fixture
def sample_rows_few_categories():
    """少量分类+数值行。"""
    return SAMPLE_ROWS_FEW_CATEGORIES


@pytest.fixture
def sample_columns_dual_numeric():
    """双数值+维度列。"""
    return SAMPLE_COLUMNS_DUAL_NUMERIC


@pytest.fixture
def sample_rows_dual_numeric():
    """双数值+维度行。"""
    return SAMPLE_ROWS_DUAL_NUMERIC


@pytest.fixture
def mock_llm_router():
    """模拟 LLM Router。"""
    from unittest.mock import AsyncMock

    from datapilot_llm.provider import LLMResponse

    router = AsyncMock()
    router.generate.return_value = LLMResponse(
        content='[{"type": "line", "confidence": 0.95}]',
        prompt_tokens=100,
        completion_tokens=50,
        model="qwen-plus",
        latency_ms=200.0,
    )
    return router
