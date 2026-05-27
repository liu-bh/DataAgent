"""PromptVersion 模型单元测试。

测试 PromptVersion SQLAlchemy 模型的字段定义和约束。
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from decimal import Decimal
from uuid import uuid4

from datapilot_prompt.models import PromptVersion, VALID_SCENES
from datapilot_common.database import Base


class TestPromptVersionModel:
    """PromptVersion 模型测试。"""

    def test_valid_scenes(self) -> None:
        """验证合法场景值。"""
        assert VALID_SCENES == ("nl2sql", "intent", "explanation", "correction")

    def test_tablename(self) -> None:
        """验证表名。"""
        assert PromptVersion.__tablename__ == "prompt_versions"

    def test_model_inherits_base(self) -> None:
        """验证模型继承自 Base。"""
        assert issubclass(PromptVersion, Base)

    def test_table_constraints(self) -> None:
        """验证表级约束。"""
        table_args = PromptVersion.__table_args__
        # __table_args__ 是一个元组，最后一个元素可能是 dict
        assert isinstance(table_args, tuple)

        # 验证约束存在
        constraint_names = []
        for item in table_args:
            if hasattr(item, "name"):
                constraint_names.append(item.name)

        assert "ck_prompt_versions_scene" in constraint_names
        assert "ck_prompt_versions_score_range" in constraint_names
        assert "ck_prompt_versions_traffic_range" in constraint_names
        assert "uidx_prompt_versions_scene_version" in constraint_names

    def test_create_model_instance(self) -> None:
        """测试创建模型实例。"""
        prompt = PromptVersion(
            id=str(uuid4()),
            scene="nl2sql",
            version=1,
            content="# NL2SQL Prompt\n你是 SQL 助手...",
            is_active=True,
            ab_test_traffic=0.0,
        )

        assert prompt.scene == "nl2sql"
        assert prompt.version == 1
        assert prompt.is_active is True
        assert prompt.ab_test_traffic == 0.0
        assert prompt.effectiveness_score is None

    def test_ab_test_traffic_default(self) -> None:
        """测试 ab_test_traffic 默认值。"""
        prompt = PromptVersion(
            id=str(uuid4()),
            scene="intent",
            version=1,
            content="意图识别 Prompt",
        )
        assert prompt.ab_test_traffic == 0.0

    def test_is_active_default(self) -> None:
        """测试 is_active 默认值。"""
        prompt = PromptVersion(
            id=str(uuid4()),
            scene="explanation",
            version=1,
            content="解释 Prompt",
        )
        assert prompt.is_active is False

    def test_all_scenes_valid(self) -> None:
        """验证所有场景值都能创建实例。"""
        for scene in VALID_SCENES:
            prompt = PromptVersion(
                id=str(uuid4()),
                scene=scene,
                version=1,
                content=f"{scene} Prompt 内容",
            )
            assert prompt.scene == scene

    def test_effectiveness_score_nullable(self) -> None:
        """测试 effectiveness_score 可为 None。"""
        prompt = PromptVersion(
            id=str(uuid4()),
            scene="correction",
            version=1,
            content="校验 Prompt",
            effectiveness_score=None,
        )
        assert prompt.effectiveness_score is None

    def test_effectiveness_score_with_value(self) -> None:
        """测试 effectiveness_score 设置有效值。"""
        prompt = PromptVersion(
            id=str(uuid4()),
            scene="correction",
            version=1,
            content="校验 Prompt",
            effectiveness_score=Decimal("0.8523"),
        )
        assert prompt.effectiveness_score == Decimal("0.8523")
