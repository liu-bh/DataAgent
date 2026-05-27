"""Session Service 路由单元测试。"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


# --- Schema 测试 ---


class TestSessionSchemas:
    """会话 Schema 测试。"""

    def test_session_create(self) -> None:
        """测试 SessionCreate 正确解析。"""
        from datapilot_session.schemas.session import SessionCreate

        user_id = uuid.uuid4()
        data = {"user_id": user_id, "title": "测试会话"}
        req = SessionCreate.model_validate(data)
        assert req.user_id == user_id
        assert req.title == "测试会话"

    def test_session_create_default_title(self) -> None:
        """测试 SessionCreate 默认标题为 None。"""
        from datapilot_session.schemas.session import SessionCreate

        user_id = uuid.uuid4()
        req = SessionCreate(user_id=user_id)
        assert req.title is None

    def test_session_update(self) -> None:
        """测试 SessionUpdate 正确解析。"""
        from datapilot_session.schemas.session import SessionUpdate

        data = {"title": "更新标题", "is_archived": True}
        req = SessionUpdate.model_validate(data)
        assert req.title == "更新标题"
        assert req.is_archived is True

    def test_session_update_partial(self) -> None:
        """测试 SessionUpdate 部分更新。"""
        from datapilot_session.schemas.session import SessionUpdate

        req = SessionUpdate(title="仅更新标题")
        data = req.model_dump(exclude_unset=True)
        assert data == {"title": "仅更新标题"}

    def test_message_response(self) -> None:
        """测试 MessageResponse 序列化。"""
        from datapilot_session.schemas.session import MessageResponse

        session_id = uuid.uuid4()
        msg_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        mock_msg = MagicMock()
        mock_msg.id = msg_id
        mock_msg.session_id = session_id
        mock_msg.role = "user"
        mock_msg.content = "测试消息"
        mock_msg.sql = "SELECT 1"
        mock_msg.chart_spec = {"type": "bar"}
        mock_msg.created_at = now

        resp = MessageResponse.model_validate(mock_msg, from_attributes=True)
        assert resp.id == msg_id
        assert resp.role == "user"
        assert resp.sql == "SELECT 1"
        assert resp.chart_spec == {"type": "bar"}

    def test_message_response_nullable_fields(self) -> None:
        """测试 MessageResponse 可空字段默认为 None。"""
        from datapilot_session.schemas.session import MessageResponse

        mock_msg = MagicMock()
        mock_msg.id = uuid.uuid4()
        mock_msg.session_id = uuid.uuid4()
        mock_msg.role = "assistant"
        mock_msg.content = "回复内容"
        mock_msg.sql = None
        mock_msg.chart_spec = None
        mock_msg.created_at = datetime.now(timezone.utc)

        resp = MessageResponse.model_validate(mock_msg, from_attributes=True)
        assert resp.sql is None
        assert resp.chart_spec is None

    def test_session_response(self) -> None:
        """测试 SessionResponse 序列化。"""
        from datapilot_session.schemas.session import SessionResponse

        now = datetime.now(timezone.utc)
        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_session.tenant_id = uuid.uuid4()
        mock_session.user_id = uuid.uuid4()
        mock_session.title = "测试会话"
        mock_session.message_count = 5
        mock_session.expires_at = now
        mock_session.is_archived = False
        mock_session.created_at = now
        mock_session.updated_at = now

        resp = SessionResponse.model_validate(mock_session, from_attributes=True)
        assert resp.title == "测试会话"
        assert resp.message_count == 5
        assert resp.is_archived is False

    def test_session_list_response(self) -> None:
        """测试 SessionListResponse 分页结构。"""
        from datapilot_session.schemas.session import SessionListResponse, SessionResponse

        now = datetime.now(timezone.utc)
        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_session.tenant_id = uuid.uuid4()
        mock_session.user_id = uuid.uuid4()
        mock_session.title = "会话1"
        mock_session.message_count = 0
        mock_session.expires_at = None
        mock_session.is_archived = False
        mock_session.created_at = now
        mock_session.updated_at = now

        resp = SessionListResponse(
            data=[SessionResponse.model_validate(mock_session, from_attributes=True)],
            pagination={"page": 1, "page_size": 20, "total": 1, "total_pages": 1},
        )
        assert len(resp.data) == 1
        assert resp.pagination["total"] == 1


# --- Exception 测试 ---


class TestSessionExceptions:
    """会话异常类测试。"""

    def test_not_found_error(self) -> None:
        """测试 NotFoundError。"""
        from datapilot_session.exceptions import NotFoundError

        exc = NotFoundError("会话")
        assert exc.status_code == 404
        assert exc.error_code == "NOT_FOUND"
        assert "会话" in exc.message

    def test_authentication_error(self) -> None:
        """测试 AuthenticationError。"""
        from datapilot_session.exceptions import AuthenticationError

        exc = AuthenticationError("Token 无效")
        assert exc.status_code == 401

    def test_validation_error(self) -> None:
        """测试 ValidationError。"""
        from datapilot_session.exceptions import ValidationError

        exc = ValidationError("参数校验失败")
        assert exc.status_code == 422
        assert exc.error_code == "VALIDATION_ERROR"

    def test_app_error_inheritance(self) -> None:
        """测试所有异常都继承自 AppError。"""
        from datapilot_session.exceptions import (
            AppError,
            AuthenticationError,
            NotFoundError,
            ValidationError,
        )

        assert issubclass(AuthenticationError, AppError)
        assert issubclass(NotFoundError, AppError)
        assert issubclass(ValidationError, AppError)


# --- Model 测试 ---


class TestSessionModels:
    """会话模型测试。"""

    def test_user_role_enum(self) -> None:
        """测试 Session 模型可以正确实例化（结构验证）。"""
        # 仅验证模型定义可以导入和属性存在
        from datapilot_session.models.session import Message, Session

        # 验证表名
        assert Session.__tablename__ == "sessions"
        assert Message.__tablename__ == "messages"

    def test_session_columns(self) -> None:
        """验证 Session 模型字段定义。"""
        from datapilot_session.models.session import Session

        # 检查 __annotations__ 或 mapped_columns 存在
        assert hasattr(Session, "id")
        assert hasattr(Session, "tenant_id")
        assert hasattr(Session, "user_id")
        assert hasattr(Session, "title")
        assert hasattr(Session, "message_count")
        assert hasattr(Session, "expires_at")
        assert hasattr(Session, "is_archived")
        assert hasattr(Session, "created_at")
        assert hasattr(Session, "updated_at")
        assert hasattr(Session, "messages")

    def test_message_columns(self) -> None:
        """验证 Message 模型字段定义。"""
        from datapilot_session.models.session import Message

        assert hasattr(Message, "id")
        assert hasattr(Message, "session_id")
        assert hasattr(Message, "role")
        assert hasattr(Message, "content")
        assert hasattr(Message, "sql")
        assert hasattr(Message, "chart_spec")
        assert hasattr(Message, "created_at")
        assert hasattr(Message, "session")
