"""向量检索与语义搜索模块。

提供 Embedding 向量化、pgvector 存储、混合搜索（向量 + 关键词）、RRF 重排、语义缓存等能力。
"""

from datapilot_semantic.retrieval.embedding import EmbeddingClient
from datapilot_semantic.retrieval.vector_store import VectorStore
from datapilot_semantic.retrieval.hybrid_search import HybridSearcher
from datapilot_semantic.retrieval.cache import SemanticCache

__all__ = [
    "EmbeddingClient",
    "VectorStore",
    "HybridSearcher",
    "SemanticCache",
]
