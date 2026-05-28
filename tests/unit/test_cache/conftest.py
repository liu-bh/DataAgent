"""test_cache 测试配置与共享 fixtures。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# 确保项目源码路径可被导入
project_root = Path(__file__).resolve().parent.parent.parent.parent
service_src = project_root / "services" / "query-executor-service" / "src"
if str(service_src) not in sys.path:
    sys.path.insert(0, str(service_src))

# 同时确保 libs 路径可被导入
libs_root = project_root / "libs"
for lib_dir in libs_root.iterdir():
    if lib_dir.is_dir():
        lib_src = lib_dir / "src"
        if lib_src.exists() and str(lib_src) not in sys.path:
            sys.path.insert(0, str(lib_src))


@pytest.fixture
def tenant_id() -> str:
    """默认租户 ID。"""
    return "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def sample_sql() -> str:
    """示例 SQL 语句。"""
    return "SELECT user_id, COUNT(*) AS order_count FROM orders GROUP BY user_id"


@pytest.fixture
def sample_data_small() -> bytes:
    """小数据集（<1MB），适合 Redis。"""
    return b'{"columns":["user_id","order_count"],"rows":[[1,5],[2,3]]}'


@pytest.fixture
def sample_data_large() -> bytes:
    """大数据集（>=1MB），适合 MinIO。"""
    # 生成 2MB 数据
    return b"x" * (2 * 1024 * 1024)


@pytest.fixture
def mock_redis_cache() -> AsyncMock:
    """创建 mock RedisResultCache。"""
    mock = AsyncMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = True
    mock.exists.return_value = False
    mock.get_ttl.return_value = -2
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_minio_cache() -> AsyncMock:
    """创建 mock MinIOResultCache。"""
    mock = AsyncMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = True
    mock.exists.return_value = False
    mock.ensure_bucket = AsyncMock()
    mock.close = AsyncMock()
    return mock
