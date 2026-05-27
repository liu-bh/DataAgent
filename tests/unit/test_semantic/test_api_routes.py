"""API 路由单元测试。

使用 mock 的 AsyncSession 测试语义模型的 CRUD API 路由逻辑。
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from datapilot_common.exceptions import NotFoundError, ValidationError


# ---------------------------------------------------------------------------
# 辅助工具
# ---------------------------------------------------------------------------


def _make_model(**overrides) -> MagicMock:
    """构造 mock 的 SemanticModel 实例。"""
    defaults = {
        "id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "name": "电商指标体系",
        "description": "电商业务指标",
        "domain": "电商",
        "data_source_ids": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "deleted_at": None,
        "metrics": [],
        "dimensions": [],
    }
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_metric(**overrides) -> MagicMock:
    """构造 mock 的 Metric 实例。"""
    defaults = {
        "id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "semantic_model_id": str(uuid4()),
        "name": "GMV",
        "description": "商品交易总额",
        "calculation": "SUM(amount)",
        "unit": "元",
        "version": 1,
        "effective_time": datetime.now(timezone.utc),
        "parent_metric_id": None,
        "tags": [],
        "embedding": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "deleted_at": None,
    }
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_dimension(**overrides) -> MagicMock:
    """构造 mock 的 Dimension 实例。"""
    defaults = {
        "id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "semantic_model_id": str(uuid4()),
        "name": "地区",
        "column_name": "region",
        "table_id": None,
        "synonyms": [],
        "hierarchy": None,
        "is_virtual": False,
        "virtual_expression": None,
        "embedding": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "deleted_at": None,
    }
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


class MockResult:
    """模拟 SQLAlchemy 查询结果。"""

    def __init__(self, data: object | None = None, scalar: int | None = None) -> None:
        self._data = data
        self._scalar = scalar

    def scalar_one_or_none(self) -> object | None:
        return self._data

    def scalar(self) -> int | None:
        return self._scalar

    def scalars(self) -> MockScalars:
        return MockScalars(self._data if isinstance(self._data, list) else [self._data] if self._data else [])


class MockScalars:
    """模拟 scalars() 结果集。"""

    def __init__(self, items: list) -> None:
        self._items = items

    def all(self) -> list:
        return self._items


class MockSession:
    """模拟 AsyncSession。"""

    def __init__(self) -> None:
        self.execute_result: MockResult | None = None
        self.added: list = []
        self.committed = False

    async def execute(self, stmt) -> MockResult:
        return self.execute_result or MockResult()

    async def refresh(self, obj) -> None:
        pass

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True


# ---------------------------------------------------------------------------
# Schema 验证测试（不依赖路由）
# ---------------------------------------------------------------------------


class TestSemanticModelSchemaValidation:
    """语义模型 Schema 验证逻辑测试。"""

    def test_create_schema_with_valid_domain(self) -> None:
        """测试合法 domain 创建 Schema。"""
        from datapilot_semantic.models.schemas import SemanticModelCreate

        body = SemanticModelCreate(name="测试", domain="电商")
        assert body.domain == "电商"

    def test_create_schema_with_invalid_domain_raises(self) -> None:
        """测试非法 domain 抛出 ValidationError。"""
        from pydantic import ValidationError

        from datapilot_semantic.models.schemas import SemanticModelCreate

        with pytest.raises(ValidationError):
            SemanticModelCreate(name="测试", domain="医疗")

    def test_update_schema_exclude_unset(self) -> None:
        """测试 Update Schema 的 exclude_unset 行为。"""
        from datapilot_semantic.models.schemas import SemanticModelUpdate

        body = SemanticModelUpdate(description="新描述")
        dumped = body.model_dump(exclude_unset=True)
        assert dumped == {"description": "新描述"}
        assert "name" not in dumped


class TestMetricSchemaValidation:
    """指标 Schema 验证逻辑测试。"""

    def test_create_metric_requires_calculation(self) -> None:
        """测试创建指标必须有 calculation。"""
        from pydantic import ValidationError

        from datapilot_semantic.models.schemas import MetricCreate

        with pytest.raises(ValidationError):
            MetricCreate(
                semantic_model_id=str(uuid4()),
                name="测试",
                calculation="",
            )

    def test_metric_response_serialization(self) -> None:
        """测试 MetricResponse 序列化。"""
        from datapilot_semantic.models.schemas import MetricResponse

        now = datetime.now(timezone.utc)
        resp = MetricResponse(
            id=str(uuid4()),
            tenant_id=str(uuid4()),
            semantic_model_id=str(uuid4()),
            name="GMV",
            description=None,
            calculation="SUM(amount)",
            unit="元",
            version=1,
            effective_time=now,
            parent_metric_id=None,
            tags=["电商"],
            created_at=now,
            updated_at=now,
        )
        data = resp.model_dump()
        assert data["version"] == 1
        assert data["tags"] == ["电商"]


class TestDimensionSchemaValidation:
    """维度 Schema 验证逻辑测试。"""

    def test_virtual_dimension_requires_expression(self) -> None:
        """测试虚拟维度必须有表达式。"""
        from pydantic import ValidationError

        from datapilot_semantic.models.schemas import DimensionCreate

        with pytest.raises(ValidationError):
            DimensionCreate(
                semantic_model_id=str(uuid4()),
                name="虚拟维度",
                is_virtual=True,
            )

    def test_non_virtual_dimension_no_expression_ok(self) -> None:
        """测试非虚拟维度不需要表达式。"""
        from datapilot_semantic.models.schemas import DimensionCreate

        body = DimensionCreate(
            semantic_model_id=str(uuid4()),
            name="地区",
            is_virtual=False,
        )
        assert body.virtual_expression is None


class TestTableRelationshipSchemaValidation:
    """表关系 Schema 验证逻辑测试。"""

    def test_invalid_join_type_raises(self) -> None:
        """测试非法连接类型。"""
        from pydantic import ValidationError

        from datapilot_semantic.models.schemas import TableRelationshipCreate

        with pytest.raises(ValidationError):
            TableRelationshipCreate(
                semantic_model_id=str(uuid4()),
                left_table_id=str(uuid4()),
                right_table_id=str(uuid4()),
                join_type="cross",
                join_condition="a.id = b.id",
            )


class TestPaginatedResponse:
    """分页响应测试。"""

    def test_create_with_zero_total(self) -> None:
        """测试空数据分页。"""
        from datapilot_semantic.models.schemas import PaginatedResponse

        resp = PaginatedResponse.create(data=[], total=0, page=1, page_size=20)
        assert resp.pagination.total == 0
        assert resp.pagination.total_pages == 0
        assert resp.data == []

    def test_create_with_exact_pages(self) -> None:
        """测试整除分页。"""
        from datapilot_semantic.models.schemas import PaginatedResponse

        resp = PaginatedResponse.create(
            data=[{"id": "1"}] * 20,
            total=40,
            page=1,
            page_size=20,
        )
        assert resp.pagination.total_pages == 2

    def test_create_with_remainder(self) -> None:
        """测试有余数分页。"""
        from datapilot_semantic.models.schemas import PaginatedResponse

        resp = PaginatedResponse.create(
            data=[{"id": "1"}] * 18,
            total=58,
            page=3,
            page_size=20,
        )
        assert resp.pagination.total_pages == 3  # ceil(58/20) = 3


class TestNotFoundError:
    """NotFoundError 测试。"""

    def test_not_found_with_id(self) -> None:
        """测试带 ID 的 404 错误。"""
        err = NotFoundError(resource="语义模型", resource_id="123")
        assert err.status_code == 404
        assert err.error_code == "RESOURCE_NOT_FOUND"
        assert "123" in err.message

    def test_not_found_without_id(self) -> None:
        """测试不带 ID 的 404 错误。"""
        err = NotFoundError(resource="语义模型")
        assert "不存在" in err.message
