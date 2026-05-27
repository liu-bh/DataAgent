"""认证相关 Pydantic Schema。"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class LoginRequest(BaseModel):
    """登录请求。"""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token 响应。"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # 秒


class RefreshRequest(BaseModel):
    """刷新 Token 请求。"""

    refresh_token: str


class UserResponse(BaseModel):
    """用户信息响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
