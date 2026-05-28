"""DataPilot 查询结果缓存模块。

提供分级缓存策略（Redis 小结果 / MinIO 大结果）、
统一缓存管理器和数据新鲜度标注能力。
"""

from .freshness import FreshnessChecker, FreshnessInfo, FreshnessLevel
from .manager import CacheResult, ResultCacheManager
from .minio_cache import MinIOResultCache
from .redis_cache import RedisResultCache
from .strategy import CachePolicy, CacheStrategy, CacheTier

__all__ = [
    "CachePolicy",
    "CacheResult",
    "CacheStrategy",
    "CacheTier",
    "FreshnessChecker",
    "FreshnessInfo",
    "FreshnessLevel",
    "MinIOResultCache",
    "RedisResultCache",
    "ResultCacheManager",
]
