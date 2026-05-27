"""授权数据模型。

定义 license.json 的 Pydantic 数据模型，包含产品授权的全部字段。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LicenseData(BaseModel):
    """产品授权数据模型。

    Attributes:
        product: 产品名称
        licensee: 被授权方名称
        license_key: 授权唯一标识
        issued_at: 授权签发时间 (ISO 8601)
        expires_at: 授权过期时间 (ISO 8601)
        allowed_ips: IP 白名单列表，支持 CIDR 格式
        max_concurrent_users: 最大并发用户数
        features: 已授权功能列表
        signature: HMAC-SHA256 签名（hex 编码）
    """

    product: str = Field(..., min_length=1, description="产品名称")
    licensee: str = Field(..., min_length=1, description="被授权方名称")
    license_key: str = Field(..., min_length=1, description="授权唯一标识")
    issued_at: datetime = Field(..., description="授权签发时间")
    expires_at: datetime = Field(..., description="授权过期时间")
    allowed_ips: list[str] = Field(default_factory=list, description="IP 白名单（支持 CIDR）")
    max_concurrent_users: int = Field(default=10, ge=1, description="最大并发用户数")
    features: list[str] = Field(default_factory=list, description="已授权功能列表")
    signature: str = Field(..., min_length=1, description="HMAC-SHA256 签名")

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    @property
    def is_expired(self) -> bool:
        """检查授权是否已过期。"""
        return datetime.utcnow() > self.expires_at

    def payload_for_signing(self) -> dict:
        """返回用于签名字段字典（不含 signature 本身）。"""
        return self.model_dump(exclude={"signature"}, mode="json")
