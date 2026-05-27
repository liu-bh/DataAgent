"""Prometheus 指标模块。

提供请求计数和延迟直方图，以及 FastAPI middleware 注册函数。

用法::

    from fastapi import FastAPI
    from datapilot_common.metrics import setup_metrics

    app = FastAPI()
    setup_metrics(app)
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram

# ---------------------------------------------------------------------------
# 指标定义
# ---------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "datapilot_http_requests_total",
    "HTTP 请求总数",
    labelnames=["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "datapilot_http_request_duration_seconds",
    "HTTP 请求延迟（秒）",
    labelnames=["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 10.0],
)

# 不需要追踪健康检查
_SKIP_PATHS: set[str] = {"/health", "/metrics", "/readiness", "/liveness"}


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class _MetricsMiddleware:
    """Prometheus 指标收集中间件。"""

    async def __call__(self, request: Request, call_next: Any) -> Response:
        """拦截请求，记录计数和延迟。"""
        path = request.url.path

        # 跳过不需要追踪的路径
        if path in _SKIP_PATHS:
            return await call_next(request)

        method = request.method
        # 使用路由匹配到的 path pattern（如 /api/v1/items/{item_id}）
        endpoint = request.url.path

        start_time = time.perf_counter()
        response: Response = await call_next(request)
        duration = time.perf_counter() - start_time

        status_code = str(response.status_code)

        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)

        return response


# ---------------------------------------------------------------------------
# 注册函数
# ---------------------------------------------------------------------------


def setup_metrics(app: FastAPI) -> None:
    """将 Prometheus 指标中间件注册到 FastAPI 应用。

    Args:
        app: FastAPI 应用实例。
    """
    app.add_middleware(_MetricsMiddleware)
