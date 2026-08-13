"""Global backfill: index ALL real commerce data (products, categories, orders) and
knowledge documents for every store into each store's RAG vector collection.

Reads only real data from Mongo — never seeds or fakes anything. Runs the same
code path as the admin reindex endpoint (POST /api/v1/knowledge/jobs/reindex).

Usage:
    python scripts/backfill_all_stores.py [--store STORE_ID] [--wait]
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_all_stores")


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
    parser.add_argument("--store", help="Index only this store id")
    parser.add_argument("--wait", action="store_true", help="Wait for dispatched document jobs to finish")
    args = parser.parse_args()

    store_ids = [args.store] if args.store else _all_store_ids()
    logger.info("Indexing %d store(s): %s", len(store_ids), store_ids)

    indexer = StoreIndexer()
    for store_id in store_ids:
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
