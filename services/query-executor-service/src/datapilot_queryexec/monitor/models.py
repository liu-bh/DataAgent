"""监控数据模型。

定义数据源状态、健康检查结果和熔断状态等核心数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CircuitState(StrEnum):
    """熔断器状态枚举。"""

    CLOSED = "closed"  # 正常
    OPEN = "open"  # 熔断（不可达自动摘除）
    HALF_OPEN = "half_open"  # 半开（探测恢复）


@dataclass
class DataSourceStatus:
    """数据源运行时状态。"""

    datasource_id: str
    name: str
    dialect: str
    host: str = ""
    port: int = 0
    healthy: bool = True
    latency_ms: float = 0.0
    pool_size: int = 0
    pool_used: int = 0
    circuit_state: str = CircuitState.CLOSED
    last_check_at: datetime | None = None
    consecutive_failures: int = 0
    total_queries: int = 0
    error_queries: int = 0
    avg_latency_ms: float = 0.0


class HealthCheckResult(BaseModel):
    """单次健康检查结果。"""

    model_config = ConfigDict(from_attributes=True)

    datasource_id: str
    healthy: bool
    latency_ms: float = 0.0
    error: str = ""
    checked_at: datetime = Field(default_factory=datetime.utcnow)
