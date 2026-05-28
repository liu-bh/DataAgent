"""Pydantic Schema 定义。

提供语义层 API 的请求/响应模型。
"""

from __future__ import annotations

import math
from datetime import datetime  # noqa: TC003 — Pydantic 需要 datetime 运行时可用
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# 通用分页响应
# ---------------------------------------------------------------------------

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """分页元信息。"""

    page: int = Field(description="当前页码（从 1 开始）")
    page_size: int = Field(description="每页条数")
    total: int = Field(description="总条数")
    total_pages: int = Field(description="总页数")


class PaginatedResponse(BaseModel, Generic[T]):
    """通用分页响应。"""

    data: list[T] = Field(default_factory=list, description="数据列表")
    pagination: PaginationMeta = Field(description="分页元信息")

    @staticmethod
    def create(data: list[T], total: int, page: int, page_size: int) -> PaginatedResponse[T]:
        """根据数据创建分页响应。

        Args:
            data: 当前页的数据列表。
            total: 总条数。
            page: 当前页码。
            page_size: 每页条数。

        Returns:
            分页响应实例。
        """
        total_pages = math.ceil(total / page_size) if page_size > 0 else 0
        return PaginatedResponse(
            data=data,
            pagination=PaginationMeta(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
            ),
        )


# ---------------------------------------------------------------------------
# SemanticModel
# ---------------------------------------------------------------------------


class SemanticModelCreate(BaseModel):
    """创建语义模型请求。"""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., min_length=1, max_length=100, description="业务语义视图名称")
    description: str | None = Field(None, description="视图描述")
    domain: str = Field(..., description="业务域（电商/运营/财务/通用）")
    data_source_ids: list[str] = Field(default_factory=list, description="关联的数据源 ID 数组")

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """校验业务域枚举值。"""
        allowed = ("电商", "运营", "财务", "通用")
        if v not in allowed:
            raise ValueError(f"domain 必须为 {allowed} 之一，收到: {v}")
        return v


class SemanticModelUpdate(BaseModel):
    """更新语义模型请求。"""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, min_length=1, max_length=100, description="业务语义视图名称")
    description: str | None = Field(None, description="视图描述")
    domain: str | None = Field(None, description="业务域（电商/运营/财务/通用）")
    data_source_ids: list[str] | None = Field(None, description="关联的数据源 ID 数组")

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str | None) -> str | None:
        """校验业务域枚举值。"""
        if v is not None:
            allowed = ("电商", "运营", "财务", "通用")
            if v not in allowed:
                raise ValueError(f"domain 必须为 {allowed} 之一，收到: {v}")
        return v


class SemanticModelResponse(BaseModel):
    """语义模型响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="语义模型 ID")
    tenant_id: str = Field(description="租户 ID")
    name: str = Field(description="业务语义视图名称")
    description: str | None = Field(None, description="视图描述")
    domain: str = Field(description="业务域")
    data_source_ids: list[str] = Field(description="关联的数据源 ID 数组")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
    # 关联信息（详情接口会填充）
    metrics: list[MetricResponse] = Field(default_factory=list, description="关联的指标")
    dimensions: list[DimensionResponse] = Field(default_factory=list, description="关联的维度")


# ---------------------------------------------------------------------------
# Metric
# ---------------------------------------------------------------------------


class MetricCreate(BaseModel):
    """创建指标请求。"""

    model_config = ConfigDict(from_attributes=True)

    semantic_model_id: str = Field(..., description="所属语义模型 ID")
    name: str = Field(..., min_length=1, max_length=100, description="指标名称")
    description: str | None = Field(None, description="指标描述")
    calculation: str = Field(..., min_length=1, description="计算表达式")
    unit: str | None = Field(None, max_length=20, description="单位：元/个/率")
    parent_metric_id: str | None = Field(None, description="父指标 ID（嵌套引用）")
    tags: list[str] = Field(default_factory=list, description="标签数组")


class MetricUpdate(BaseModel):
    """更新指标请求。更新时会自动创建新版本（version+1）。"""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, min_length=1, max_length=100, description="指标名称")
    description: str | None = Field(None, description="指标描述")
    calculation: str | None = Field(None, min_length=1, description="计算表达式")
    unit: str | None = Field(None, max_length=20, description="单位：元/个/率")
    parent_metric_id: str | None = Field(None, description="父指标 ID")
    tags: list[str] | None = Field(None, description="标签数组")


class MetricResponse(BaseModel):
    """指标响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="指标 ID")
    tenant_id: str = Field(description="租户 ID")
    semantic_model_id: str = Field(description="所属语义模型 ID")
    name: str = Field(description="指标名称")
    description: str | None = Field(None, description="指标描述")
    calculation: str = Field(description="计算表达式")
    unit: str | None = Field(None, description="单位")
    version: int = Field(description="当前版本号")
    effective_time: datetime | None = Field(None, description="版本生效时间")
    parent_metric_id: str | None = Field(None, description="父指标 ID")
    tags: list[str] = Field(description="标签数组")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


# ---------------------------------------------------------------------------
# Dimension
# ---------------------------------------------------------------------------


class DimensionCreate(BaseModel):
    """创建维度请求。"""

    model_config = ConfigDict(from_attributes=True)

    semantic_model_id: str = Field(..., description="所属语义模型 ID")
    name: str = Field(..., min_length=1, max_length=100, description="维度名称")
    column_name: str | None = Field(None, max_length=200, description="对应物理列名")
    table_id: str | None = Field(None, description="所属源表 ID")
    synonyms: list[str] = Field(default_factory=list, description="同义词数组")
    hierarchy: dict[str, Any] | None = Field(None, description="层级定义")
    is_virtual: bool = Field(default=False, description="是否虚拟维度")
    virtual_expression: str | None = Field(None, description="虚拟维度表达式")

    @model_validator(mode="after")
    def validate_virtual_expression(self) -> DimensionCreate:
        """虚拟维度必须有表达式。"""
        if self.is_virtual and not self.virtual_expression:
            raise ValueError("虚拟维度必须提供 virtual_expression")
        return self


class DimensionUpdate(BaseModel):
    """更新维度请求。"""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, min_length=1, max_length=100, description="维度名称")
    column_name: str | None = Field(None, max_length=200, description="对应物理列名")
    table_id: str | None = Field(None, description="所属源表 ID")
    synonyms: list[str] | None = Field(None, description="同义词数组")
    hierarchy: dict[str, Any] | None = Field(None, description="层级定义")
    is_virtual: bool | None = Field(None, description="是否虚拟维度")
    virtual_expression: str | None = Field(None, description="虚拟维度表达式")


class DimensionResponse(BaseModel):
    """维度响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="维度 ID")
    tenant_id: str = Field(description="租户 ID")
    semantic_model_id: str = Field(description="所属语义模型 ID")
    name: str = Field(description="维度名称")
    column_name: str | None = Field(None, description="对应物理列名")
    table_id: str | None = Field(None, description="所属源表 ID")
    synonyms: list[str] = Field(description="同义词数组")
    hierarchy: dict[str, Any] | None = Field(None, description="层级定义")
    is_virtual: bool = Field(description="是否虚拟维度")
    virtual_expression: str | None = Field(None, description="虚拟维度表达式")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


# ---------------------------------------------------------------------------
# TableRelationship
# ---------------------------------------------------------------------------


class TableRelationshipCreate(BaseModel):
    """创建表关系请求。"""

    model_config = ConfigDict(from_attributes=True)

    semantic_model_id: str = Field(..., description="所属语义模型 ID")
    left_table_id: str = Field(..., description="左表 ID")
    right_table_id: str = Field(..., description="右表 ID")
    join_type: str = Field(..., description="连接类型：inner/left/right/full")
    join_condition: str = Field(..., min_length=1, description="连接条件")

    @field_validator("join_type")
    @classmethod
    def validate_join_type(cls, v: str) -> str:
        """校验连接类型枚举值。"""
        allowed = ("inner", "left", "right", "full")
        if v not in allowed:
            raise ValueError(f"join_type 必须为 {allowed} 之一，收到: {v}")
        return v


class TableRelationshipResponse(BaseModel):
    """表关系响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="关系 ID")
    tenant_id: str = Field(description="租户 ID")
    semantic_model_id: str = Field(description="所属语义模型 ID")
    left_table_id: str = Field(description="左表 ID")
    right_table_id: str = Field(description="右表 ID")
    join_type: str = Field(description="连接类型")
    join_condition: str = Field(description="连接条件")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
