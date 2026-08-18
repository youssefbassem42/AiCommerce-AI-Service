import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from bson import ObjectId

from app.application.dto.ai_dto import EmbeddingRequest
from app.application.integration.sync.formatters import format_record
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory
from app.infrastructure.qdrant.provider import QdrantProvider
from app.infrastructure.vectorstore.base import VectorRecord
from app.shared.vector_payloads import product_payload

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768
BATCH_SIZE = 50
SUPPORTED_ENTITY_TYPES: set[str] | None = None  # None means all types are accepted

# Resolver signature: (store_id, organization_id) -> current knowledge version.
KnowledgeVersionResolver = Callable[[str, str], Awaitable[int]]

# Resolver signature: (store_id, external_id) -> canonical Mongo product id or None.
ProductIdentityResolver = Callable[[str, str], Awaitable[str | None]]


def _is_mongo_object_id(value: Any) -> bool:
    return isinstance(value, str) and ObjectId.is_valid(value)


class EntityVectorSyncResult:
    def __init__(self, entity_type: str):
        self.entity_type = entity_type
        self.total_records = 0
        self.total_embedded = 0
        self.total_synced = 0
        self.errors: list[str] = []

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "total_records": self.total_records,
            "total_embedded": self.total_embedded,
            "total_synced": self.total_synced,
            "errors": self.errors,
        }


class CommerceKnowledgeBridge:
    def __init__(
        self,
        vector_store: QdrantProvider | None = None,
        llm_provider: BaseLLMProvider | None = None,
        embedding_model: str = EMBEDDING_MODEL,
        knowledge_version_resolver: KnowledgeVersionResolver | None = None,
        product_identity_resolver: ProductIdentityResolver | None = None,
    ):
        self._vector_store = vector_store
        self._llm_provider = llm_provider
        self._embedding_model = embedding_model
        self._knowledge_version_resolver = knowledge_version_resolver or self._resolve_knowledge_version
        self._product_identity_resolver = product_identity_resolver or self._resolve_product_identity

    async def _resolve_product_identity(self, store_id: str, external_id: str) -> str | None:
        """Resolve the canonical Mongo product id for an externally-synced record.

        Integration payloads carry ``external_id`` but not the Mongo ``_id``;
        the vector identity must be the canonical Mongo product id so the
        recommendation pipeline can resolve candidates against the catalog.
        Returns None when the product is not in the catalog or the lookup
        fails (callers then keep the external id as a best-effort fallback).
        """
        try:
            from app.infrastructure.mongodb.collections import get_products_collection

            doc = await get_products_collection().find_one(
                {"store_id": store_id, "external_id": external_id},
                {"_id": 1},
            )
            if doc is None or doc.get("_id") is None:
                return None
            return str(doc["_id"])
        except Exception as exc:
            logger.warning(
                "Product identity lookup failed (store=%s external_id=%s): %s",
                store_id,
                external_id,
                exc,
            )
            return None

    async def _ensure_providers(self) -> None:
        if not self._vector_store:
            self._vector_store = QdrantProvider()
            try:
                await asyncio.wait_for(
                    self._vector_store.connect(),
                    timeout=10,
                )
            except (TimeoutError, ConnectionError, OSError) as e:
                logger.warning("Qdrant unavailable, vector sync will be skipped: %s", e)
                self._vector_store = None
                raise ConnectionError(f"Qdrant not available: {e}")
        if not self._llm_provider:
            from app.core.ai_settings import ai_settings

            embedding_provider = ai_settings.EMBEDDING_PROVIDER
            factory = LLMProviderFactory()
            self._llm_provider = factory.get_provider(embedding_provider)

    async def _resolve_knowledge_version(self, store_id: str, organization_id: str) -> int:
        """Resolve the store's current active knowledge version.

        Falls back to 1 when no version has been started or the lookup fails,
        so synced vectors remain retrievable under the default tenant version.
        """
        try:
            from app.infrastructure.mongodb.collections import get_knowledge_versions_collection

            col = get_knowledge_versions_collection()
            cursor = (
                col.find(
                    {"organization_id": organization_id, "store_id": store_id},
                )
                .sort("version_number", -1)
                .limit(1)
            )
            latest = await cursor.to_list(length=1)
            if latest:
                return int(latest[0].get("version_number", 1))
        except Exception as exc:
            logger.warning("Could not resolve knowledge version for store '%s': %s", store_id, exc)
        return 1

    async def sync_entity(
        self,
        store_id: str,
        organization_id: str,
        entity_type: str,
        records: list[dict[str, Any]],
    ) -> EntityVectorSyncResult:
        result = EntityVectorSyncResult(entity_type=entity_type)

        if SUPPORTED_ENTITY_TYPES is not None and entity_type not in SUPPORTED_ENTITY_TYPES:
            result.errors.append(f"Entity type '{entity_type}' not supported for vector sync.")
            return result

        if not records:
            logger.info("No records to sync for entity '%s' (store=%s)", entity_type, store_id)
            return result

        result.total_records = len(records)

        try:
            await self._ensure_providers()
        except Exception as e:
            msg = f"Vector store unavailable, skipping sync: {e}"
            logger.warning("%s", msg)
            result.errors.append(msg)
            return result

        try:
            knowledge_version = await self._knowledge_version_resolver(store_id, organization_id)
        except Exception as exc:
            logger.warning("Knowledge version resolution failed for store '%s': %s", store_id, exc)
            knowledge_version = 1

        collection = f"kb_{store_id}"

        try:
            if not await self._vector_store.collection_exists(collection):
                await self._vector_store.create_collection(collection, vector_size=EMBEDDING_DIMENSIONS)
        except Exception as e:
            logger.warning("Failed to ensure collection '%s': %s", collection, e)

        try:
            await self._delete_stale_vectors(collection, store_id, entity_type)
        except Exception as e:
            logger.warning("Failed to delete stale vectors for %s/%s: %s", store_id, entity_type, e)

        records = await self._resolve_product_identities(store_id, entity_type, records, result)
        if not records:
            logger.warning("No indexable records for entity '%s' (store=%s)", entity_type, store_id)
            return result
        result.total_records = len(records)

        formatted = []
        for rec in records:
            text = format_record(entity_type, rec)
            if text:
                formatted.append(text)

        if not formatted:
            logger.warning("No formatted records for entity '%s' (store=%s)", entity_type, store_id)
            return result

        all_points: list[VectorRecord] = []
        for i in range(0, len(formatted), BATCH_SIZE):
            batch = formatted[i : i + BATCH_SIZE]
            batch_records = records[i : i + BATCH_SIZE]
            try:
                request = EmbeddingRequest(input=batch, model=self._embedding_model)
                response = await self._llm_provider.embeddings(request)
                for j, emb in enumerate(response.embeddings):
                    if j >= len(batch_records):
                        # Provider returned fewer embeddings than the batch
                        # (e.g. a partial rate-limit failure): stop here instead
                        # of indexing out of range.
                        break
                    rec = batch_records[j]
                    rec_idx = i + j
                    entity_key = _entity_key(rec)
                    all_points.append(
                        VectorRecord(
                            id=f"{store_id}:{entity_type}:{entity_key}:{rec_idx}",
                            vector=emb,
                            payload=self._build_payload(
                                organization_id=organization_id,
                                store_id=store_id,
                                entity_type=entity_type,
                                entity_key=entity_key,
                                record=rec,
                                content=batch[j],
                                rec_idx=rec_idx,
                                knowledge_version=knowledge_version,
                            ),
                        )
                    )
                result.total_embedded += len(response.embeddings)
            except Exception as e:
                logger.exception("Embedding failed for batch %d of '%s'", i // BATCH_SIZE, entity_type)
                result.errors.append(f"Embedding batch failed: {e}")

        if all_points:
            try:
                await self._vector_store.upsert(collection, all_points)
                result.total_synced = len(all_points)
                logger.info(
                    "Synced %d vectors for entity '%s' (store=%s)",
                    len(all_points),
                    entity_type,
                    store_id,
                )
            except Exception as e:
                logger.exception("Vector store upsert failed for '%s'", entity_type)
                result.errors.append(f"Vector store upsert failed: {e}")

        return result

    async def sync_record(
        self,
        store_id: str,
        organization_id: str,
        entity_type: str,
        record: dict[str, Any],
    ) -> EntityVectorSyncResult:
        """Embed and upsert a single record (incremental CRUD path)."""
        return await self.sync_entity(store_id, organization_id, entity_type, [record])

    async def delete_record(
        self,
        store_id: str,
        entity_type: str,
        entity_key: str,
    ) -> int:
        """Remove all vector points belonging to a single record."""
        await self._ensure_providers()
        collection = f"kb_{store_id}"
        exists = await self._vector_store.collection_exists(collection)
        if not exists:
            return 0
        return await self._vector_store.delete_by_filter(
            collection,
            must=[
                {"key": "store_id", "value": store_id},
                {"key": "entity_type", "value": entity_type},
                {"key": "document_id", "value": entity_key},
            ],
            must_not=None,
        )

    async def _resolve_product_identities(
        self,
        store_id: str,
        entity_type: str,
        records: list[dict[str, Any]],
        result: EntityVectorSyncResult,
    ) -> list[dict[str, Any]]:
        """Enforce the canonical product vector identity (Mongo ``_id``).

        Only product records are rewritten. A record that already carries a
        valid Mongo ObjectId is kept untouched; one with an external identity
        is resolved against the catalog; one with no usable identity at all
        is skipped and reported so payloads never index an empty key.
        """
        if entity_type != "product":
            return records

        enriched: list[dict[str, Any]] = []
        for rec in records:
            if _is_mongo_object_id(_entity_key(rec)):
                enriched.append(rec)
                continue
            external_id = rec.get("external_id") or rec.get("id")
            if not external_id:
                result.errors.append(f"Skipped product with no canonical id: {rec.get('title') or '(untitled)'}")
                logger.warning("Skipping product without canonical id (store=%s)", store_id)
                continue
            resolved = await self._product_identity_resolver(store_id, str(external_id))
            if resolved and _is_mongo_object_id(resolved):
                enriched.append({**rec, "_id": resolved})
                continue
            if rec.get("_id"):
                # Best effort: keep the existing identity so the sync is not
                # lost; the canonical-id reindex will repair the payload.
                logger.warning(
                    "Product identity not canonical (store=%s external_id=%s) — kept existing _id",
                    store_id,
                    external_id,
                )
                enriched.append(rec)
                continue
            enriched.append({**rec, "_id": str(external_id)})
            logger.warning(
                "Product identity not resolvable (store=%s external_id=%s) — indexed under external id",
                store_id,
                external_id,
            )
        return enriched

    async def purge_entity_vectors(self, store_id: str, entity_type: str) -> int:
        """Delete all vector points of one entity type for a store (any source).

        Used by the store reindex path: product vectors are rebuilt entirely
        from the current Mongo catalog, so stale points (e.g. indexed under a
        legacy external-id identity) must be removed first. Strictly
        store-scoped and entity-scoped — never a collection drop.
        """
        await self._ensure_providers()
        collection = f"kb_{store_id}"
        if not await self._vector_store.collection_exists(collection):
            return 0
        return await self._vector_store.delete_by_filter(
            collection,
            must=[
                {"key": "store_id", "value": store_id},
                {"key": "entity_type", "value": entity_type},
            ],
            must_not=None,
        )

    def _build_payload(
        self,
        organization_id: str,
        store_id: str,
        entity_type: str,
        entity_key: str,
        record: dict[str, Any],
        content: str,
        rec_idx: int,
        knowledge_version: int,
    ) -> dict[str, Any]:
        title = record.get("title") or record.get("name") or f"{entity_type}:{entity_key}"
        if entity_type == "product":
            price = record.get("price")
            if isinstance(price, dict):
                price = price.get("amount")
            try:
                price_float = float(price) if price is not None else None
            except (TypeError, ValueError):
                price_float = None
            currency = record.get("currency") or (
                record.get("price", {}).get("currency") if isinstance(record.get("price"), dict) else None
            )
            specs = []
            for spec_name in ("sku", "vendor", "product_type", "inventory_quantity", "compare_at_price"):
                if record.get(spec_name) is not None:
                    specs.append({"name": spec_name, "value": str(record.get(spec_name))})
            if record.get("tags"):
                specs.append({"name": "tags", "value": ", ".join(str(t) for t in record["tags"])})
            extra: dict[str, Any] = {}
            if record.get("image_url"):
                extra["image_url"] = str(record["image_url"])
            if record.get("url") or record.get("handle"):
                extra["product_url"] = str(record.get("url") or record.get("handle"))
            return product_payload(
                organization_id=organization_id,
                store_id=store_id,
                product_id=entity_key,
                title=title,
                content=content,
                price=price_float,
                currency=currency or None,
                category_id=record.get("category_id"),
                brand_id=record.get("brand_id"),
                specs=specs or None,
                external_id=str(record.get("external_id") or ""),
                document_id=entity_key,
                document_title=title,
                chunk_index=rec_idx,
                knowledge_version=knowledge_version,
                **extra,
            )
        from app.shared.vector_payloads import EntityType, base_entity_payload

        entity_type_value = EntityType.as_value(entity_type)
        return base_entity_payload(
            organization_id=organization_id,
            store_id=store_id,
            entity_type=entity_type_value,
            entity_id=entity_key,
            source_type="integration_sync",
            external_id=str(record.get("external_id") or ""),
            document_id=entity_key,
            document_title=title,
            document_status="active",
            chunk_index=rec_idx,
            content=content,
            knowledge_version=knowledge_version,
        )

    async def _delete_stale_vectors(
        self,
        collection: str,
        store_id: str,
        entity_type: str,
    ) -> None:
        try:
            exists = await self._vector_store.collection_exists(collection)
            if not exists:
                return
            await self._vector_store.delete_by_filter(
                collection,
                must=[
                    {"key": "store_id", "value": store_id},
                    {"key": "entity_type", "value": entity_type},
                    {"key": "source_type", "value": "integration_sync"},
                ],
                must_not=None,
            )
        except Exception as e:
            logger.warning("Could not delete stale vectors: %s", e)
            raise


def _entity_key(record: dict[str, Any]) -> str:
    """Stable tenant-scoped identity for a record: Mongo _id first, then external id."""
    key = record.get("_id") or record.get("external_id") or record.get("id") or ""
    return str(key)
