"""HTTP 请求追踪中间件。

为每个请求生成唯一 ID，记录请求耗时，
注入响应头，输出结构化访问日志。
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

logger = structlog.get_logger(__name__)


class RequestTraceMiddleware(BaseHTTPMiddleware):
    """请求追踪中间件。

    功能：
    1. 为每个请求生成 request_id
    2. 记录请求耗时
    3. 注入 X-Request-ID 响应头
    4. 输出结构化访问日志
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """处理请求并注入追踪信息。

        Args:
            request: 原始请求。
            call_next: 下一个中间件或路由处理器。

        Returns:
            带有追踪头信息的响应。
        """
        request_id = str(uuid.uuid4())[:8]
        start_time = time.perf_counter()

        # 注入 request_id 到请求状态
        request.state.request_id = request_id

        response = await call_next(request)

        latency_ms = (time.perf_counter() - start_time) * 1000

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=round(latency_ms, 2),
            request_id=request_id,
        )

        return response
