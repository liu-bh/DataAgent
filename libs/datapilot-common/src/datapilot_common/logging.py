"""structlog 配置模块。

提供 JSON 格式的结构化日志输出，自动注入 trace_id、tenant_id、user_id。

用法::

    from datapilot_common.logging import setup_logging, get_logger

    setup_logging()
    log = get_logger(__name__)
    log.info("服务启动", service="agent-service")
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def _add_trace_id(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """从 contextvars 或 structlog context 获取 trace_id 注入日志。"""
    trace_id = event_dict.get("trace_id")
    if not trace_id:
        # 尝试从 structlog 的 context 获取（由 middleware 注入）
        ctx = structlog.get_context()
        trace_id = ctx.get("trace_id")
    if trace_id:
        event_dict["trace_id"] = trace_id
    return event_dict


def _inject_defaults(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """注入默认的 tenant_id 和 user_id（默认为 system）。"""
    event_dict.setdefault("tenant_id", "system")
    event_dict.setdefault("user_id", "system")
    return event_dict


def _format_timestamp(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """格式化时间戳为 ISO 8601。"""
    if "timestamp" in event_dict:
        ts = event_dict["timestamp"]
        if hasattr(ts, "isoformat"):
            event_dict["timestamp"] = ts.isoformat()
    return event_dict


def setup_logging(log_level: str = "INFO") -> None:
    """初始化 structlog 配置。

    Args:
        log_level: 日志级别字符串，默认 INFO。
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso"),
        _format_timestamp,
        _add_trace_id,
        _inject_defaults,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """获取绑定了模块名的 structlog logger。

    Args:
        name: 通常传入 __name__。

    Returns:
        structlog.BoundLogger 实例。
    """
    return structlog.get_logger(name)
