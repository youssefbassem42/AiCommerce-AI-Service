"""Reindex all tenant vector collections with the canonical payload model.

Phase 1 migration: purge legacy vectors that lack the canonical ``entity_type``
payload field (indexed before the canonical payload existed) and re-index every
store's real commerce data and knowledge documents through the same code path
as the admin reindex endpoint (``StoreIndexer``).

Steps per store::

    purge legacy vectors (entity_type missing / source_type empty)
          ↓
    reindex products/categories/orders (canonical payload)
          ↓
    reindex knowledge chunks (canonical payload, via celery jobs)
          ↓
    ensure payload indexes (entity_type, store_id, document_status)

Usage:
    python scripts/reindex.py [--store STORE_ID] [--wait] [--skip-purge]
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.application.knowledge.indexing import StoreIndexer  # noqa: E402
from app.infrastructure.mongodb.collections import (  # noqa: E402
    get_categories_collection,
    get_knowledge_documents_collection,
    get_orders_collection,
    get_products_collection,
)
from app.infrastructure.qdrant.provider import QdrantProvider  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("reindex")


def _all_store_ids() -> list[str]:
    stores: set[str] = set()
    for collection in (
        get_products_collection(),
        get_categories_collection(),
        get_orders_collection(),
        get_knowledge_documents_collection(),
    ):
        for store_id in collection.distinct("store_id"):
            if store_id:
                stores.add(str(store_id))
    return sorted(stores)


async def _purge_legacy_vectors(vs: QdrantProvider, store_id: str) -> int:
    """Delete vectors that predate the canonical payload model.

    Legacy knowledge vectors were upserted with only ``chunk_id``/``document_id``
    (no ``entity_type``, no ``store_id``), so they are invisible to every
    canonical filter and must be removed before re-indexing.
    """
    collection = f"kb_{store_id}"
    if not await vs.collection_exists(collection):
        return 0

    deleted = 0
    for must in (
        [{"key": "entity_type", "op": "is_null"}],
        [{"key": "entity_type", "op": "is_empty"}],
        [{"key": "source_type", "op": "is_empty"}],
    ):
        try:
            await vs.delete_by_filter(collection, must=must, must_not=None)
            deleted += 1
        except Exception:
            logger.exception("Purge failed for '%s' with filter %s", collection, must)
    return deleted


async def _ensure_payload_indexes(vs: QdrantProvider, store_id: str) -> None:
    collection = f"kb_{store_id}"
    if not await vs.collection_exists(collection):
        return
    for field in ("entity_type", "store_id", "document_status"):
        try:
            await vs.create_payload_index(collection, field_name=field, field_type="keyword")
        except Exception:
            logger.exception("Payload index creation failed for '%s/%s'", collection, field)


async def _wait_for_jobs(job_ids: list[str], timeout: int = 900) -> None:
    from bson import ObjectId

    from app.infrastructure.mongodb.collections import get_knowledge_jobs_collection

    remaining = dict.fromkeys(job_ids, "pending")
    deadline = time.time() + timeout
    while remaining and time.time() < deadline:
        for job_id in list(remaining):
            job = await get_knowledge_jobs_collection().find_one({"_id": ObjectId(job_id)})
            if job:
                status = job.get("status")
                if status in ("completed", "failed", "dead_letter"):
                    remaining[job_id] = status
                    logger.info("job %s -> %s", job_id, status)
        for job_id, status in list(remaining.items()):
            if status != "pending":
                del remaining[job_id]
        if remaining:
            await asyncio.sleep(10)
    pending = [jid for jid, s in remaining.items() if s == "pending"]
    if pending:
        logger.warning("Timed out waiting for jobs: %s", pending)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", help="Reindex only this store id")
    parser.add_argument("--wait", action="store_true", help="Wait for dispatched document jobs to finish")
    parser.add_argument("--skip-purge", action="store_true", help="Skip the legacy-vector purge step")
    args = parser.parse_args()

    store_ids = [args.store] if args.store else _all_store_ids()
    logger.info("Reindexing %d store(s): %s", len(store_ids), store_ids)

    vs = QdrantProvider()
    await vs.connect()

    indexer = StoreIndexer()
    try:
        for store_id in store_ids:
            if not args.skip_purge:
                deleted = await _purge_legacy_vectors(vs, store_id)
                if deleted:
                    logger.info("store=%s purged %d legacy vector group(s)", store_id, deleted)

            summary = await indexer.index_store(
                store_id,
                progress_callback=lambda p, s=store_id: logger.info("  %s progress: %.0f%%", s, p * 100),
            )
            logger.info(
                "store=%s products=%s categories=%s orders=%s docs=%s",
                store_id,
                summary["products"],
                summary["categories"],
                summary["orders"],
                summary["documents"],
            )

            await _ensure_payload_indexes(vs, store_id)
    finally:
        await vs.disconnect()

    if args.wait:
        from app.infrastructure.mongodb.collections import get_knowledge_jobs_collection

        dispatched = (
            await get_knowledge_jobs_collection()
            .find({"triggered_by": "system:store_reindex", "status": {"$in": ["pending", "running"]}})
            .to_list(length=10_000)
        )
        job_ids = [str(j["_id"]) for j in dispatched]
        if job_ids:
            logger.info("Waiting for %d dispatched document jobs", len(job_ids))
            await _wait_for_jobs(job_ids)


if __name__ == "__main__":
    asyncio.run(main())
