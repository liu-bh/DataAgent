"""Prometheus 监控指标。

提供查询延迟、连接池使用率、健康状态等指标的采集和暴露。
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# 连接池
# ---------------------------------------------------------------------------

CONNECTOR_POOL_USED = Gauge(
    "queryexec_connector_pool_used",
    "连接池已使用连接数",
    labelnames=["datasource_id", "dialect"],
)

CONNECTOR_POOL_SIZE = Gauge(
    "queryexec_connector_pool_size",
    "连接池总大小",
    labelnames=["datasource_id", "dialect"],
)

# ---------------------------------------------------------------------------
# 查询延迟
# ---------------------------------------------------------------------------

QUERY_LATENCY = Histogram(
    "queryexec_query_latency_seconds",
    "查询延迟（秒）",
    labelnames=["datasource_id", "dialect"],
)

# ---------------------------------------------------------------------------
# 查询计数
# ---------------------------------------------------------------------------

QUERY_TOTAL = Counter(
    "queryexec_query_total",
    "查询总数",
    labelnames=["datasource_id", "dialect", "status"],
)

QUERY_ERRORS = Counter(
    "queryexec_query_errors_total",
    "查询错误数",
    labelnames=["datasource_id", "dialect", "error_type"],
)

# ---------------------------------------------------------------------------
# 健康状态
# ---------------------------------------------------------------------------

DATASOURCE_HEALTH = Gauge(
    "queryexec_datasource_health",
    "数据源健康状态 (1=健康, 0=不健康)",
    labelnames=["datasource_id"],
)


def record_query_metrics(
    datasource_id: str,
    dialect: str,
    success: bool,
    latency_ms: float,
    error_type: str = "",
) -> None:
    """记录查询指标。

    Args:
        datasource_id: 数据源 ID。
        dialect: 数据库方言。
        success: 查询是否成功。
        latency_ms: 查询延迟（毫秒）。
        error_type: 错误类型，仅在失败时传递。
    """
    status = "success" if success else "error"
    QUERY_TOTAL.labels(
        datasource_id=datasource_id,
        dialect=dialect,
        status=status,
    ).inc()

    QUERY_LATENCY.labels(
        datasource_id=datasource_id,
        dialect=dialect,
    ).observe(latency_ms / 1000.0)

    if not success and error_type:
        QUERY_ERRORS.labels(
            datasource_id=datasource_id,
            dialect=dialect,
            error_type=error_type,
        ).inc()


def record_health_metrics(
    datasource_id: str,
    dialect: str,
    healthy: bool,
    pool_used: int,
    pool_size: int,
) -> None:
    """记录健康指标。

    Args:
        datasource_id: 数据源 ID。
        dialect: 数据库方言。
        healthy: 是否健康。
        pool_used: 已使用连接数。
        pool_size: 连接池总大小。
    """
    DATASOURCE_HEALTH.labels(datasource_id=datasource_id).set(1 if healthy else 0)
    CONNECTOR_POOL_USED.labels(
        datasource_id=datasource_id, dialect=dialect
    ).set(pool_used)
    CONNECTOR_POOL_SIZE.labels(
        datasource_id=datasource_id, dialect=dialect
    ).set(pool_size)
