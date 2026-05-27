"""SQLAlchemy 模型单元测试。

测试语义层所有 ORM 模型的创建、字段映射和默认值。
不需要真实数据库连接，仅测试模型定义和实例化。
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from datapilot_semantic.models import (
    Dimension,
    Metric,
    MetricDimension,
    SemanticModel,
    SourceTable,
    TableRelationship,
)


class TestSemanticModel:
    """SemanticModel 模型测试。"""

    def test_create_minimal(self) -> None:
        """测试最小化创建语义模型。"""
        model = SemanticModel(
            name="电商指标体系",
            domain="电商",
            data_source_ids=[],
        )
        assert model.name == "电商指标体系"
        assert model.domain == "电商"
        assert model.data_source_ids == []
        assert model.description is None
        assert model.deleted_at is None
        assert model.id is not None
        assert model.tenant_id is not None
        assert isinstance(model.created_at, datetime)
        assert isinstance(model.updated_at, datetime)

    def test_create_with_all_fields(self) -> None:
        """测试完整字段创建语义模型。"""
        ds_ids = [str(uuid4()), str(uuid4())]
        model = SemanticModel(
            name="财务报表",
            description="财务域指标和维度",
            domain="财务",
            data_source_ids=ds_ids,
        )
        assert model.description == "财务域指标和维度"
        assert model.data_source_ids == ds_ids

    def test_valid_domains(self) -> None:
        """测试允许的业务域值。"""
        for domain in ("电商", "运营", "财务", "通用"):
            model = SemanticModel(name=f"测试{domain}", domain=domain)
            assert model.domain == domain

    def test_table_name(self) -> None:
        """验证表名。"""
        assert SemanticModel.__tablename__ == "semantic_models"


class TestMetric:
    """Metric 模型测试。"""

    def test_create_minimal(self) -> None:
        """测试最小化创建指标。"""
        metric = Metric(
            semantic_model_id=str(uuid4()),
            name="GMV",
            calculation="SUM(order_amount)",
        )
        assert metric.name == "GMV"
        assert metric.calculation == "SUM(order_amount)"
        assert metric.version == 1
        assert metric.tags == []
        assert metric.unit is None
        assert metric.parent_metric_id is None
        assert metric.embedding is None
        assert metric.deleted_at is None

    def test_create_with_all_fields(self) -> None:
        """测试完整字段创建指标。"""
        sm_id = str(uuid4())
        parent_id = str(uuid4())
        metric = Metric(
            semantic_model_id=sm_id,
            name="利润率",
            description="净利润 / 营收",
            calculation="profit / revenue",
            unit="率",
            parent_metric_id=parent_id,
            tags=["财务", "核心"],
        )
        assert metric.version == 1
        assert metric.parent_metric_id == parent_id
        assert metric.tags == ["财务", "核心"]

    def test_version_default(self) -> None:
        """测试版本号默认值为 1。"""
        metric = Metric(
            semantic_model_id=str(uuid4()),
            name="测试",
            calculation="1",
        )
        assert metric.version == 1

    def test_table_name(self) -> None:
        """验证表名。"""
        assert Metric.__tablename__ == "metrics"


class TestDimension:
    """Dimension 模型测试。"""

    def test_create_minimal(self) -> None:
        """测试最小化创建维度。"""
        dimension = Dimension(
            semantic_model_id=str(uuid4()),
            name="地区",
            column_name="region",
        )
        assert dimension.name == "地区"
        assert dimension.column_name == "region"
        assert dimension.synonyms == []
        assert dimension.is_virtual is False
        assert dimension.virtual_expression is None
        assert dimension.hierarchy is None
        assert dimension.embedding is None
        assert dimension.deleted_at is None

    def test_create_with_synonyms(self) -> None:
        """测试创建带同义词的维度。"""
        dimension = Dimension(
            semantic_model_id=str(uuid4()),
            name="地区",
            synonyms=["区域", "大区", "省份"],
        )
        assert dimension.synonyms == ["区域", "大区", "省份"]

    def test_create_virtual_dimension(self) -> None:
        """测试创建虚拟维度。"""
        dimension = Dimension(
            semantic_model_id=str(uuid4()),
            name="金额区间",
            is_virtual=True,
            virtual_expression="CASE WHEN amount > 1000 THEN '高' ELSE '低' END",
        )
        assert dimension.is_virtual is True
        assert "CASE" in dimension.virtual_expression

    def test_table_name(self) -> None:
        """验证表名。"""
        assert Dimension.__tablename__ == "dimensions"


class TestMetricDimension:
    """MetricDimension 关联模型测试。"""

    def test_create(self) -> None:
        """测试创建指标-维度关联。"""
        md = MetricDimension(
            metric_id=str(uuid4()),
            dimension_id=str(uuid4()),
        )
        assert md.metric_id is not None
        assert md.dimension_id is not None

    def test_table_name(self) -> None:
        """验证表名。"""
        assert MetricDimension.__tablename__ == "metric_dimensions"


class TestTableRelationship:
    """TableRelationship 模型测试。"""

    def test_create(self) -> None:
        """测试创建表关系。"""
        tr = TableRelationship(
            semantic_model_id=str(uuid4()),
            left_table_id=str(uuid4()),
            right_table_id=str(uuid4()),
            join_type="left",
            join_condition="orders.user_id = users.id",
        )
        assert tr.join_type == "left"
        assert tr.join_condition == "orders.user_id = users.id"

    def test_valid_join_types(self) -> None:
        """测试允许的连接类型。"""
        for jt in ("inner", "left", "right", "full"):
            tr = TableRelationship(
                semantic_model_id=str(uuid4()),
                left_table_id=str(uuid4()),
                right_table_id=str(uuid4()),
                join_type=jt,
                join_condition="a.id = b.id",
            )
            assert tr.join_type == jt

    def test_table_name(self) -> None:
        """验证表名。"""
        assert TableRelationship.__tablename__ == "table_relationships"


class TestSourceTable:
    """SourceTable 模型测试。"""

    def test_create_minimal(self) -> None:
        """测试最小化创建源表。"""
        st = SourceTable(
            data_source_id=str(uuid4()),
            schema_name="public",
            table_name="orders",
        )
        assert st.schema_name == "public"
        assert st.table_name == "orders"
        assert st.columns is None
        assert st.row_count is None
        assert st.embedding is None
        assert st.last_synced_at is None
        assert st.deleted_at is None

    def test_create_with_columns(self) -> None:
        """测试创建带列定义的源表。"""
        cols = [
            {"name": "id", "type": "BIGINT", "is_primary_key": True},
            {"name": "amount", "type": "DECIMAL(18,4)", "is_primary_key": False},
        ]
        st = SourceTable(
            data_source_id=str(uuid4()),
            schema_name="public",
            table_name="orders",
            columns=cols,
            row_count=100000,
            description="订单表",
        )
        assert st.columns == cols
        assert st.row_count == 100000

    def test_table_name(self) -> None:
        """验证表名。"""
        assert SourceTable.__tablename__ == "source_tables"
