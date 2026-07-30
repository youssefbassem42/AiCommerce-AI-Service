import logging
from datetime import UTC, datetime, timedelta

from app.application.integration.sync.orchestrator import SyncOrchestrator
from app.core.celery_app import celery_app
from app.domain.job.value_objects import JobStatus
from app.infrastructure.mongodb.collections import (
    get_dashboard_insights_collection,
    get_knowledge_jobs_collection,
    get_orders_collection,
)
from app.infrastructure.mongodb.repositories.integration_connection_repository import (
    IntegrationConnectionMongoRepository,
)
from app.infrastructure.tasks.helpers import _run_async

logger = logging.getLogger(__name__)


@celery_app.task(
    name="knowledge.retry_failed_jobs",
    max_retries=1,
    acks_late=True,
)
def retry_failed_jobs_task() -> dict:
    def _run():
        async def _async_run():
            collection = get_knowledge_jobs_collection()

            stale_running = await collection.find(
                {
                    "status": JobStatus.RUNNING.value,
                    "started_at": {"$lt": datetime.now(UTC) - timedelta(hours=2)},
                }
            ).to_list(length=100)

            requeued_running = 0
            for job in stale_running:
                await collection.update_one(
                    {"_id": job["_id"]},
                    {
                        "$set": {
                            "status": JobStatus.RETRYING.value,
                            "error_message": "Stale job timed out after 2 hours",
                            "updated_at": datetime.now(UTC),
                        }
                    },
                )
                requeued_running += 1

            retryable = await collection.find(
                {
                    "status": JobStatus.RETRYING.value,
                    "retry_count": {"$lt": 3},
                }
            ).to_list(length=100)

            requeued_retries = 0
            for job in retryable:
                await collection.update_one(
                    {"_id": job["_id"]},
                    {
                        "$set": {
                            "status": JobStatus.PENDING.value,
                            "updated_at": datetime.now(UTC),
                        }
                    },
                )
                requeued_retries += 1

            return {
                "stale_running_requeued": requeued_running,
                "retryable_requeued": requeued_retries,
            }

        return _run_async(_async_run())

    try:
        return _run()
    except Exception as exc:
        logger.error("retry_failed_jobs failed: %s", exc, exc_info=True)
        return {"error": str(exc)}


@celery_app.task(
    name="knowledge.cleanup_dead_letters",
    max_retries=1,
    acks_late=True,
)
def cleanup_dead_letters_task(dry_run: bool = True) -> dict:
    def _run():
        async def _async_run():
            collection = get_knowledge_jobs_collection()

            cutoff = datetime.now(UTC) - timedelta(days=7)
            old_dead = await collection.find(
                {
                    "status": JobStatus.DEAD_LETTER.value,
                    "completed_at": {"$lt": cutoff},
                }
            ).to_list(length=200)

            if not dry_run:
                ids = [j["_id"] for j in old_dead]
                if ids:
                    await collection.delete_many({"_id": {"$in": ids}})

            return {
                "found_old_dead_letters": len(old_dead),
                "dry_run": dry_run,
                "deleted": 0 if dry_run else len(old_dead),
            }

        return _run_async(_async_run())

    try:
        return _run()
    except Exception as exc:
        logger.error("cleanup_dead_letters failed: %s", exc, exc_info=True)
        return {"error": str(exc)}


async def _weekly_full_sync(repo, connections):
    orchestrator = SyncOrchestrator(repository=repo)
    results = []
    for conn in connections:
        try:
            sync_result = await orchestrator.sync_connection(conn.id)
            results.append(
                {
                    "connection_id": conn.id,
                    "store_id": conn.store_id,
                    "status": sync_result.status,
                    "error": sync_result.error,
                }
            )
        except Exception as e:
            logger.error("Weekly sync failed for '%s': %s", conn.id, e, exc_info=True)
            results.append({"connection_id": conn.id, "store_id": conn.store_id, "status": "error", "error": str(e)})
    return {
        "total_connections": len(connections),
        "results": results,
        "synced_at": datetime.now(UTC).isoformat(),
    }


async def _hourly_commerce_sync(repo, connections):
    orchestrator = SyncOrchestrator(repository=repo, vector_sync_enabled=False)
    now = datetime.now(UTC)
    sync_results = []
    total_revenue = 0.0
    store_revenue = {}

    for conn in connections:
        store_id = conn.store_id
        try:
            sync_result = await orchestrator.sync_connection(conn.id, entity_types=["inventory", "order"])
            sync_results.append(
                {
                    "connection_id": conn.id,
                    "store_id": store_id,
                    "status": sync_result.status,
                    "error": sync_result.error,
                }
            )
        except Exception as e:
            logger.error("Hourly sync failed for '%s': %s", conn.id, e, exc_info=True)
            sync_results.append({"connection_id": conn.id, "store_id": store_id, "status": "error", "error": str(e)})

    orders_coll = get_orders_collection()
    insights_coll = get_dashboard_insights_collection()

    pipeline = [
        {"$match": {"deleted_at": None}},
        {
            "$group": {
                "_id": "$store_id",
                "total_revenue": {"$sum": "$total_price.amount"},
                "order_count": {"$sum": 1},
                "avg_order_value": {"$avg": "$total_price.amount"},
            }
        },
    ]
    async for row in orders_coll.aggregate(pipeline):
        store_id = row["_id"]
        revenue = round(row["total_revenue"], 2)
        order_count = row["order_count"]
        avg_value = round(row["avg_order_value"], 2) if row["avg_order_value"] else 0.0
        total_revenue += revenue
        store_revenue[store_id] = {"revenue": revenue, "order_count": order_count, "avg_order_value": avg_value}

        await insights_coll.update_one(
            {"store_id": store_id},
            {
                "$set": {
                    "store_id": store_id,
                    "calculated_at": now,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "recommendations": [],
                    "metadata": {
                        "metric_name": "revenue",
                        "total_revenue": revenue,
                        "order_count": order_count,
                        "avg_order_value": avg_value,
                        "currency": "USD",
                    },
                    "created_at": now,
                },
            },
            upsert=True,
        )

        await insights_coll.update_one(
            {"store_id": store_id, "metadata.metric_name": "revenue"},
            {
                "$set": {
                    "metadata.total_revenue": revenue,
                    "metadata.order_count": order_count,
                    "metadata.avg_order_value": avg_value,
                    "metadata.last_updated": now.isoformat(),
                    "updated_at": now,
                }
            },
        )

    return {
        "connections_synced": len(sync_results),
        "sync_results": sync_results,
        "stores_with_revenue": len(store_revenue),
        "total_revenue": round(total_revenue, 2),
        "store_revenue": store_revenue,
        "synced_at": now.isoformat(),
    }


@celery_app.task(name="integration.weekly_sync", max_retries=1, acks_late=True)
def weekly_sync_task() -> dict:
    def _run():
        async def _async_run():
            repo = IntegrationConnectionMongoRepository()
            connections = await repo.find_active()
            return await _weekly_full_sync(repo, connections)

        return _run_async(_async_run())

    try:
        return _run()
    except Exception as exc:
        logger.error("weekly_sync failed: %s", exc, exc_info=True)
        return {"error": str(exc)}


@celery_app.task(name="integration.hourly_commerce_sync", max_retries=1, acks_late=True)
def hourly_commerce_sync_task() -> dict:
    def _run():
        async def _async_run():
            repo = IntegrationConnectionMongoRepository()
            connections = await repo.find_active()
            return await _hourly_commerce_sync(repo, connections)

        return _run_async(_async_run())

    try:
        return _run()
    except Exception as exc:
        logger.error("hourly_commerce_sync failed: %s", exc, exc_info=True)
        return {"error": str(exc)}
