"""JWT 工具模块：Token 创建与验证。"""

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from datapilot_auth.config import settings
from datapilot_auth.exceptions import AuthenticationError, TokenExpiredError

# Token 类型常量
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def create_access_token(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """创建访问 Token。

    Args:
        user_id: 用户 ID
        tenant_id: 租户 ID
        role: 用户角色
        expires_delta: 自定义过期时间，默认使用配置值
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "type": TOKEN_TYPE_ACCESS,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),  # Token 唯一标识，用于吊销
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    expires_delta: timedelta | None = None,
) -> str:
    """创建刷新 Token。

    Args:
        user_id: 用户 ID
        tenant_id: 租户 ID
        expires_delta: 自定义过期时间，默认使用配置值
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.refresh_token_expire_days)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "type": TOKEN_TYPE_REFRESH,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """解码并验证 JWT Token。

    Args:
        token: JWT Token 字符串

    Returns:
        Token payload 字典

    Raises:
        TokenExpiredError: Token 已过期
        AuthenticationError: Token 无效
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError()
    except JWTError:
        raise AuthenticationError("无效的 Token")
