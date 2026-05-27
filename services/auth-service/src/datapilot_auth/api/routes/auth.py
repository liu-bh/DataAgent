"""认证路由：登录、刷新、登出、当前用户。"""

import uuid

from fastapi import APIRouter, Depends, Header
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datapilot_auth.config import settings
from datapilot_auth.database import get_db
from datapilot_auth.exceptions import AuthenticationError, NotFoundError
from datapilot_auth.models.user import User
from datapilot_auth.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from datapilot_auth.services.jwt import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# TODO: Token 黑名单应使用 Redis，后续迁移到 datapilot-common
_token_blacklist: set[str] = set()


async def get_current_user(
    authorization: str = Header(..., description="Bearer {token}"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI 依赖：从 Authorization 头解析当前用户。"""
    if not authorization.startswith("Bearer "):
        raise AuthenticationError("缺少 Bearer Token")

    token = authorization.removeprefix("Bearer ")
    payload = decode_token(token)

    # 校验 Token 类型
    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise AuthenticationError("Token 类型错误")

    # 校验是否已吊销
    jti = payload.get("jti")
    if jti and jti in _token_blacklist:
        raise AuthenticationError("Token 已被吊销")

    # 查询用户
    user_id = uuid.UUID(payload["sub"])
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise AuthenticationError("用户不存在或已禁用")

    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """用户登录，返回 access_token + refresh_token。"""
    stmt = select(User).where(User.email == body.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("邮箱或密码错误")

    if not user.is_active:
        raise AuthenticationError("用户已被禁用")

    if not pwd_context.verify(body.password, user.password_hash):
        raise AuthenticationError("邮箱或密码错误")

    access_token = create_access_token(user.id, user.tenant_id, user.role)
    refresh_token = create_refresh_token(user.id, user.tenant_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """用 refresh_token 换取新的 access_token。"""
    payload = decode_token(body.refresh_token)

    if payload.get("type") != TOKEN_TYPE_REFRESH:
        raise AuthenticationError("Token 类型错误")

    user_id = uuid.UUID(payload["sub"])
    tenant_id = uuid.UUID(payload["tenant_id"])

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise AuthenticationError("用户不存在或已禁用")

    access_token = create_access_token(user.id, user.tenant_id, user.role)
    refresh_token = create_refresh_token(user.id, user.tenant_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout")
async def logout(
    authorization: str = Header(..., description="Bearer {token}"),
) -> dict:
    """登出，吊销当前 Token。"""
    if authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ")
        try:
            payload = decode_token(token)
            jti = payload.get("jti")
            if jti:
                _token_blacklist.add(jti)
        except AuthenticationError:
            pass  # Token 无效时忽略

    return {"message": "登出成功"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """获取当前登录用户信息。"""
    return UserResponse.model_validate(current_user)
