import contextlib
import logging

from pymongo import ASCENDING, DESCENDING, TEXT, IndexModel

logger = logging.getLogger(__name__)


async def ensure_knowledge_upload_indexes(db) -> None:
    """Reconcile knowledge_uploads indexes to the scoped (checksum, store_id) uniqueness.

    Idempotent and safe to run at startup: keeps the per-tenant dedup index in place and
    drops the legacy global `checksum_1` index that could reject legitimate cross-store
    uploads of identical content.
    """
    try:
        await db["knowledge_uploads"].create_indexes(
            [
                IndexModel([("checksum", ASCENDING), ("store_id", ASCENDING)], unique=True),
            ]
        )
        with contextlib.suppress(Exception):
            await db["knowledge_uploads"].drop_index("checksum_1")
        logger.info("knowledge_uploads indexes reconciled (checksum+store_id unique).")
    except Exception:
        logger.exception("Failed to reconcile knowledge_uploads indexes")


async def ensure_ticket_idempotency_index(db) -> None:
    """Reconcile the ticket_analysis idempotency index.

    Enforces at most one OPEN ticket per (store_id, conversation_id) so concurrent
    escalations of the same conversation cannot create duplicates. The partial filter
    scopes uniqueness to active statuses (resolved/closed tickets do not block new
    escalations) and to documents that actually carry a conversation_id, so pre-existing
    records are never rejected. Idempotent and safe to run at startup.
    """
    try:
        await db["ticket_analysis"].create_indexes(
            [
                IndexModel(
                    [("store_id", ASCENDING), ("conversation_id", ASCENDING)],
                    unique=True,
                    partialFilterExpression={
                        "conversation_id": {"$type": "string"},
                        "status": {"$in": ["open", "in_progress"]},
                    },
                )
            ]
        )
        logger.info("ticket_analysis idempotency index reconciled (open ticket per conversation).")
    except Exception:
        logger.exception("Failed to reconcile ticket_analysis idempotency index")


async def setup_database_indexes(db) -> None:
    """Create all indexes on collections for fast lookup and query optimization."""
    logger.info("Initializing database indexes...")

    await db["conversations"].create_indexes(
        [
            IndexModel([("customer_id", ASCENDING)]),
            IndexModel([("store_id", ASCENDING)]),
            IndexModel([("store_id", ASCENDING), ("customer_id", ASCENDING)]),
            IndexModel([("status", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
        ]
    )

    await db["messages"].create_indexes(
        [
            IndexModel([("conversation_id", ASCENDING)]),
            IndexModel([("conversation_id", ASCENDING), ("timestamp", ASCENDING)]),
            IndexModel([("timestamp", ASCENDING)]),
        ]
    )

    await db["knowledge_documents"].create_indexes(
        [
            IndexModel([("store_id", ASCENDING)]),
            IndexModel([("status", ASCENDING)]),
            IndexModel([("title", TEXT)], name="knowledge_doc_title_text"),
        ]
    )

    await db["knowledge_chunks"].create_indexes(
        [
            IndexModel([("document_id", ASCENDING)]),
            IndexModel([("document_id", ASCENDING), ("chunk_index", ASCENDING)], unique=True),
            IndexModel([("embedding_id", ASCENDING)], sparse=True),
        ]
    )

    await db["knowledge_business_summaries"].create_indexes(
        [
            IndexModel([("document_id", ASCENDING)]),
            IndexModel([("document_id", ASCENDING), ("version_number", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
        ]
    )

    await db["knowledge_uploads"].create_indexes(
        [
            IndexModel([("store_id", ASCENDING)]),
            IndexModel([("checksum", ASCENDING), ("store_id", ASCENDING)], unique=True),
            IndexModel([("status", ASCENDING)]),
            IndexModel([("uploaded_by", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
            IndexModel([("store_id", ASCENDING), ("status", ASCENDING)]),
        ]
    )
    with contextlib.suppress(Exception):
        await db["knowledge_uploads"].drop_index("checksum_1")

    await db["runtime_logs"].create_indexes(
        [
            IndexModel([("conversation_id", ASCENDING)]),
            IndexModel([("timestamp", ASCENDING)], expireAfterSeconds=2592000),  # 30 days
            IndexModel([("level", ASCENDING)]),
        ]
    )

    await db["prompt_history"].create_indexes(
        [
            IndexModel([("runtimeId", ASCENDING)]),
            IndexModel([("timestamp", ASCENDING)], expireAfterSeconds=2592000),
            IndexModel([("provider", ASCENDING), ("model", ASCENDING)]),
        ]
    )

    await db["recommendations"].create_indexes(
        [
            IndexModel([("conversation_id", ASCENDING)]),
            IndexModel([("customer_id", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
        ]
    )

    await db["bundle_suggestions"].create_indexes(
        [
            IndexModel([("store_id", ASCENDING)]),
            IndexModel([("status", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
        ]
    )

    await db["dashboard_insights"].create_indexes(
        [IndexModel([("store_id", ASCENDING)]), IndexModel([("calculated_at", DESCENDING)])]
    )

    await db["ticket_analysis"].create_indexes(
        [
            IndexModel([("ticket_id", ASCENDING)], unique=True),
            IndexModel([("store_id", ASCENDING)]),
            IndexModel([("customer_id", ASCENDING)]),
            IndexModel([("priority", ASCENDING)]),
            IndexModel([("sentiment", ASCENDING)]),
            IndexModel([("status", ASCENDING)]),
            IndexModel([("store_id", ASCENDING), ("status", ASCENDING)]),
            IndexModel([("store_id", ASCENDING), ("customer_id", ASCENDING), ("status", ASCENDING)]),
        ]
    )

    await db["ticket_notifications"].create_indexes(
        [
            IndexModel([("ticket_id", ASCENDING)]),
            IndexModel([("customer_id", ASCENDING), ("read", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
        ]
    )

    await db["knowledge_jobs"].create_indexes(
        [
            IndexModel([("status", ASCENDING), ("job_type", ASCENDING)]),
            IndexModel([("status", ASCENDING), ("created_at", ASCENDING)]),
            IndexModel([("celery_task_id", ASCENDING)], sparse=True),
            IndexModel([("store_id", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
        ]
    )

    await db["products"].create_indexes(
        [
            IndexModel(
                [("organization_id", ASCENDING), ("store_id", ASCENDING), ("external_id", ASCENDING)],
                unique=True,
            ),
            IndexModel([("store_id", ASCENDING), ("status", ASCENDING)]),
            IndexModel([("title", TEXT)], name="product_title_text"),
            IndexModel([("store_id", ASCENDING), ("updated_at", DESCENDING)]),
        ]
    )

    await db["categories"].create_indexes(
        [
            IndexModel([("store_id", ASCENDING), ("external_id", ASCENDING)], unique=True),
            IndexModel([("store_id", ASCENDING), ("parent_id", ASCENDING)]),
        ]
    )

    await db["orders"].create_indexes(
        [
            IndexModel([("store_id", ASCENDING), ("external_id", ASCENDING)], unique=True),
            IndexModel([("store_id", ASCENDING), ("created_at", DESCENDING)]),
        ]
    )

    await db["inventory"].create_indexes(
        [
            IndexModel([("store_id", ASCENDING), ("variant_id", ASCENDING)], unique=True),
        ]
    )

    await db["customers"].create_indexes(
        [
            IndexModel([("store_id", ASCENDING), ("external_id", ASCENDING)], unique=True),
            IndexModel([("store_id", ASCENDING), ("email", ASCENDING)]),
        ]
    )

    await db["bundle_tracking"].create_indexes(
        [
            IndexModel([("store_id", ASCENDING), ("bundle_key", ASCENDING)], unique=True),
            IndexModel([("store_id", ASCENDING), ("is_top", ASCENDING)]),
            IndexModel([("store_id", ASCENDING), ("copy_count", DESCENDING)]),
            IndexModel([("last_copied_at", DESCENDING)]),
        ]
    )

    await db["integration_connections"].create_indexes(
        [
            IndexModel([("store_id", ASCENDING)]),
            IndexModel([("organization_id", ASCENDING), ("store_id", ASCENDING)]),
            IndexModel([("store_id", ASCENDING), ("name", ASCENDING)], unique=True),
            IndexModel([("platform_name", ASCENDING)]),
        ]
    )

    await db["prompts"].create_indexes(
        [
            IndexModel([("key", ASCENDING)], unique=True),
            IndexModel([("type", ASCENDING)]),
            IndexModel([("tags", ASCENDING)]),
            IndexModel([("is_active", ASCENDING)]),
            IndexModel([("updated_at", DESCENDING)]),
        ]
    )

    await db["store_capabilities"].create_indexes(
        [
            IndexModel([("store_id", ASCENDING)], unique=True),
        ]
    )

    await db["api_keys"].create_indexes(
        [
            IndexModel([("key_hash", ASCENDING)], unique=True),
            IndexModel([("key_prefix", ASCENDING)], unique=True),
            IndexModel([("store_id", ASCENDING)]),
            IndexModel([("is_active", ASCENDING)]),
            IndexModel([("store_id", ASCENDING), ("is_active", ASCENDING)]),
            IndexModel([("expires_at", ASCENDING)], sparse=True),
        ]
    )

    await db["audit_logs"].create_indexes(
        [
            IndexModel([("action", ASCENDING)]),
            IndexModel([("actor_id", ASCENDING)]),
            IndexModel([("resource_type", ASCENDING)]),
            IndexModel([("tenant_id", ASCENDING)]),
            IndexModel([("outcome", ASCENDING)]),
            IndexModel([("timestamp", DESCENDING)]),
            IndexModel([("tenant_id", ASCENDING), ("timestamp", DESCENDING)]),
            IndexModel([("actor_id", ASCENDING), ("timestamp", DESCENDING)]),
            IndexModel([("action", ASCENDING), ("outcome", ASCENDING)]),
        ]
    )

    await db["customers"].create_indexes(
        [
            IndexModel([("store_id", ASCENDING), ("external_id", ASCENDING)], unique=True),
            IndexModel([("store_id", ASCENDING), ("email", ASCENDING)]),
        ]
    )

    await db["knowledge_versions"].create_indexes(
        [
            IndexModel([("store_id", ASCENDING)]),
            IndexModel([("store_id", ASCENDING), ("status", ASCENDING)]),
            IndexModel([("store_id", ASCENDING), ("version_number", DESCENDING)]),
        ]
    )

    await db["widget_installations"].create_indexes(
        [
            IndexModel([("public_key_hash", ASCENDING)], unique=True),
            IndexModel([("widget_id", ASCENDING)], unique=True),
            IndexModel([("store_id", ASCENDING)]),
            IndexModel([("store_id", ASCENDING), ("status", ASCENDING)]),
            IndexModel([("status", ASCENDING)]),
        ]
    )

    await db["store_plan_policies"].create_indexes(
        [
            IndexModel([("store_id", ASCENDING)], unique=True),
        ]
    )

    await db["runtime_logs"].create_indexes(
        [
            IndexModel([("store_id", ASCENDING), ("billing_period", ASCENDING), ("timestamp", DESCENDING)]),
            IndexModel([("store_id", ASCENDING), ("provider", ASCENDING), ("timestamp", DESCENDING)]),
            IndexModel([("store_id", ASCENDING), ("model", ASCENDING), ("timestamp", DESCENDING)]),
        ]
    )

    logger.info("Database indexes successfully created.")
