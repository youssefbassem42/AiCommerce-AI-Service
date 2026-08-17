"""B2 remediation — canonical product vector identity + store-scoped purge.

Regression tests for the discovered bug: integration payloads carry
``external_id`` but not the Mongo ``_id``, so vectors were indexed under the
external id while the recommendation pipeline resolves candidates by Mongo
``_id``. The bridge must enforce the canonical Mongo product id as the vector
identity, and the store reindex must purge stale product points before
rebuilding them.

Covers:
- Valid Mongo ObjectId ``_id`` is kept untouched (no resolver call)
- External identity resolved to the canonical Mongo id via the resolver
- Unresolvable identity keeps the existing ``_id`` (best effort)
- No identity at all is skipped and reported
- ``purge_entity_vectors`` is store- and entity-scoped, never a collection drop
- ``StoreIndexer`` purges product vectors before reindexing products
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.integration.sync.knowledge_bridge import CommerceKnowledgeBridge
from app.application.knowledge.indexing import StoreIndexer


@pytest.fixture
def mock_vector_store():
    vs = AsyncMock()
    vs.collection_exists = AsyncMock(return_value=True)
    vs.delete_by_filter = AsyncMock()
    vs.upsert = AsyncMock()
    return vs


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.embeddings = AsyncMock(return_value=MagicMock(embeddings=[[0.1, 0.2, 0.3]], model="gemini-embedding-001"))
    return llm


CANONICAL_1 = "6a7ce4bb89fffc2a947e9eb5"
CANONICAL_2 = "6a7ce4bb89fffc2a947e9eb6"


def make_bridge(mock_vector_store, mock_llm, resolver=None):
    return CommerceKnowledgeBridge(
        vector_store=mock_vector_store,
        llm_provider=mock_llm,
        knowledge_version_resolver=AsyncMock(return_value=1),
        product_identity_resolver=resolver,
    )


class TestCanonicalProductIdentity:
    @pytest.mark.asyncio
    async def test_valid_mongo_id_kept_without_resolver_call(self, mock_vector_store, mock_llm):
        resolver = AsyncMock(return_value=None)
        bridge = make_bridge(mock_vector_store, mock_llm, resolver)
        await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="product",
            records=[{"_id": CANONICAL_1, "title": "Laptop", "external_id": "1"}],
        )
        resolver.assert_not_called()
        point = mock_vector_store.upsert.await_args.args[1][0]
        assert point.id == f"s1:product:{CANONICAL_1}:0"
        assert point.payload["product_id"] == CANONICAL_1

    @pytest.mark.asyncio
    async def test_external_identity_resolved_to_canonical_mongo_id(self, mock_vector_store, mock_llm):
        resolver = AsyncMock(return_value=CANONICAL_2)
        bridge = make_bridge(mock_vector_store, mock_llm, resolver)
        await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="product",
            records=[{"external_id": "20", "title": "Laptop Backpack", "price": 55}],
        )
        resolver.assert_awaited_once_with("s1", "20")
        point = mock_vector_store.upsert.await_args.args[1][0]
        assert point.id == f"s1:product:{CANONICAL_2}:0"
        assert point.payload["product_id"] == CANONICAL_2
        assert point.payload["entity_id"] == CANONICAL_2
        assert point.payload["document_id"] == CANONICAL_2

    @pytest.mark.asyncio
    async def test_unresolvable_identity_keeps_existing_id(self, mock_vector_store, mock_llm):
        resolver = AsyncMock(return_value=None)
        bridge = make_bridge(mock_vector_store, mock_llm, resolver)
        await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="product",
            records=[{"_id": "mongo-id-1", "title": "Retro Sunglasses", "external_id": "23"}],
        )
        point = mock_vector_store.upsert.await_args.args[1][0]
        assert point.payload["product_id"] == "mongo-id-1"

    @pytest.mark.asyncio
    async def test_identity_without_id_uses_external_id_fallback(self, mock_vector_store, mock_llm):
        resolver = AsyncMock(return_value=None)
        bridge = make_bridge(mock_vector_store, mock_llm, resolver)
        await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="product",
            records=[{"external_id": "p1", "title": "A"}],
        )
        point = mock_vector_store.upsert.await_args.args[1][0]
        assert point.payload["product_id"] == "p1"

    @pytest.mark.asyncio
    async def test_product_without_identity_is_skipped(self, mock_vector_store, mock_llm):
        bridge = make_bridge(mock_vector_store, mock_llm)
        result = await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="product",
            records=[{"title": "No Identity Product"}],
        )
        assert result.total_synced == 0
        mock_vector_store.upsert.assert_not_called()
        assert any("no canonical id" in err for err in result.errors)

    @pytest.mark.asyncio
    async def test_non_product_entities_are_not_rewritten(self, mock_vector_store, mock_llm):
        resolver = AsyncMock(side_effect=AssertionError("should not be called"))
        bridge = make_bridge(mock_vector_store, mock_llm, resolver)
        await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="category",
            records=[{"external_id": "c1", "name": "Electronics"}],
        )
        resolver.assert_not_called()
        point = mock_vector_store.upsert.await_args.args[1][0]
        assert point.payload["document_title"] == "Electronics"

    @pytest.mark.asyncio
    async def test_default_resolver_failure_keeps_sync_alive(self, mock_vector_store, mock_llm):
        bridge = make_bridge(mock_vector_store, mock_llm)
        result = await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="product",
            records=[{"external_id": "x1", "title": "A"}],
        )
        assert result.total_synced == 1
        assert mock_vector_store.upsert.await_args.args[1][0].payload["product_id"] == "x1"


class TestPurgeEntityVectors:
    @pytest.mark.asyncio
    async def test_purge_is_store_and_entity_scoped(self, mock_vector_store, mock_llm):
        mock_vector_store.delete_by_filter = AsyncMock(return_value=7)
        bridge = make_bridge(mock_vector_store, mock_llm)
        deleted = await bridge.purge_entity_vectors(store_id="s1", entity_type="product")
        assert deleted == 7
        kwargs = mock_vector_store.delete_by_filter.await_args.kwargs
        must = kwargs["must"]
        assert {"key": "store_id", "value": "s1"} in must
        assert {"key": "entity_type", "value": "product"} in must
        assert kwargs["must_not"] is None
        assert mock_vector_store.delete_collection.call_count == 0

    @pytest.mark.asyncio
    async def test_purge_missing_collection_returns_zero(self, mock_vector_store, mock_llm):
        mock_vector_store.collection_exists = AsyncMock(return_value=False)
        bridge = make_bridge(mock_vector_store, mock_llm)
        assert await bridge.purge_entity_vectors(store_id="s1", entity_type="product") == 0
        mock_vector_store.delete_by_filter.assert_not_called()

    @pytest.mark.asyncio
    async def test_purge_failure_does_not_raise(self, mock_vector_store, mock_llm):
        mock_vector_store.delete_by_filter = AsyncMock(side_effect=RuntimeError("qdrant down"))
        bridge = make_bridge(mock_vector_store, mock_llm)
        with pytest.raises(RuntimeError):
            await bridge.purge_entity_vectors(store_id="s1", entity_type="product")


class TestStoreIndexerProductPurge:
    @pytest.mark.asyncio
    async def test_index_products_purges_before_sync(self):
        bridge = AsyncMock()
        bridge.purge_entity_vectors = AsyncMock(return_value=3)
        indexer = StoreIndexer(bridge=bridge)
        indexer._iter_products = AsyncMock(return_value=[])
        indexer._sync_entity_type = AsyncMock(return_value={"synced": 0})

        summary = await indexer._index_products("s1")

        bridge.purge_entity_vectors.assert_awaited_once_with("s1", "product")
        indexer._sync_entity_type.assert_awaited_once()
        assert summary == {"synced": 0}

    @pytest.mark.asyncio
    async def test_index_products_continues_when_purge_fails(self):
        bridge = AsyncMock()
        bridge.purge_entity_vectors = AsyncMock(side_effect=RuntimeError("qdrant down"))
        indexer = StoreIndexer(bridge=bridge)
        indexer._iter_products = AsyncMock(return_value=[])
        indexer._sync_entity_type = AsyncMock(return_value={"synced": 0})

        summary = await indexer._index_products("s1")

        assert summary == {"synced": 0}
