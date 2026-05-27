"""Pydantic Schema 单元测试。

测试语义层所有请求/响应 Schema 的验证和序列化。
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from datapilot_semantic.models.schemas import (
    DimensionCreate,
    DimensionResponse,
    DimensionUpdate,
    MetricCreate,
    MetricResponse,
    MetricUpdate,
    PaginatedResponse,
    PaginationMeta,
    SemanticModelCreate,
    SemanticModelResponse,
    SemanticModelUpdate,
    TableRelationshipCreate,
    TableRelationshipResponse,
)


# ---------------------------------------------------------------------------
# 通用分页
# ---------------------------------------------------------------------------


class TestPaginationMeta:
    """PaginationMeta 测试。"""

    def test_create(self) -> None:
        """测试创建分页元信息。"""
        meta = PaginationMeta(page=1, page_size=20, total=58, total_pages=3)
        assert meta.page == 1
        assert meta.page_size == 20
        assert meta.total == 58
        assert meta.total_pages == 3


class TestPaginatedResponse:
    """PaginatedResponse 测试。"""

    def test_create_method(self) -> None:
        """测试 PaginatedResponse.create 工厂方法。"""
        data = [{"id": "1"}, {"id": "2"}]
        resp = PaginatedResponse.create(
            data=data, total=58, page=1, page_size=20
        )
        assert resp.pagination.total == 58
        assert resp.pagination.total_pages == 3  # ceil(58/20) = 3
        assert len(resp.data) == 2


# ---------------------------------------------------------------------------
# SemanticModelCreate / Update / Response
# ---------------------------------------------------------------------------


class TestSemanticModelCreate:
    """SemanticModelCreate 测试。"""

    def test_valid_create(self) -> None:
        """测试合法创建请求。"""
        body = SemanticModelCreate(
            name="电商指标体系",
            domain="电商",
            description="电商业务指标",
        )
        assert body.name == "电商指标体系"
        assert body.domain == "电商"
        assert body.data_source_ids == []

    def test_with_data_source_ids(self) -> None:
        """测试带数据源 ID 的创建。"""
        ds_ids = [str(uuid4()), str(uuid4())]
        body = SemanticModelCreate(
            name="测试",
            domain="通用",
            data_source_ids=ds_ids,
        )
        assert body.data_source_ids == ds_ids

    def test_invalid_domain(self) -> None:
        """测试非法业务域。"""
        with pytest.raises(ValidationError) as exc_info:
            SemanticModelCreate(name="测试", domain="非法")
        assert "domain" in str(exc_info.value).lower()

    def test_all_valid_domains(self) -> None:
        """测试所有合法业务域。"""
        for domain in ("电商", "运营", "财务", "通用"):
            body = SemanticModelCreate(name="测试", domain=domain)
            assert body.domain == domain


class TestSemanticModelUpdate:
    """SemanticModelUpdate 测试。"""

    def test_partial_update(self) -> None:
        """测试部分更新（仅更新 description）。"""
        body = SemanticModelUpdate(description="新描述")
        dumped = body.model_dump(exclude_unset=True)
        assert "description" in dumped
        assert "name" not in dumped
        assert "domain" not in dumped

    def test_invalid_domain_in_update(self) -> None:
        """测试更新时非法业务域。"""
        with pytest.raises(ValidationError):
            SemanticModelUpdate(domain="非法")


class TestSemanticModelResponse:
    """SemanticModelResponse 测试。"""

    def test_from_attributes(self) -> None:
        """测试 from_attributes 模式。"""
        now = datetime.now(timezone.utc)
        response = SemanticModelResponse(
            id=str(uuid4()),
            tenant_id=str(uuid4()),
            name="测试",
            description="描述",
            domain="电商",
            data_source_ids=[],
            created_at=now,
            updated_at=now,
        )
        assert response.metrics == []
        assert response.dimensions == []


# ---------------------------------------------------------------------------
# MetricCreate / Update / Response
# ---------------------------------------------------------------------------


class TestMetricCreate:
    """MetricCreate 测试。"""

    def test_valid_create(self) -> None:
        """测试合法创建请求。"""
        body = MetricCreate(
            semantic_model_id=str(uuid4()),
            name="GMV",
            calculation="SUM(order_amount)",
            unit="元",
        )
        assert body.name == "GMV"
        assert body.unit == "元"
        assert body.tags == []

    def test_with_parent_and_tags(self) -> None:
        """测试带父指标和标签。"""
        body = MetricCreate(
            semantic_model_id=str(uuid4()),
            name="利润率",
            calculation="profit / revenue",
            parent_metric_id=str(uuid4()),
            tags=["财务", "核心"],
        )
        assert body.parent_metric_id is not None
        assert body.tags == ["财务", "核心"]

    def test_empty_calculation_raises(self) -> None:
        """测试空计算表达式。"""
        with pytest.raises(ValidationError):
            MetricCreate(
                semantic_model_id=str(uuid4()),
                name="测试",
                calculation="",
            )


class TestMetricUpdate:
    """MetricUpdate 测试。"""

    def test_partial_update(self) -> None:
        """测试部分更新。"""
        body = MetricUpdate(calculation="SUM(new_field)")
        dumped = body.model_dump(exclude_unset=True)
        assert "calculation" in dumped
        assert "name" not in dumped

    def test_all_none_fields(self) -> None:
        """测试所有字段都为 None。"""
        body = MetricUpdate()
        dumped = body.model_dump(exclude_unset=True)
        assert dumped == {}


class TestMetricResponse:
    """MetricResponse 测试。"""

    def test_from_attributes(self) -> None:
        """测试创建响应。"""
        now = datetime.now(timezone.utc)
        response = MetricResponse(
            id=str(uuid4()),
            tenant_id=str(uuid4()),
            semantic_model_id=str(uuid4()),
            name="GMV",
            description="商品交易总额",
            calculation="SUM(amount)",
            unit="元",
            version=1,
            effective_time=now,
            parent_metric_id=None,
            tags=["电商"],
            created_at=now,
            updated_at=now,
        )
        assert response.version == 1
        assert response.tags == ["电商"]


# ---------------------------------------------------------------------------
# DimensionCreate / Update / Response
# ---------------------------------------------------------------------------


class TestDimensionCreate:
    """DimensionCreate 测试。"""

    def test_valid_create(self) -> None:
        """测试合法创建请求。"""
        body = DimensionCreate(
            semantic_model_id=str(uuid4()),
            name="地区",
            column_name="region",
        )
        assert body.name == "地区"
        assert body.synonyms == []
        assert body.is_virtual is False

    def test_with_synonyms(self) -> None:
        """测试带同义词。"""
        body = DimensionCreate(
            semantic_model_id=str(uuid4()),
            name="地区",
            synonyms=["区域", "大区"],
        )
        assert body.synonyms == ["区域", "大区"]

    def test_virtual_dimension_requires_expression(self) -> None:
        """测试虚拟维度必须有表达式。"""
        with pytest.raises(ValidationError):
            DimensionCreate(
                semantic_model_id=str(uuid4()),
                name="虚拟维度",
                is_virtual=True,
                virtual_expression=None,
            )

    def test_virtual_dimension_with_expression(self) -> None:
        """测试虚拟维度带表达式可以创建。"""
        body = DimensionCreate(
            semantic_model_id=str(uuid4()),
            name="金额区间",
            is_virtual=True,
            virtual_expression="CASE WHEN amount > 1000 THEN '高' ELSE '低' END",
        )
        assert body.is_virtual is True
        assert "CASE" in body.virtual_expression


class TestDimensionUpdate:
    """DimensionUpdate 测试。"""

    def test_partial_update(self) -> None:
        """测试部分更新。"""
        body = DimensionUpdate(synonyms=["新同义词"])
        dumped = body.model_dump(exclude_unset=True)
        assert "synonyms" in dumped
        assert "name" not in dumped


class TestDimensionResponse:
    """DimensionResponse 测试。"""

    def test_response_fields(self) -> None:
        """测试响应字段。"""
        now = datetime.now(timezone.utc)
        response = DimensionResponse(
            id=str(uuid4()),
            tenant_id=str(uuid4()),
            semantic_model_id=str(uuid4()),
            name="地区",
            column_name="region",
            table_id=str(uuid4()),
            synonyms=["区域"],
            hierarchy={"level": "province"},
            is_virtual=False,
            virtual_expression=None,
            created_at=now,
            updated_at=now,
        )
        assert response.synonyms == ["区域"]
        assert response.hierarchy == {"level": "province"}


# ---------------------------------------------------------------------------
# TableRelationshipCreate / Response
# ---------------------------------------------------------------------------


class TestTableRelationshipCreate:
    """TableRelationshipCreate 测试。"""

    def test_valid_create(self) -> None:
        """测试合法创建请求。"""
        body = TableRelationshipCreate(
            semantic_model_id=str(uuid4()),
            left_table_id=str(uuid4()),
            right_table_id=str(uuid4()),
            join_type="left",
            join_condition="orders.user_id = users.id",
        )
        assert body.join_type == "left"

    def test_invalid_join_type(self) -> None:
        """测试非法连接类型。"""
        with pytest.raises(ValidationError):
            TableRelationshipCreate(
                semantic_model_id=str(uuid4()),
                left_table_id=str(uuid4()),
                right_table_id=str(uuid4()),
                join_type="cross",
                join_condition="a.id = b.id",
            )

    def test_all_valid_join_types(self) -> None:
        """测试所有合法连接类型。"""
        for jt in ("inner", "left", "right", "full"):
            body = TableRelationshipCreate(
                semantic_model_id=str(uuid4()),
                left_table_id=str(uuid4()),
                right_table_id=str(uuid4()),
                join_type=jt,
                join_condition="a.id = b.id",
            )
            assert body.join_type == jt


class TestTableRelationshipResponse:
    """TableRelationshipResponse 测试。"""

    def test_response_fields(self) -> None:
        """测试响应字段。"""
        now = datetime.now(timezone.utc)
        response = TableRelationshipResponse(
            id=str(uuid4()),
            tenant_id=str(uuid4()),
            semantic_model_id=str(uuid4()),
            left_table_id=str(uuid4()),
            right_table_id=str(uuid4()),
            join_type="inner",
            join_condition="a.id = b.id",
            created_at=now,
            updated_at=now,
        )
        assert response.join_type == "inner"
        assert response.join_condition == "a.id = b.id"
