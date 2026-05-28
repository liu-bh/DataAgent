"""VectorStore 单元测试。

测试内容:
- upsert_embedding（插入/更新向量）
- search（余弦相似度搜索）
- create_index（IVFFlat 索引创建）
- delete_embedding（删除向量）
- batch_upsert_embeddings
- 实体类型校验
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestVectorStoreInit:
    """VectorStore 初始化和实体类型校验测试。"""

    def test_validate_valid_entity_type(self) -> None:
        """测试合法实体类型校验通过。"""
        from datapilot_semantic.retrieval.vector_store import VectorStore

        session = MagicMock()
        store = VectorStore(session)

        for entity_type in ["metric", "dimension", "source_table"]:
            result = store._validate_entity_type(entity_type)
            assert result == entity_type

    def test_validate_invalid_entity_type(self) -> None:
        """测试非法实体类型抛出异常。"""
        from datapilot_semantic.retrieval.vector_store import VectorStore

        session = MagicMock()
        store = VectorStore(session)

        with pytest.raises(ValueError, match="不支持的实体类型"):
            store._validate_entity_type("invalid_type")

    def test_get_table_name(self) -> None:
        """测试表名映射。"""
        from datapilot_semantic.retrieval.vector_store import VectorStore

        session = MagicMock()
        store = VectorStore(session)

        assert store._get_table_name("metric") == "metrics"
        assert store._get_table_name("dimension") == "dimensions"
        assert store._get_table_name("source_table") == "source_tables"


class TestUpsertEmbedding:
    """VectorStore.upsert_embedding 测试。"""

    @pytest.mark.asyncio
    async def test_upsert_with_embedding(self) -> None:
        """测试 upsert 带向量。"""
        session = MagicMock()
        session.execute = AsyncMock()

        from datapilot_semantic.retrieval.vector_store import VectorStore

        store = VectorStore(session)
        entity_id = uuid.uuid4()
        embedding = [0.1] * 1536

        await store.upsert_embedding(
            entity_type="metric",
            entity_id=entity_id,
            embedding=embedding,
            name="GMV",
        )

        session.execute.assert_called_once()
        # 验证 SQL 包含正确的表名
        call_args = session.execute.call_args
        sql_str = str(call_args.args[0].text)
        assert "metrics" in sql_str
        assert "embedding" in sql_str
        # params 作为第二个位置参数传入
        params = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs
        assert "entity_id" in params

    @pytest.mark.asyncio
    async def test_upsert_clear_embedding(self) -> None:
        """测试 upsert 清除向量（embedding=None）。"""
        session = MagicMock()
        session.execute = AsyncMock()

        from datapilot_semantic.retrieval.vector_store import VectorStore

        store = VectorStore(session)
        entity_id = uuid.uuid4()

        await store.upsert_embedding(
            entity_type="metric",
            entity_id=entity_id,
            embedding=None,
        )

        session.execute.assert_called_once()
        call_args = session.execute.call_args
        sql_str = str(call_args.args[0].text)
        assert "NULL" in sql_str

    @pytest.mark.asyncio
    async def test_upsert_empty_embedding_list(self) -> None:
        """测试空列表视为 None。"""
        session = MagicMock()
        session.execute = AsyncMock()

        from datapilot_semantic.retrieval.vector_store import VectorStore

        store = VectorStore(session)
        entity_id = uuid.uuid4()

        await store.upsert_embedding(
            entity_type="dimension",
            entity_id=entity_id,
            embedding=[],
        )

        call_args = session.execute.call_args
        sql_str = str(call_args.args[0].text)
        assert "NULL" in sql_str


class TestVectorSearch:
    """VectorStore.search 测试。"""

    @pytest.mark.asyncio
    async def test_search_returns_hits(self) -> None:
        """测试搜索返回正确结果。"""
        # 构建模拟查询结果
        mock_row = MagicMock()
        mock_row.id = uuid.uuid4()
        mock_row.name = "GMV"
        mock_row.description = "商品交易总额"
        mock_row.similarity = 0.95
        mock_row.distance = 0.05

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]

        session = MagicMock()
        session.execute = AsyncMock(return_value=mock_result)

        from datapilot_semantic.retrieval.vector_store import VectorStore

        store = VectorStore(session)
        embedding = [0.1] * 1536

        hits = await store.search(
            entity_type="metric",
            query_embedding=embedding,
            top_k=10,
            threshold=0.7,
        )

        assert len(hits) == 1
        assert hits[0].entity_type == "metric"
        assert hits[0].entity_id == str(mock_row.id)
        assert hits[0].name == "GMV"
        assert hits[0].similarity == 0.95
        assert hits[0].distance == 0.05

    @pytest.mark.asyncio
    async def test_search_with_tenant_id(self) -> None:
        """测试带租户过滤的搜索。"""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        session = MagicMock()
        session.execute = AsyncMock(return_value=mock_result)

        from datapilot_semantic.retrieval.vector_store import VectorStore

        store = VectorStore(session)
        tenant_id = uuid.uuid4()

        await store.search(
            entity_type="metric",
            query_embedding=[0.1] * 1536,
            tenant_id=tenant_id,
        )

        call_args = session.execute.call_args
        # params 作为第二个位置参数传入
        params = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs
        assert "tenant_id" in params

    @pytest.mark.asyncio
    async def test_search_filters_by_threshold(self) -> None:
        """测试相似度阈值过滤（在 SQL 层过滤）。"""
        mock_row_low = MagicMock()
        mock_row_low.id = uuid.uuid4()
        mock_row_low.name = "低分"
        mock_row_low.description = None
        mock_row_low.similarity = 0.5
        mock_row_low.distance = 0.5

        mock_row_high = MagicMock()
        mock_row_high.id = uuid.uuid4()
        mock_row_high.name = "高分"
        mock_row_high.description = "desc"
        mock_row_high.similarity = 0.9
        mock_row_high.distance = 0.1

        # 子查询返回 2 条，外层 WHERE 过滤后只保留高分
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row_high]

        session = MagicMock()
        session.execute = AsyncMock(return_value=mock_result)

        from datapilot_semantic.retrieval.vector_store import VectorStore

        store = VectorStore(session)

        hits = await store.search(
            entity_type="metric",
            query_embedding=[0.1] * 1536,
            threshold=0.7,
        )

        assert len(hits) == 1
        assert hits[0].similarity == 0.9

    @pytest.mark.asyncio
    async def test_search_invalid_entity_type(self) -> None:
        """测试不支持的实体类型抛出异常。"""
        session = MagicMock()

        from datapilot_semantic.retrieval.vector_store import VectorStore

        store = VectorStore(session)

        with pytest.raises(ValueError, match="不支持的实体类型"):
            await store.search(
                entity_type="invalid",
                query_embedding=[0.1] * 1536,
            )


class TestCreateIndex:
    """VectorStore.create_index 测试。"""

    @pytest.mark.asyncio
    async def test_create_index_concurrently(self) -> None:
        """测试使用 CONCURRENTLY 创建索引。"""
        mock_connection = AsyncMock()
        mock_connection.in_transaction.return_value = False
        mock_connection.execute = AsyncMock()

        session = MagicMock()
        session.connection = AsyncMock(return_value=mock_connection)

        from datapilot_semantic.retrieval.vector_store import VectorStore

        store = VectorStore(session)

        index_name = await store.create_index(
            entity_type="metric",
            concurrently=True,
        )

        assert index_name == "idx_metrics_embedding"
        mock_connection.execute.assert_called_once()

        # 验证 SQL 包含 CONCURRENTLY
        call_args = mock_connection.execute.call_args
        sql_str = str(call_args.args[0].text)
        assert "CONCURRENTLY" in sql_str
        assert "ivfflat" in sql_str
        assert "vector_cosine_ops" in sql_str

    @pytest.mark.asyncio
    async def test_create_index_without_concurrently(self) -> None:
        """测试不使用 CONCURRENTLY 创建索引。"""
        mock_connection = AsyncMock()
        mock_connection.in_transaction.return_value = False
        mock_connection.execute = AsyncMock()

        session = MagicMock()
        session.connection = AsyncMock(return_value=mock_connection)

        from datapilot_semantic.retrieval.vector_store import VectorStore

        store = VectorStore(session)

        await store.create_index(
            entity_type="dimension",
            concurrently=False,
            lists=50,
        )

        call_args = mock_connection.execute.call_args
        sql_str = str(call_args.args[0].text)
        assert "CONCURRENTLY" not in sql_str
        assert "lists = 50" in sql_str

    @pytest.mark.asyncio
    async def test_create_index_all_entity_types(self) -> None:
        """测试三种实体类型都能创建索引。"""
        mock_connection = AsyncMock()
        mock_connection.in_transaction.return_value = False
        mock_connection.execute = AsyncMock()

        session = MagicMock()
        session.connection = AsyncMock(return_value=mock_connection)

        from datapilot_semantic.retrieval.vector_store import VectorStore

        store = VectorStore(session)

        expected = {
            "metric": "idx_metrics_embedding",
            "dimension": "idx_dimensions_embedding",
            "source_table": "idx_source_tables_embedding",
        }

        for entity_type, expected_name in expected.items():
            index_name = await store.create_index(entity_type=entity_type)
            assert index_name == expected_name


class TestDeleteEmbedding:
    """VectorStore.delete_embedding 测试。"""

    @pytest.mark.asyncio
    async def test_delete_existing(self) -> None:
        """测试删除存在的向量。"""
        mock_result = MagicMock()
        mock_result.rowcount = 1

        session = MagicMock()
        session.execute = AsyncMock(return_value=mock_result)
        session.commit = AsyncMock()

        from datapilot_semantic.retrieval.vector_store import VectorStore

        store = VectorStore(session)
        entity_id = uuid.uuid4()

        deleted = await store.delete_embedding(
            entity_type="metric",
            entity_id=entity_id,
        )

        assert deleted is True
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_non_existing(self) -> None:
        """测试删除不存在的向量。"""
        mock_result = MagicMock()
        mock_result.rowcount = 0

        session = MagicMock()
        session.execute = AsyncMock(return_value=mock_result)
        session.commit = AsyncMock()

        from datapilot_semantic.retrieval.vector_store import VectorStore

        store = VectorStore(session)
        entity_id = uuid.uuid4()

        deleted = await store.delete_embedding(
            entity_type="metric",
            entity_id=entity_id,
        )

        assert deleted is False


class TestBatchUpsert:
    """VectorStore.batch_upsert_embeddings 测试。"""

    @pytest.mark.asyncio
    async def test_batch_upsert(self) -> None:
        """测试批量 upsert。"""
        session = MagicMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        from datapilot_semantic.retrieval.vector_store import VectorStore

        store = VectorStore(session)
        items = [
            {"entity_id": uuid.uuid4(), "embedding": [0.1] * 1536},
            {"entity_id": uuid.uuid4(), "embedding": [0.2] * 1536},
        ]

        count = await store.batch_upsert_embeddings(
            entity_type="metric",
            items=items,
        )

        assert count == 2
        assert session.execute.call_count == 2
        session.commit.assert_called_once()


class TestBuildVectorLiteral:
    """_build_vector_literal 工具函数测试。"""

    def test_simple_vector(self) -> None:
        """测试简单向量字面量。"""
        from datapilot_semantic.retrieval.vector_store import _build_vector_literal

        result = _build_vector_literal([0.1, 0.2, 0.3])
        assert result == "[0.1,0.2,0.3]"

    def test_large_vector(self) -> None:
        """测试大维度向量字面量。"""
        from datapilot_semantic.retrieval.vector_store import _build_vector_literal

        vec = [float(i) / 100 for i in range(1536)]
        result = _build_vector_literal(vec)
        assert result.startswith("[")
        assert result.endswith("]")
        # 验证包含逗号分隔的数值
        parts = result[1:-1].split(",")
        assert len(parts) == 1536

    def test_negative_values(self) -> None:
        """测试包含负值的向量。"""
        from datapilot_semantic.retrieval.vector_store import _build_vector_literal

        result = _build_vector_literal([-0.5, 0.0, 0.5])
        assert result == "[-0.5,0.0,0.5]"


class TestVectorSearchHit:
    """VectorSearchHit 数据类测试。"""

    def test_creation(self) -> None:
        """测试创建搜索命中结果。"""
        from datapilot_semantic.retrieval.vector_store import VectorSearchHit

        hit = VectorSearchHit(
            entity_type="metric",
            entity_id=str(uuid.uuid4()),
            name="GMV",
            description="商品交易总额",
            similarity=0.95,
            distance=0.05,
        )

        assert hit.entity_type == "metric"
        assert hit.similarity == 0.95
        assert hit.distance == 0.05
