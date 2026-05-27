"""FastAPI 授权中间件。

- 服务启动时加载并校验 license.json，无效则拒绝启动。
- 每个请求检查客户端 IP 是否在白名单内（带内存缓存）。
- 未授权请求返回统一的 JSON 错误格式。
"""

from __future__ import annotations

import time
from collections.abc import Callable  # noqa: TC003
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.requests import Request

from .validator import (
    DEFAULT_SIGNING_SECRET,
    LicenseError,
    LicenseIpDeniedError,
    LicenseValidator,
)

# 健康检查路径前缀，这些路径不进行 IP 白名单检查
HEALTH_CHECK_PREFIXES = ("/health", "/metrics", "/ready")


class LicenseMiddleware(BaseHTTPMiddleware):
    """FastAPI 授权中间件。

    在服务启动阶段通过 lifespan 事件加载并校验授权文件，
    在每个请求阶段检查客户端 IP 白名单。

    Args:
        app: ASGI 应用实例。
        license_path: 授权文件路径。
        signing_secret: 签名密钥。
        cache_ttl: IP 白名单检查缓存过期时间（秒），默认 300 秒。
        skip_paths: 跳过 IP 检查的路径前缀列表。
    """

    def __init__(
        self,
        app: Callable,
        license_path: str = "./license.json",
        signing_secret: str = DEFAULT_SIGNING_SECRET,
        cache_ttl: int = 300,
        skip_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._license_path = license_path
        self._signing_secret = signing_secret
        self._cache_ttl = cache_ttl
        self._skip_paths = skip_paths or list(HEALTH_CHECK_PREFIXES)
        self._validator = LicenseValidator(
            license_path=license_path,
            signing_secret=signing_secret,
        )
        # IP 检查缓存：{ip: (allowed: bool, timestamp: float)}
        self._ip_cache: dict[str, tuple[bool, float]] = {}

    def load_license(self) -> None:
        """加载并校验授权文件，在应用启动时调用。

        Raises:
            LicenseError: 授权无效时抛出异常。
        """
        self._validator.load()
        self._validator.validate()

    def _get_client_ip(self, request: Request) -> str:
        """从请求中提取客户端 IP。

        优先读取 X-Forwarded-For / X-Real-IP 头（反向代理场景），
        否则使用 client host。
        """
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # 取第一个 IP（最原始的客户端 IP）
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

        if request.client:
            return request.client.host

        return "unknown"

    def _check_ip_cached(self, client_ip: str) -> bool:
        """带缓存的 IP 白名单检查。"""
        now = time.monotonic()

        # 检查缓存
        cached = self._ip_cache.get(client_ip)
        if cached is not None:
            allowed, ts = cached
            if now - ts < self._cache_ttl:
                return allowed

        # 执行检查并更新缓存
        try:
            self._validator.check_ip(client_ip)
            self._ip_cache[client_ip] = (True, now)
            return True
        except LicenseIpDeniedError:
            self._ip_cache[client_ip] = (False, now)
            return False
        except LicenseError:
            # 授权未加载等其他异常
            return False

    def _should_skip(self, path: str) -> bool:
        """判断请求路径是否应跳过 IP 检查。"""
        return any(path.startswith(prefix) for prefix in self._skip_paths)

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        """处理每个请求，检查 IP 白名单。"""
        path = request.url.path

        # 跳过健康检查等路径
        if self._should_skip(path):
            return await call_next(request)

        # 提取客户端 IP
        client_ip = self._get_client_ip(request)

        # 带缓存的 IP 白名单检查
        if not self._check_ip_cached(client_ip):
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "LICENSE_IP_DENIED",
                        "message": f"请求 IP {client_ip} 不在授权白名单内",
                    },
                },
            )

        return await call_next(request)


def _license_error_response(exc: LicenseError) -> JSONResponse:
    """构造统一的授权错误响应。"""
    return JSONResponse(
        status_code=exc.status,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
            },
        },
    )
