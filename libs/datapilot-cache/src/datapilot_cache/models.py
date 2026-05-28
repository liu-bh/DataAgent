"""缓存数据模型定义。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CacheKey:
    """缓存键（不可变，可作为字典键）。"""

    namespace: str
    key: str
    version: str = "v1"

    def __hash__(self) -> int:
        return hash((self.namespace, self.key, self.version))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CacheKey):
            return NotImplemented
        return (
            self.namespace == other.namespace
            and self.key == other.key
            and self.version == other.version
        )

    def __str__(self) -> str:
        return f"{self.namespace}:{self.version}:{self.key}"


@dataclass
class CacheEntry:
    """缓存条目。"""

    key: CacheKey
    value: Any
    created_at: float = field(default_factory=time.time)
    ttl: float = 300.0  # 秒
    hit_count: int = 0
    size_bytes: int = 0
    tags: list[str] = field(default_factory=list)

    @property
    def expires_at(self) -> float:
        """过期时间戳。"""
        return self.created_at + self.ttl

    @property
    def is_expired(self) -> bool:
        """是否已过期。"""
        return time.time() > self.expires_at


@dataclass
class CacheStats:
    """缓存统计信息。"""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_size_bytes: int = 0
    entry_count: int = 0

    @property
    def hit_rate(self) -> float:
        """缓存命中率。"""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total
