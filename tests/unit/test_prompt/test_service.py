"""PromptManager CRUD 单元测试。

使用 mock 模拟数据库会话，测试 PromptManager 的核心逻辑。
"""

from __future__ import annotations

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

import pytest

from datapilot_prompt.service import PromptManager
from datapilot_prompt.models import PromptVersion
from datapilot_prompt.schemas import PromptResponse
from datapilot_common.exceptions import NotFoundError, ValidationError


def _make_prompt(
    scene: str = "nl2sql",
    version: int = 1,
    is_active: bool = True,
    ab_test_traffic: float = 0.0,
    prompt_id: UUID | None = None,
    effectiveness_score: Decimal | None = None,
) -> PromptVersion:
    """创建模拟 PromptVersion 对象。"""
    from datetime import datetime, timezone

    pid = prompt_id or uuid4()
    prompt = MagicMock(spec=PromptVersion)
    prompt.id = str(pid)
    prompt.scene = scene
    prompt.version = version
    prompt.content = f"{scene} prompt v{version}"
    prompt.is_active = is_active
    prompt.ab_test_traffic = Decimal(str(ab_test_traffic))
    prompt.effectiveness_score = effectiveness_score
    prompt.created_at = datetime.now(timezone.utc)
    prompt.updated_at = datetime.now(timezone.utc)
    return prompt


@pytest.fixture
def mock_session() -> AsyncMock:
    """创建模拟 AsyncSession。"""
    return AsyncMock()


@pytest.fixture
def manager(mock_session: AsyncMock) -> PromptManager:
    """创建 PromptManager 实例（不传 ABTestingManager）。"""
    return PromptManager(db_session=mock_session)


class TestPromptManagerCreate:
    """create_prompt 测试。"""

    @pytest.mark.asyncio
    async def test_create_first_version_auto_activate(self, manager: PromptManager, mock_session: AsyncMock) -> None:
        """创建场景第一个版本时自动激活。"""
        # mock: 查询最大版本号 → 0
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_session.execute = AsyncMock(return_value=mock_result)

        # mock: 查询总数 → 0（第一个版本）
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        # 第一次调用返回 max_version，第二次返回 count
        mock_session.execute = AsyncMock(
            side_effect=[mock_result, count_result, AsyncMock()]
        )
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await manager.create_prompt(
            scene="nl2sql",
            content="NL2SQL prompt v1",
        )

        # 验证 prompt 被添加到 session
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

        added_prompt = mock_session.add.call_args[0][0]
        assert added_prompt.scene == "nl2sql"
        assert added_prompt.version == 1
        assert added_prompt.is_active is True

    @pytest.mark.asyncio
    async def test_create_subsequent_version_not_active(self, manager: PromptManager, mock_session: AsyncMock) -> None:
        """创建后续版本时不自动激活。"""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 2  # 已有 v1, v2
        count_result = MagicMock()
        count_result.scalar_one.return_value = 2  # 已有 2 个版本

        mock_session.execute = AsyncMock(
            side_effect=[mock_result, count_result, AsyncMock()]
        )
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await manager.create_prompt(
            scene="nl2sql",
            content="NL2SQL prompt v3",
        )

        added_prompt = mock_session.add.call_args[0][0]
        assert added_prompt.version == 3
        assert added_prompt.is_active is False

    @pytest.mark.asyncio
    async def test_create_invalid_scene(self, manager: PromptManager) -> None:
        """创建无效场景时抛出 ValidationError。"""
        with pytest.raises(ValidationError) as exc_info:
            await manager.create_prompt(
                scene="invalid_scene",
                content="test",
            )
        assert "无效的场景标识" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_create_invalid_traffic(self, manager: PromptManager) -> None:
        """创建流量比例超出范围时抛出 ValidationError。"""
        with pytest.raises(ValidationError) as exc_info:
            await manager.create_prompt(
                scene="nl2sql",
                content="test",
                ab_test_traffic=1.5,
            )
        assert "ab_test_traffic" in exc_info.value.message


class TestPromptManagerGetActive:
    """get_active_prompt 测试。"""

    @pytest.mark.asyncio
    async def test_get_active_prompt_success(self, manager: PromptManager, mock_session: AsyncMock) -> None:
        """成功获取激活版本。"""
        prompt = _make_prompt(scene="nl2sql", is_active=True)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = prompt
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await manager.get_active_prompt("nl2sql")

        assert result.scene == "nl2sql"
        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_get_active_prompt_not_found(self, manager: PromptManager, mock_session: AsyncMock) -> None:
        """场景没有激活版本时抛出 NotFoundError。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(NotFoundError):
            await manager.get_active_prompt("nl2sql")


class TestPromptManagerActivate:
    """activate_prompt 测试。"""

    @pytest.mark.asyncio
    async def test_activate_prompt_success(self, manager: PromptManager, mock_session: AsyncMock) -> None:
        """成功激活版本。"""
        target_prompt = _make_prompt(scene="nl2sql", version=2, is_active=False)
        active_prompt = _make_prompt(scene="nl2sql", version=1, is_active=True)

        # 第一次查询：找到目标版本
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = target_prompt

        # 第二次查询：找到当前激活版本
        active_result = MagicMock()
        active_result.scalars.return_value.all.return_value = [active_prompt]

        mock_session.execute = AsyncMock(
            side_effect=[find_result, active_result]
        )
        mock_session.flush = AsyncMock()

        result = await manager.activate_prompt(uuid4())

        assert result.scene == "nl2sql"
        assert result.version == 2
        assert active_prompt.is_active is False
        assert target_prompt.is_active is True

    @pytest.mark.asyncio
    async def test_activate_prompt_not_found(self, manager: PromptManager, mock_session: AsyncMock) -> None:
        """激活不存在的版本时抛出 NotFoundError。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(NotFoundError):
            await manager.activate_prompt(uuid4())


class TestPromptManagerList:
    """list_prompts 测试。"""

    @pytest.mark.asyncio
    async def test_list_prompts_success(self, manager: PromptManager, mock_session: AsyncMock) -> None:
        """成功列出场景版本。"""
        prompts = [
            _make_prompt(scene="nl2sql", version=2),
            _make_prompt(scene="nl2sql", version=1),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = prompts
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await manager.list_prompts("nl2sql")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_prompts_empty(self, manager: PromptManager, mock_session: AsyncMock) -> None:
        """场景无版本时返回空列表。"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await manager.list_prompts("nl2sql")

        assert result == []


class TestPromptManagerGetById:
    """get_prompt_by_id 测试。"""

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, manager: PromptManager, mock_session: AsyncMock) -> None:
        """根据 ID 成功获取版本。"""
        prompt = _make_prompt(scene="nl2sql", version=1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = prompt
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await manager.get_prompt_by_id(prompt.id)

        assert result.scene == "nl2sql"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, manager: PromptManager, mock_session: AsyncMock) -> None:
        """ID 不存在时抛出 NotFoundError。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(NotFoundError):
            await manager.get_prompt_by_id(uuid4())
