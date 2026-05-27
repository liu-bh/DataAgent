"""DataPilot 产品授权模块。

提供授权文件生成、签名校验、有效性验证和 FastAPI 中间件。

公共接口：
- LicenseData: 授权数据模型
- LicenseValidator: 授权校验器
- LicenseMiddleware: FastAPI 授权中间件
- LicenseError 及其子类: 授权异常体系
- sign_license / verify_signature: HMAC-SHA256 签名与验签
"""

from .crypto import sign_license, verify_signature
from .license import LicenseData
from .middleware import LicenseMiddleware
from .validator import (
    LicenseError,
    LicenseExpiredError,
    LicenseFeatureDisabledError,
    LicenseInvalidError,
    LicenseIpDeniedError,
    LicenseUserLimitError,
    LicenseValidator,
)

__all__ = [
    # 数据模型
    "LicenseData",
    # 校验器
    "LicenseValidator",
    # 异常
    "LicenseError",
    "LicenseExpiredError",
    "LicenseFeatureDisabledError",
    "LicenseIpDeniedError",
    "LicenseInvalidError",
    "LicenseUserLimitError",
    # 中间件
    "LicenseMiddleware",
    # 签名
    "sign_license",
    "verify_signature",
]
