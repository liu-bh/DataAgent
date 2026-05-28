"""请求级别指标收集。

收集各端点的请求计数、错误计数、延迟分布。
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


def _percentile(sorted_values: list[float], p: float) -> float:
    """计算排序列表的百分位数。

    Args:
        sorted_values: 已排序的数值列表。
        p: 百分位数 (0~100)。

    Returns:
        百分位数值，列表为空时返回 0.0。
    """
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    # 最近邻排序法
    k = int(p / 100.0 * (n - 1))
    return sorted_values[k]


@dataclass
class RequestMetrics:
    """请求指标收集器（线程安全简化版）。

    使用线程锁保护内部计数器，支持多线程场景。
    """

    _request_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int), repr=False)
    _error_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int), repr=False)
    _latencies: dict[str, list[float]] = field(
        default_factory=lambda: defaultdict(list), repr=False
    )
    _active_requests: int = 0
    _total_requests: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_request(
        self,
        endpoint: str,
        method: str = "GET",
        status_code: int = 200,
        latency_ms: float = 0.0,
    ) -> None:
        """记录一次请求。

        Args:
            endpoint: 端点路径。
            method: HTTP 方法。
            status_code: 响应状态码。
            latency_ms: 请求耗时（毫秒）。
        """
        key = f"{method.upper()}:{endpoint}"
        is_error = status_code >= 400

        with self._lock:
            self._request_counts[key] += 1
            self._total_requests += 1
            if is_error:
                self._error_counts[key] += 1
            if latency_ms > 0:
                self._latencies[key].append(latency_ms)

    def get_summary(self) -> dict[str, Any]:
        """获取指标摘要。

        返回各端点的请求计数、错误计数、平均延迟、P50/P95/P99 延迟，
        以及全局活跃请求数和总请求数。

        Returns:
            指标摘要字典。
        """
        with self._lock:
            endpoints: dict[str, Any] = {}
            all_keys = set(self._request_counts.keys()) | set(self._latencies.keys())

            for key in sorted(all_keys):
                count = self._request_counts.get(key, 0)
                errors = self._error_counts.get(key, 0)
                latencies = self._latencies.get(key, [])

                info: dict[str, Any] = {
                    "request_count": count,
                    "error_count": errors,
                    "error_rate": round(errors / count, 4) if count > 0 else 0.0,
                }

                if latencies:
                    sorted_lat = sorted(latencies)
                    info["avg_latency_ms"] = round(sum(latencies) / len(latencies), 2)
                    info["min_latency_ms"] = round(min(sorted_lat), 2)
                    info["max_latency_ms"] = round(max(sorted_lat), 2)
                    info["p50_latency_ms"] = round(_percentile(sorted_lat, 50), 2)
                    info["p95_latency_ms"] = round(_percentile(sorted_lat, 95), 2)
                    info["p99_latency_ms"] = round(_percentile(sorted_lat, 99), 2)

                endpoints[key] = info

            return {
                "active_requests": self._active_requests,
                "total_requests": self._total_requests,
                "endpoints": endpoints,
            }

    def increment_active(self) -> None:
        """增加活跃请求计数。"""
        with self._lock:
            self._active_requests += 1

    def decrement_active(self) -> None:
        """减少活跃请求计数。"""
        with self._lock:
            self._active_requests -= 1
