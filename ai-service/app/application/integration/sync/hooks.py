import logging
from typing import Any

logger = logging.getLogger(__name__)


def enqueue_sync_record(
    store_id: str,
    organization_id: str,
    entity_type: str,
    record: dict[str, Any],
) -> None:
    """Fire-and-forget vector sync for one commerce record (CRUD hook)."""
    try:
        from app.workers.embedding.tasks import sync_entity_record_task

        sync_entity_record_task.delay(store_id, organization_id, entity_type, record)
    except Exception:
        logger.exception(
            "Failed to enqueue vector sync for %s record (store=%s)",
            entity_type,
            store_id,
        )


def enqueue_delete_record(store_id: str, entity_type: str, entity_key: str) -> None:
    """Fire-and-forget removal of one record's vector points (CRUD hook)."""
    try:
        from app.workers.embedding.tasks import delete_entity_record_task

        delete_entity_record_task.delay(store_id, entity_type, entity_key)
    except Exception:
        logger.exception(
            "Failed to enqueue vector removal for %s record (store=%s)",
            entity_type,
            store_id,
        )
