"""DataSourceService 单元测试。

测试数据源管理服务的 CRUD、健康检查、元数据同步等业务逻辑。
使用 mock 模拟数据库会话，不依赖真实数据库。
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

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

from datapilot_semantic.metadata.schemas import (
    DataSourceCreate,
    DataSourceResponse,
    DataSourceUpdate,
    SyncResultResponse,
)
from datapilot_semantic.metadata.service import DataSourceService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def datasource_id() -> UUID:
    """生成数据源 ID。"""
    return uuid4()


@pytest.fixture
def tenant_id() -> UUID:
    """生成租户 ID。"""
    return uuid4()


@pytest.fixture
def mock_db() -> AsyncMock:
    """创建 mock 数据库会话。"""
    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def service() -> DataSourceService:
    """创建 DataSourceService 实例。"""
    return DataSourceService()


@pytest.fixture
def create_data() -> DataSourceCreate:
    """创建测试用的 DataSourceCreate 请求体。"""
    return DataSourceCreate(
        name="测试数据源",
        type="postgresql",
        host="localhost",
        port=5432,
        database="test_db",
        username="admin",
        password="secret123",
        pool_size=5,
        freshness_level="daily",
        freshness_cron="0 0 * * *",
    )


@pytest.fixture
def mock_datasource(create_data: DataSourceCreate, datasource_id: UUID, tenant_id: UUID) -> MagicMock:
    """创建 mock 的 DataSource ORM 对象。"""
    ds = MagicMock()
    ds.id = datasource_id
    ds.tenant_id = tenant_id
    ds.name = create_data.name
    ds.type = create_data.type
    ds.host = create_data.host
    ds.port = create_data.port
    ds.database = create_data.database
    ds.username = create_data.username
    ds.password = "encrypted_password"
    ds.pool_size = create_data.pool_size
    ds.freshness_level = create_data.freshness_level
    ds.freshness_cron = create_data.freshness_cron
    ds.status = "active"
    ds.last_health_check = None
    ds.deleted_at = None
    ds.created_at = datetime.now(timezone.utc)
    ds.updated_at = datetime.now(timezone.utc)
    return ds


# ---------------------------------------------------------------------------
# 测试：初始化
# ---------------------------------------------------------------------------


class TestDataSourceServiceInit:
    """DataSourceService 初始化测试。"""

    def test_init_without_factory(self) -> None:
        """无 session_factory 初始化。"""
        service = DataSourceService()
        assert service._session_factory is None

    def test_init_with_factory(self) -> None:
        """带 session_factory 初始化。"""
        factory = MagicMock()
        service = DataSourceService(session_factory=factory)
        assert service._session_factory is factory


# ---------------------------------------------------------------------------
# 测试：创建数据源
# ---------------------------------------------------------------------------


class TestCreateDataSource:
    """create_datasource 方法测试。"""

    @patch("datapilot_semantic.metadata.service.encrypt_password", return_value="encrypted")
    async def test_create_datasource_success(
        self,
        mock_encrypt: MagicMock,
        service: DataSourceService,
        create_data: DataSourceCreate,
        mock_db: AsyncMock,
        mock_datasource: MagicMock,
    ) -> None:
        """成功创建数据源。"""
        # 模拟 flush 后 refresh 返回带有 ID 的对象
        mock_db.refresh.side_effect = lambda obj: setattr(
            obj, "id", mock_datasource.id
        )

        result = await service.create_datasource(create_data, mock_db)

        # 验证密码被加密
        mock_encrypt.assert_called_once_with(create_data.password)
        # 验证对象被添加到会话
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()
        assert isinstance(result, DataSourceResponse)

    @patch("datapilot_semantic.metadata.service.encrypt_password", return_value="encrypted")
    async def test_create_datasource_default_pool_size(
        self,
        mock_encrypt: MagicMock,
        service: DataSourceService,
        mock_db: AsyncMock,
    ) -> None:
        """创建数据源时使用默认连接池大小。"""
        data = DataSourceCreate(
            name="默认池大小",
            type="mysql",
            host="127.0.0.1",
            port=3306,
            database="mydb",
            username="root",
            password="pwd",
        )
        mock_db.refresh = AsyncMock()

        await service.create_datasource(data, mock_db)
        mock_db.add.assert_called_once()

        # 获取添加的对象并验证默认值
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.pool_size == 5  # 默认值


# ---------------------------------------------------------------------------
# 测试：获取数据源
# ---------------------------------------------------------------------------


class TestGetDataSource:
    """get_datasource 方法测试。"""

    async def test_get_datasource_success(
        self,
        service: DataSourceService,
        mock_db: AsyncMock,
        mock_datasource: MagicMock,
        datasource_id: UUID,
    ) -> None:
        """成功获取数据源详情。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_datasource
        mock_db.execute.return_value = mock_result

        result = await service.get_datasource(datasource_id, mock_db)

        assert isinstance(result, DataSourceResponse)
        mock_db.execute.assert_awaited_once()

    async def test_get_datasource_not_found(
        self,
        service: DataSourceService,
        mock_db: AsyncMock,
        datasource_id: UUID,
    ) -> None:
        """数据源不存在时抛出 NotFoundError。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError, match="数据源"):
            await service.get_datasource(datasource_id, mock_db)


# ---------------------------------------------------------------------------
# 测试：列表查询
# ---------------------------------------------------------------------------


class TestListDataSources:
    """list_datasources 方法测试。"""

    async def test_list_datasources_default(
        self,
        service: DataSourceService,
        mock_db: AsyncMock,
        mock_datasource: MagicMock,
    ) -> None:
        """默认参数列表查询。"""
        # 模拟 count 查询
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1
        # 模拟数据查询
        mock_data_result = MagicMock()
        mock_data_result.scalars.return_value.all.return_value = [mock_datasource]

        mock_db.execute.side_effect = [mock_count_result, mock_data_result]

        result = await service.list_datasources(mock_db)

        assert result.pagination.total == 1
        assert result.pagination.page == 1
        assert result.pagination.page_size == 20
        assert len(result.data) == 1
        assert mock_db.execute.await_count == 2

    async def test_list_datasources_with_type_filter(
        self,
        service: DataSourceService,
        mock_db: AsyncMock,
    ) -> None:
        """按类型过滤列表查询。"""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_data_result = MagicMock()
        mock_data_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [mock_count_result, mock_data_result]

        result = await service.list_datasources(mock_db, type="mysql")

        assert result.pagination.total == 0
        assert len(result.data) == 0


# ---------------------------------------------------------------------------
# 测试：更新数据源
# ---------------------------------------------------------------------------


class TestUpdateDataSource:
    """update_datasource 方法测试。"""

    @patch("datapilot_semantic.metadata.service.encrypt_password", return_value="new_encrypted")
    async def test_update_datasource_name(
        self,
        mock_encrypt: MagicMock,
        service: DataSourceService,
        mock_db: AsyncMock,
        mock_datasource: MagicMock,
        datasource_id: UUID,
    ) -> None:
        """更新数据源名称。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_datasource
        mock_db.execute.return_value = mock_result

        update_data = DataSourceUpdate(name="新名称")
        result = await service.update_datasource(datasource_id, update_data, mock_db)

        assert isinstance(result, DataSourceResponse)
        assert mock_datasource.name == "新名称"
        mock_db.flush.assert_awaited_once()

    @patch("datapilot_semantic.metadata.service.encrypt_password", return_value="new_encrypted")
    async def test_update_datasource_password_encrypted(
        self,
        mock_encrypt: MagicMock,
        service: DataSourceService,
        mock_db: AsyncMock,
        mock_datasource: MagicMock,
        datasource_id: UUID,
    ) -> None:
        """更新密码时应加密。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_datasource
        mock_db.execute.return_value = mock_result

        update_data = DataSourceUpdate(password="new_secret")
        await service.update_datasource(datasource_id, update_data, mock_db)

        # 验证密码被加密
        mock_encrypt.assert_called_once_with("new_secret")
        assert mock_datasource.password == "new_encrypted"

    async def test_update_datasource_not_found(
        self,
        service: DataSourceService,
        mock_db: AsyncMock,
        datasource_id: UUID,
    ) -> None:
        """更新不存在的数据源时抛出 NotFoundError。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        update_data = DataSourceUpdate(name="新名称")
        with pytest.raises(NotFoundError, match="数据源"):
            await service.update_datasource(datasource_id, update_data, mock_db)


# ---------------------------------------------------------------------------
# 测试：删除数据源
# ---------------------------------------------------------------------------


class TestDeleteDataSource:
    """delete_datasource 方法测试。"""

    async def test_delete_datasource_soft_delete(
        self,
        service: DataSourceService,
        mock_db: AsyncMock,
        mock_datasource: MagicMock,
        datasource_id: UUID,
    ) -> None:
        """软删除数据源。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_datasource
        mock_db.execute.return_value = mock_result

        await service.delete_datasource(datasource_id, mock_db)

        # 验证软删除标记
        assert mock_datasource.deleted_at is not None
        assert mock_datasource.status == "disabled"
        mock_db.flush.assert_awaited_once()

    async def test_delete_datasource_not_found(
        self,
        service: DataSourceService,
        mock_db: AsyncMock,
        datasource_id: UUID,
    ) -> None:
        """删除不存在的数据源时抛出 NotFoundError。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError, match="数据源"):
            await service.delete_datasource(datasource_id, mock_db)


# ---------------------------------------------------------------------------
# 测试：健康检查
# ---------------------------------------------------------------------------


class TestGetDatasourceHealth:
    """get_datasource_health 方法测试。"""

    @patch("datapilot_semantic.metadata.service.test_connection", return_value=True)
    async def test_health_check_healthy(
        self,
        mock_test_conn: MagicMock,
        service: DataSourceService,
        mock_db: AsyncMock,
        mock_datasource: MagicMock,
        datasource_id: UUID,
    ) -> None:
        """健康检查 - 健康。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_datasource
        mock_db.execute.return_value = mock_result

        result = await service.get_datasource_health(datasource_id, mock_db)

        assert result.status == "healthy"
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()

    @patch("datapilot_semantic.metadata.service.test_connection", return_value=False)
    async def test_health_check_down(
        self,
        mock_test_conn: MagicMock,
        service: DataSourceService,
        mock_db: AsyncMock,
        mock_datasource: MagicMock,
        datasource_id: UUID,
    ) -> None:
        """健康检查 - 不可达。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_datasource
        mock_db.execute.return_value = mock_result

        result = await service.get_datasource_health(datasource_id, mock_db)

        assert result.status == "down"

    async def test_health_check_api_type(
        self,
        service: DataSourceService,
        mock_db: AsyncMock,
        mock_datasource: MagicMock,
        datasource_id: UUID,
    ) -> None:
        """API 类型数据源跳过连接测试，默认健康。"""
        mock_datasource.type = "api"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_datasource
        mock_db.execute.return_value = mock_result

        result = await service.get_datasource_health(datasource_id, mock_db)

        assert result.status == "healthy"

    async def test_health_check_not_found(
        self,
        service: DataSourceService,
        mock_db: AsyncMock,
        datasource_id: UUID,
    ) -> None:
        """健康检查 - 数据源不存在。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError, match="数据源"):
            await service.get_datasource_health(datasource_id, mock_db)


# ---------------------------------------------------------------------------
# 测试：元数据同步
# ---------------------------------------------------------------------------


class TestSyncDataSource:
    """sync_datasource 方法测试。"""

    @patch("datapilot_semantic.metadata.service.sync_metadata")
    async def test_sync_success(
        self,
        mock_sync: AsyncMock,
        service: DataSourceService,
        mock_db: AsyncMock,
        mock_datasource: MagicMock,
        datasource_id: UUID,
    ) -> None:
        """同步成功。"""
        mock_sync.return_value = SyncResultResponse(
            datasource_id=datasource_id,
            status="success",
            total_tables=5,
            synced_tables=5,
            updated_tables=0,
            new_tables=5,
            message="同步完成",
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_datasource
        mock_db.execute.return_value = mock_result

        result = await service.sync_datasource(datasource_id, mock_db)

        assert result.status == "success"
        assert result.synced_tables == 5
        mock_sync.assert_awaited_once()

    async def test_sync_api_type_raises_error(
        self,
        service: DataSourceService,
        mock_db: AsyncMock,
        mock_datasource: MagicMock,
        datasource_id: UUID,
    ) -> None:
        """API 类型数据源不支持同步，抛出 ValidationError。"""
        mock_datasource.type = "api"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_datasource
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValidationError, match="API 类型的数据源不支持元数据同步"):
            await service.sync_datasource(datasource_id, mock_db)

    async def test_sync_not_found(
        self,
        service: DataSourceService,
        mock_db: AsyncMock,
        datasource_id: UUID,
    ) -> None:
        """同步不存在的数据源时抛出 NotFoundError。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError, match="数据源"):
            await service.sync_datasource(datasource_id, mock_db)
