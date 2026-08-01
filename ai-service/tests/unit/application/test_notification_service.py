from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.ticket.services.notification_service import TicketNotificationService


class _AsyncCursor:
    """Sync-chainable fake cursor supporting async iteration."""

    def __init__(self, docs):
        self._docs = docs

    def sort(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self

    async def __aiter__(self):
        for doc in self._docs:
            yield doc


@pytest.fixture
def collection():
    return MagicMock()


@pytest.fixture
def service(collection):
    s = TicketNotificationService()
    s._collection = collection
    return s


class TestTicketNotificationService:
    async def test_create_notification_inserts_document(self, service, collection):
        collection.insert_one = AsyncMock()
        notification = await service.create_notification(
            ticket_id="t1",
            store_id="s1",
            customer_id="c1",
            message="A specialist will follow up.",
            eta=datetime.now(UTC) + timedelta(hours=8),
        )
        assert notification["ticket_id"] == "t1"
        assert notification["customer_id"] == "c1"
        assert notification["read"] is False
        collection.insert_one.assert_awaited_once()

    async def test_create_notification_raises_on_failure(self, service, collection):
        collection.insert_one = AsyncMock(side_effect=RuntimeError("db down"))
        with pytest.raises(RuntimeError):
            await service.create_notification(
                ticket_id="t1",
                store_id="s1",
                customer_id="c1",
                message="hello",
            )

    async def test_list_notifications_maps_id(self, service, collection):
        collection.find.return_value = _AsyncCursor(
            [
                {"_id": "n1", "ticket_id": "t1", "message": "hi", "read": False},
                {"_id": "n2", "ticket_id": "t1", "message": "bye", "read": True},
            ]
        )

        results = await service.list_notifications(ticket_id="t1")

        assert len(results) == 2
        assert results[0]["id"] == "n1"
        assert "_id" not in results[0]
        collection.find.assert_called_once_with({"ticket_id": "t1"})

    async def test_list_notifications_filters_unread(self, service, collection):
        collection.find.return_value = _AsyncCursor([])

        await service.list_notifications(customer_id="c1", unread_only=True)

        collection.find.assert_called_once_with({"customer_id": "c1", "read": False})

    async def test_mark_read_updates_document(self, service, collection):
        collection.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
        assert await service.mark_read("n1") is True
        collection.update_one.assert_awaited_once()

    async def test_mark_read_missing_returns_false(self, service, collection):
        collection.update_one = AsyncMock(return_value=MagicMock(matched_count=0))
        assert await service.mark_read("n1") is False

    async def test_mark_all_read_returns_count(self, service, collection):
        collection.update_many = AsyncMock(return_value=MagicMock(modified_count=3))
        assert await service.mark_all_read("c1") == 3
        collection.update_many.assert_awaited_once()
        assert collection.update_many.call_args[0][0] == {"customer_id": "c1", "read": False}
        assert collection.update_many.call_args[0][1]["$set"]["read"] is True
