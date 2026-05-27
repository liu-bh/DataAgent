"""测试配置和共享 fixtures。"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

# 确保项目源码路径可被导入
project_root = Path(__file__).resolve().parent.parent.parent.parent / "services" / "semantic-service" / "src"
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture
def sample_semantic_model_id() -> str:
    """生成一个语义模型 ID。"""
    return str(uuid4())


@pytest.fixture
def sample_metric_id() -> str:
    """生成一个指标 ID。"""
    return str(uuid4())


@pytest.fixture
def sample_dimension_id() -> str:
    """生成一个维度 ID。"""
    return str(uuid4())


@pytest.fixture
def sample_tenant_id() -> str:
    """生成默认租户 ID。"""
    return "00000000-0000-0000-0000-000000000001"
