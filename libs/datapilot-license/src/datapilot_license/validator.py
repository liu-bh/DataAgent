"""授权校验器。

LicenseValidator 负责加载 license.json 并提供全面的授权校验：
- 签名完整性校验
- 有效期校验
- IP 白名单校验（支持 CIDR）
- 功能许可校验
- 并发用户数校验
"""

from __future__ import annotations

import ipaddress
from datetime import UTC, datetime
from pathlib import Path

from .crypto import verify_signature
from .license import LicenseData


class LicenseError(Exception):
    """授权相关异常基类。

    Attributes:
        code: 错误码，参见 security-standards.md 中的授权错误码定义。
        message: 人类可读的错误描述。
        status: HTTP 状态码。
    """

    def __init__(self, code: str, message: str, status: int = 403) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


class LicenseInvalidError(LicenseError):
    """授权文件不存在或签名校验失败。"""

    def __init__(self, message: str = "授权文件无效或签名校验失败") -> None:
        super().__init__(code="LICENSE_INVALID", message=message, status=403)


class LicenseExpiredError(LicenseError):
    """授权已过期。"""

    def __init__(self, message: str = "授权已过期") -> None:
        super().__init__(code="LICENSE_EXPIRED", message=message, status=403)


class LicenseIpDeniedError(LicenseError):
    """请求 IP 不在白名单内。"""

    def __init__(self, client_ip: str) -> None:
        super().__init__(
            code="LICENSE_IP_DENIED",
            message=f"请求 IP {client_ip} 不在授权白名单内",
            status=403,
        )


class LicenseFeatureDisabledError(LicenseError):
    """请求的功能未授权。"""

    def __init__(self, feature: str) -> None:
        super().__init__(
            code="LICENSE_FEATURE_DISABLED",
            message=f"功能 {feature} 未授权",
            status=403,
        )


class LicenseUserLimitError(LicenseError):
    """并发用户数超限。"""

    def __init__(self, message: str = "并发用户数已达上限") -> None:
        super().__init__(code="LICENSE_USER_LIMIT", message=message, status=429)


# 默认签名密钥（生产环境应通过环境变量注入）
DEFAULT_SIGNING_SECRET = "datapilot-default-signing-key"


class LicenseValidator:
    """授权校验器。

    负责加载并校验 license.json 的完整性和各项业务规则。

    Args:
        license_path: 授权文件路径，默认 ./license.json。
        signing_secret: 签名密钥，默认使用 DEFAULT_SIGNING_SECRET。
    """

    def __init__(
        self,
        license_path: str | Path = "./license.json",
        signing_secret: str = DEFAULT_SIGNING_SECRET,
    ) -> None:
        self._license_path = Path(license_path)
        self._signing_secret = signing_secret
        self._license: LicenseData | None = None

    @property
    def license(self) -> LicenseData:
        """获取已加载的授权数据。未加载时抛出 LicenseInvalidError。"""
        if self._license is None:
            raise LicenseInvalidError("授权文件尚未加载")
        return self._license

    def load(self) -> LicenseData:
        """从磁盘加载并解析 license.json。

        Returns:
            解析后的 LicenseData 实例。

        Raises:
            LicenseInvalidError: 文件不存在、解析失败或签名校验失败。
        """
        path = self._license_path
        if not path.exists():
            raise LicenseInvalidError(f"授权文件不存在: {path}")

        try:
            raw = path.read_text(encoding="utf-8")
            import json

            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as e:
            raise LicenseInvalidError(f"授权文件解析失败: {e}") from e

        try:
            self._license = LicenseData.model_validate(data)
        except Exception as e:
            raise LicenseInvalidError(f"授权数据格式错误: {e}") from e

        # 校验签名
        payload = self._license.payload_for_signing()
        if not verify_signature(payload, self._license.signature, self._signing_secret):
            raise LicenseInvalidError("授权签名校验失败，文件可能被篡改")

        return self._license

    def validate(self) -> LicenseData:
        """综合校验授权有效性。

        依次执行：签名校验（load 时已完成）、有效期校验。

        Returns:
            校验通过的 LicenseData 实例。

        Raises:
            LicenseError: 校验失败时抛出具体子类异常。
        """
        self.check_expiry()
        return self.license

    def check_expiry(self) -> None:
        """校验授权是否在有效期内。

        Raises:
            LicenseExpiredError: 授权已过期。
        """
        now = datetime.now(UTC)
        # 确保将 expires_at 转为带时区进行比较
        expires = self.license.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if now > expires:
            raise LicenseExpiredError(f"授权已于 {expires.isoformat()} 过期")

    def check_ip(self, client_ip: str) -> bool:
        """校验客户端 IP 是否在白名单内。

        支持 CIDR 表示法（如 10.0.0.0/8）和精确 IP 匹配。
        白名单为空时表示不限制 IP。

        Args:
            client_ip: 客户端 IP 地址字符串。

        Returns:
            IP 是否在白名单内。

        Raises:
            LicenseIpDeniedError: IP 不在白名单内。
        """
        allowed = self.license.allowed_ips
        if not allowed:
            # 白名单为空，不限制 IP
            return True

        try:
            client_addr = ipaddress.ip_address(client_ip)
        except ValueError:
            raise LicenseIpDeniedError(client_ip) from None

        for cidr in allowed:
            try:
                if client_addr in ipaddress.ip_network(cidr, strict=False):
                    return True
            except ValueError:
                # 跳过无效的 CIDR 条目
                continue

        raise LicenseIpDeniedError(client_ip)

    def check_feature(self, feature: str) -> bool:
        """校验请求的功能是否已授权。

        Args:
            feature: 功能名称标识符。

        Returns:
            功能是否已授权。

        Raises:
            LicenseFeatureDisabledError: 功能未授权。
        """
        if not self.license.features:
            # 功能列表为空，表示所有功能开放
            return True

        if feature in self.license.features:
            return True

        raise LicenseFeatureDisabledError(feature)

    def check_concurrent(self, current_users: int) -> bool:
        """校验当前并发用户数是否超限。

        Args:
            current_users: 当前在线用户数。

        Returns:
            是否在限额内。

        Raises:
            LicenseUserLimitError: 并发数超限。
        """
        if current_users >= self.license.max_concurrent_users:
            raise LicenseUserLimitError(
                f"并发用户数 {current_users} 已达上限 {self.license.max_concurrent_users}"
            )
        return True
