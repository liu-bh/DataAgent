"""SemanticModelService 单元测试。

测试语义模型管理服务的 CRUD 业务逻辑。
使用 mock 模拟数据库会话，不依赖真实数据库。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from datapilot_common.exceptions import NotFoundError, ValidationError

# 确保项目源码路径可被导入
import sys
from pathlib import Path

project_root = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "services"
    / "semantic-service"
    / "src"
)
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from datapilot_semantic.models.schemas import (
    SemanticModelCreate,
    SemanticModelResponse,
    SemanticModelUpdate,
)
from datapilot_semantic.models.service import SemanticModelService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def model_id() -> str:
    """生成语义模型 ID。"""
    return str(uuid4())


@pytest.fixture
def tenant_id() -> str:
    """生成租户 ID。"""
    return "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def mock_db() -> AsyncMock:
    """创建 mock 数据库会话。"""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    # refresh 模拟数据库刷新：填充 ORM 对象的 Base/TenantBase 默认字段
    db.refresh = AsyncMock(
        side_effect=lambda obj: _fill_orm_defaults(obj)
    )
    db.add = MagicMock()
    db.execute = AsyncMock()
    return db


def _fill_orm_defaults(obj: object) -> None:
    """为 ORM 对象填充 Base/TenantBase 的默认字段值，模拟 db.refresh 行为。"""
    from uuid import uuid4
    now = datetime.now(timezone.utc)
    if not getattr(obj, "id", None):
        setattr(obj, "id", str(uuid4()))
    if not getattr(obj, "tenant_id", None):
        setattr(obj, "tenant_id", "00000000-0000-0000-0000-000000000001")
    if not getattr(obj, "created_at", None):
        setattr(obj, "created_at", now)
    if not getattr(obj, "updated_at", None):
        setattr(obj, "updated_at", now)


@pytest.fixture
def service() -> SemanticModelService:
    """创建 SemanticModelService 实例。"""
    return SemanticModelService()


@pytest.fixture
def create_data() -> SemanticModelCreate:
    """创建测试用的 SemanticModelCreate 请求体。"""
    return SemanticModelCreate(
        name="电商销售分析",
        description="电商领域的销售数据分析模型",
        domain="电商",
        data_source_ids=["ds-001", "ds-002"],
    )


@pytest.fixture
def mock_semantic_model(
    create_data: SemanticModelCreate, model_id: str, tenant_id: str
) -> MagicMock:
    """创建 mock 的 SemanticModel ORM 对象。"""
    model = MagicMock()
    model.id = model_id
    model.tenant_id = tenant_id
    model.name = create_data.name
    model.description = create_data.description
    model.domain = create_data.domain
    model.data_source_ids = create_data.data_source_ids
    model.deleted_at = None
    model.created_at = datetime.now(timezone.utc)
    model.updated_at = datetime.now(timezone.utc)
    model.metrics = []
    model.dimensions = []
    return model


# ---------------------------------------------------------------------------
# 测试：初始化
# ---------------------------------------------------------------------------


class TestSemanticModelServiceInit:
    """SemanticModelService 初始化测试。"""

    def test_init_without_factory(self) -> None:
        """无 session_factory 初始化。"""
        service = SemanticModelService()
        assert service._session_factory is None

    def test_init_with_factory(self) -> None:
        """带 session_factory 初始化。"""
        factory = MagicMock()
        service = SemanticModelService(session_factory=factory)
        assert service._session_factory is factory


# ---------------------------------------------------------------------------
# 测试：创建语义模型
# ---------------------------------------------------------------------------


class TestCreateModel:
    """create_model 方法测试。"""

    async def test_create_model_success(
        self,
        service: SemanticModelService,
        create_data: SemanticModelCreate,
        mock_db: AsyncMock,
        mock_semantic_model: MagicMock,
    ) -> None:
        """成功创建语义模型。"""
        # 模拟 refresh 赋予 ID，同时填充其他默认字段
        def _refresh_with_id(obj: object) -> None:
            _fill_orm_defaults(obj)
            setattr(obj, "id", mock_semantic_model.id)

        mock_db.refresh.side_effect = _refresh_with_id

        result = await service.create_model(create_data, mock_db)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        assert isinstance(result, SemanticModelResponse)

    async def test_create_model_default_data_source_ids(
        self,
        service: SemanticModelService,
        mock_db: AsyncMock,
    ) -> None:
        """创建语义模型时使用默认空数据源列表。"""
        data = SemanticModelCreate(
            name="测试模型",
            domain="通用",
        )
        # 保留 fixture 中 refresh 的 side_effect，用于填充默认字段

        await service.create_model(data, mock_db)

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.data_source_ids == []


# ---------------------------------------------------------------------------
# 测试：获取语义模型
# ---------------------------------------------------------------------------


class TestGetModel:
    """get_model 方法测试。"""

    async def test_get_model_success(
        self,
        service: SemanticModelService,
        mock_db: AsyncMock,
        mock_semantic_model: MagicMock,
        model_id: str,
    ) -> None:
        """成功获取语义模型详情。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_semantic_model
        mock_db.execute.return_value = mock_result

        result = await service.get_model(model_id, mock_db)

        assert isinstance(result, SemanticModelResponse)
        assert result.name == "电商销售分析"
        assert result.metrics == []
        assert result.dimensions == []

    async def test_get_model_with_metrics_and_dimensions(
        self,
        service: SemanticModelService,
        mock_db: AsyncMock,
        mock_semantic_model: MagicMock,
        model_id: str,
    ) -> None:
        """获取语义模型时包含关联的指标和维度。"""
        mock_metric = MagicMock()
        mock_metric.id = "metric-001"
        mock_metric.name = "销售额"
        mock_metric.tenant_id = "t-001"
        mock_metric.semantic_model_id = model_id
        mock_metric.description = "总销售额"
        mock_metric.calculation = "SUM(amount)"
        mock_metric.unit = "元"
        mock_metric.version = 1
        mock_metric.effective_time = None
        mock_metric.parent_metric_id = None
        mock_metric.tags = []
        mock_metric.created_at = datetime.now(timezone.utc)
        mock_metric.updated_at = datetime.now(timezone.utc)

        mock_dimension = MagicMock()
        mock_dimension.id = "dim-001"
        mock_dimension.name = "商品类别"
        mock_dimension.tenant_id = "t-001"
        mock_dimension.semantic_model_id = model_id
        mock_dimension.column_name = "category"
        mock_dimension.table_id = None
        mock_dimension.synonyms = ["分类", "品类"]
        mock_dimension.hierarchy = None
        mock_dimension.is_virtual = False
        mock_dimension.virtual_expression = None
        mock_dimension.created_at = datetime.now(timezone.utc)
        mock_dimension.updated_at = datetime.now(timezone.utc)

        mock_semantic_model.metrics = [mock_metric]
        mock_semantic_model.dimensions = [mock_dimension]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_semantic_model
        mock_db.execute.return_value = mock_result

        result = await service.get_model(model_id, mock_db)

        assert len(result.metrics) == 1
        assert result.metrics[0].name == "销售额"
        assert len(result.dimensions) == 1
        assert result.dimensions[0].name == "商品类别"

    async def test_get_model_not_found(
        self,
        service: SemanticModelService,
        mock_db: AsyncMock,
        model_id: str,
    ) -> None:
        """语义模型不存在时抛出 NotFoundError。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError, match="语义模型"):
            await service.get_model(model_id, mock_db)


# ---------------------------------------------------------------------------
# 测试：列表查询
# ---------------------------------------------------------------------------


class TestListModels:
    """list_models 方法测试。"""

    async def test_list_models_default(
        self,
        service: SemanticModelService,
        mock_db: AsyncMock,
        mock_semantic_model: MagicMock,
    ) -> None:
        """默认参数列表查询。"""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1
        mock_data_result = MagicMock()
        mock_data_result.scalars.return_value.all.return_value = [mock_semantic_model]

        mock_db.execute.side_effect = [mock_count_result, mock_data_result]

        result = await service.list_models(mock_db)

        assert result.pagination.total == 1
        assert result.pagination.page == 1
        assert result.pagination.page_size == 20
        assert len(result.data) == 1

    async def test_list_models_with_domain_filter(
        self,
        service: SemanticModelService,
        mock_db: AsyncMock,
        mock_semantic_model: MagicMock,
    ) -> None:
        """按业务域过滤列表查询。"""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1
        mock_data_result = MagicMock()
        mock_data_result.scalars.return_value.all.return_value = [mock_semantic_model]

        mock_db.execute.side_effect = [mock_count_result, mock_data_result]

        result = await service.list_models(mock_db, domain="电商")

        assert result.pagination.total == 1
        assert len(result.data) == 1

    async def test_list_models_invalid_domain_raises_error(
        self,
        service: SemanticModelService,
        mock_db: AsyncMock,
    ) -> None:
        """无效的 domain 值抛出 ValidationError。"""
        with pytest.raises(ValidationError, match="domain 必须为"):
            await service.list_models(mock_db, domain="不存在的域")

    async def test_list_models_empty_result(
        self,
        service: SemanticModelService,
        mock_db: AsyncMock,
    ) -> None:
        """空结果列表查询。"""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_data_result = MagicMock()
        mock_data_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [mock_count_result, mock_data_result]

        result = await service.list_models(mock_db)

        assert result.pagination.total == 0
        assert result.pagination.total_pages == 0
        assert len(result.data) == 0


# ---------------------------------------------------------------------------
# 测试：更新语义模型
# ---------------------------------------------------------------------------


class TestUpdateModel:
    """update_model 方法测试。"""

    async def test_update_model_name(
        self,
        service: SemanticModelService,
        mock_db: AsyncMock,
        mock_semantic_model: MagicMock,
        model_id: str,
    ) -> None:
        """更新语义模型名称。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_semantic_model
        mock_db.execute.return_value = mock_result

        update_data = SemanticModelUpdate(name="新名称")
        result = await service.update_model(model_id, update_data, mock_db)

        assert isinstance(result, SemanticModelResponse)
        assert mock_semantic_model.name == "新名称"
        mock_db.commit.assert_awaited_once()

    async def test_update_model_partial_fields(
        self,
        service: SemanticModelService,
        mock_db: AsyncMock,
        mock_semantic_model: MagicMock,
        model_id: str,
    ) -> None:
        """部分字段更新。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_semantic_model
        mock_db.execute.return_value = mock_result

        original_description = mock_semantic_model.description
        update_data = SemanticModelUpdate(name="仅更新名称")
        await service.update_model(model_id, update_data, mock_db)

        # 描述未被更新
        assert mock_semantic_model.description == original_description

    async def test_update_model_not_found(
        self,
        service: SemanticModelService,
        mock_db: AsyncMock,
        model_id: str,
    ) -> None:
        """更新不存在的语义模型时抛出 NotFoundError。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        update_data = SemanticModelUpdate(name="新名称")
        with pytest.raises(NotFoundError, match="语义模型"):
            await service.update_model(model_id, update_data, mock_db)


# ---------------------------------------------------------------------------
# 测试：删除语义模型
# ---------------------------------------------------------------------------


class TestDeleteModel:
    """delete_model 方法测试。"""

    async def test_delete_model_soft_delete(
        self,
        service: SemanticModelService,
        mock_db: AsyncMock,
        mock_semantic_model: MagicMock,
        model_id: str,
    ) -> None:
        """软删除语义模型。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_semantic_model
        mock_db.execute.return_value = mock_result

        await service.delete_model(model_id, mock_db)

        assert mock_semantic_model.deleted_at is not None
        mock_db.commit.assert_awaited_once()

    async def test_delete_model_not_found(
        self,
        service: SemanticModelService,
        mock_db: AsyncMock,
        model_id: str,
    ) -> None:
        """删除不存在的语义模型时抛出 NotFoundError。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError, match="语义模型"):
            await service.delete_model(model_id, mock_db)
