"""Auth Service 路由单元测试。"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# --- JWT Service 测试 ---


class TestJWTService:
    """JWT 工具模块测试。"""

    def setup_method(self) -> None:
        """每个测试前重置环境变量。"""
        import os

        os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-unit-testing-minimum-32-chars"
        os.environ["JWT_ALGORITHM"] = "HS256"

    def _import_jwt(self):
        """延迟导入 JWT 模块，确保环境变量已设置。"""
        from datapilot_auth.services import jwt

        # 重新加载配置
        import importlib
        from datapilot_auth import config
        importlib.reload(config)

        # 更新 jwt 模块引用
        jwt.settings = config.settings
        return jwt

    def test_create_access_token(self) -> None:
        """测试创建 access token。"""
        jwt = self._import_jwt()
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        token = jwt.create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            role="admin",
        )

        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self) -> None:
        """测试创建 refresh token。"""
        jwt = self._import_jwt()
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        token = jwt.create_refresh_token(
            user_id=user_id,
            tenant_id=tenant_id,
        )

        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_token_success(self) -> None:
        """测试成功解码 token。"""
        jwt = self._import_jwt()
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        token = jwt.create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            role="analyst",
        )

        payload = jwt.decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["tenant_id"] == str(tenant_id)
        assert payload["role"] == "analyst"
        assert payload["type"] == "access"
        assert "jti" in payload

    def test_decode_token_expired(self) -> None:
        """测试解码过期 token 抛出异常。"""
        jwt = self._import_jwt()
        from datetime import timedelta

        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        token = jwt.create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            role="viewer",
            expires_delta=timedelta(seconds=-1),  # 已过期
        )

        from datapilot_auth.exceptions import TokenExpiredError

        with pytest.raises(TokenExpiredError):
            jwt.decode_token(token)

    def test_decode_token_invalid(self) -> None:
        """测试解码无效 token 抛出异常。"""
        jwt = self._import_jwt()

        from datapilot_auth.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError):
            jwt.decode_token("invalid-token-string")

    def test_access_token_type(self) -> None:
        """测试 access token 的 type 字段。"""
        jwt = self._import_jwt()
        token = jwt.create_access_token(
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            role="admin",
        )
        payload = jwt.decode_token(token)
        assert payload["type"] == "access"

    def test_refresh_token_type(self) -> None:
        """测试 refresh token 的 type 字段。"""
        jwt = self._import_jwt()
        token = jwt.create_refresh_token(
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
        )
        payload = jwt.decode_token(token)
        assert payload["type"] == "refresh"

    def test_token_contains_jti(self) -> None:
        """测试 token 包含唯一的 jti。"""
        jwt = self._import_jwt()
        token1 = jwt.create_access_token(
            user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), role="admin"
        )
        token2 = jwt.create_access_token(
            user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), role="admin"
        )

        payload1 = jwt.decode_token(token1)
        payload2 = jwt.decode_token(token2)
        assert payload1["jti"] != payload2["jti"]


# --- Schema 测试 ---


class TestAuthSchemas:
    """认证 Schema 测试。"""

    def test_login_request_valid(self) -> None:
        """测试 LoginRequest 正确解析。"""
        from datapilot_auth.schemas.auth import LoginRequest

        data = {"email": "test@example.com", "password": "secret123"}
        req = LoginRequest.model_validate(data)
        assert req.email == "test@example.com"
        assert req.password == "secret123"

    def test_login_request_invalid_email(self) -> None:
        """测试 LoginRequest 邮箱格式校验。"""
        from datapilot_auth.schemas.auth import LoginRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LoginRequest.model_validate({"email": "not-an-email", "password": "secret"})

    def test_token_response(self) -> None:
        """测试 TokenResponse 序列化。"""
        from datapilot_auth.schemas.auth import TokenResponse

        resp = TokenResponse(
            access_token="test-access-token",
            refresh_token="test-refresh-token",
            expires_in=1800,
        )
        data = resp.model_dump()
        assert data["access_token"] == "test-access-token"
        assert data["refresh_token"] == "test-refresh-token"
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 1800

    def test_user_response_from_attributes(self) -> None:
        """测试 UserResponse from_attributes 配置。"""
        from datapilot_auth.schemas.auth import UserResponse

        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        # 模拟 SQLAlchemy 对象
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.tenant_id = tenant_id
        mock_user.email = "test@example.com"
        mock_user.display_name = "Test User"
        mock_user.role = "admin"
        mock_user.is_active = True
        mock_user.created_at = "2026-05-27T00:00:00+08:00"

        resp = UserResponse.model_validate(mock_user, from_attributes=True)
        assert resp.id == user_id
        assert resp.email == "test@example.com"
        assert resp.role == "admin"


# --- Exception 测试 ---


class TestAuthExceptions:
    """认证异常类测试。"""

    def test_authentication_error(self) -> None:
        """测试 AuthenticationError。"""
        from datapilot_auth.exceptions import AuthenticationError

        exc = AuthenticationError("邮箱或密码错误")
        assert exc.status_code == 401
        assert exc.error_code == "AUTHENTICATION_FAILED"
        assert exc.message == "邮箱或密码错误"

    def test_token_expired_error(self) -> None:
        """测试 TokenExpiredError。"""
        from datapilot_auth.exceptions import TokenExpiredError

        exc = TokenExpiredError()
        assert exc.status_code == 401
        assert exc.error_code == "TOKEN_EXPIRED"

    def test_forbidden_error(self) -> None:
        """测试 ForbiddenError。"""
        from datapilot_auth.exceptions import ForbiddenError

        exc = ForbiddenError("无权访问")
        assert exc.status_code == 403
        assert exc.error_code == "FORBIDDEN"

    def test_not_found_error(self) -> None:
        """测试 NotFoundError。"""
        from datapilot_auth.exceptions import NotFoundError

        exc = NotFoundError("用户")
        assert exc.status_code == 404
        assert "用户" in exc.message

    def test_app_error_default(self) -> None:
        """测试 AppError 默认值。"""
        from datapilot_auth.exceptions import AppError

        exc = AppError("未知错误")
        assert exc.status_code == 400
        assert exc.error_code == "INTERNAL_ERROR"
