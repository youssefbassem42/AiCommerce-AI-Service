import logging
from datetime import UTC, datetime
from uuid import uuid4

from app.infrastructure.mongodb.collections import get_ticket_notifications_collection

logger = logging.getLogger(__name__)


class TicketNotificationService:
    """Stores customer-facing ticket notifications (pull model)."""

    def __init__(self):
        self._collection = get_ticket_notifications_collection()

    async def create_notification(
        self,
        ticket_id: str,
        store_id: str,
        customer_id: str,
        message: str,
        eta: datetime | None = None,
    ) -> dict:
        """Create a notification for the customer about a ticket update."""
        doc = {
            "_id": str(uuid4()),
            "ticket_id": ticket_id,
            "store_id": store_id,
            "customer_id": customer_id,
            "message": message,
            "eta": eta,
            "read": False,
            "created_at": datetime.now(UTC),
        }
        try:
            await self._collection.insert_one(doc)
            return dict(doc)
        except Exception as e:
            logger.error("Failed to create ticket notification: %s", e, exc_info=True)
            raise

    async def list_notifications(
        self,
        ticket_id: str | None = None,
        customer_id: str | None = None,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[dict]:
        """List notifications for a ticket and/or customer, newest first."""
        filters: dict = {}
        if ticket_id:
            filters["ticket_id"] = ticket_id
        if customer_id:
            filters["customer_id"] = customer_id
        if unread_only:
            filters["read"] = False

        cursor = self._collection.find(filters).sort("created_at", -1).limit(limit)
        results = []
        async for doc in cursor:
            if "_id" in doc:
                doc["id"] = str(doc.pop("_id"))
            results.append(doc)
        return results

    async def mark_read(self, notification_id: str) -> bool:
        """Mark a notification as read. Returns True if it existed."""
        result = await self._collection.update_one(
            {"_id": notification_id},
            {"$set": {"read": True, "read_at": datetime.now(UTC)}},
        )
        return result.matched_count > 0

    async def mark_all_read(self, customer_id: str) -> int:
        """Mark all notifications for a customer as read."""
        result = await self._collection.update_many(
            {"customer_id": customer_id, "read": False},
            {"$set": {"read": True, "read_at": datetime.now(UTC)}},
        )
        return result.modified_count
