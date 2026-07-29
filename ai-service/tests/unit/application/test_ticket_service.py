from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.ticket.dto.ticket_dto import TicketCreateDTO, TicketStatusUpdateDTO
from app.application.ticket.services.ticket_service import TicketService
from app.domain.ticket.entities.ticket_analysis import TicketAnalysis


@pytest.fixture
def ticket_repo():
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.update = AsyncMock()
    repo.paginate = AsyncMock(return_value=([], 0))
    return repo


@pytest.fixture
def sentiment_service():
    ss = AsyncMock()
    ss.analyze.return_value.sentiment = "negative"
    ss.analyze.return_value.confidence = 0.9
    ss.analyze.return_value.category = "billing"
    ss.analyze.return_value.priority = "high"
    ss.analyze.return_value.summary = "Test summary"
    ss.analyze.return_value.suggested_response = "Test response"
    return ss


@pytest.fixture
def ticket_service(ticket_repo, sentiment_service):
    return TicketService(
        ticket_repository=ticket_repo,
        sentiment_service=sentiment_service,
    )


class TestTicketService:
    async def test_create_ticket_with_minimal_data(self, ticket_service, ticket_repo, sentiment_service):
        ticket_repo.create.return_value = TicketAnalysis(
            id="ticket-1", ticket_id="ticket-1",
            store_id="s1", customer_id="c1",
            sentiment="negative", category="billing",
            summary="Test summary", priority="high", status="open",
            suggested_response="Test response",
        )

        result = await ticket_service.create_ticket(
            TicketCreateDTO(
                store_id="s1", customer_id="c1",
                messages=["I have a problem"],
            )
        )
        assert result.store_id == "s1"
        assert result.customer_id == "c1"
        assert result.sentiment == "negative"
        assert result.status == "open"

    async def test_create_ticket_with_conversation_context(self, ticket_service, ticket_repo):
        conv_service = AsyncMock()
        conv_service.get_conversation_history.return_value = []
        ticket_service._conversation_service = conv_service

        ticket_repo.create.return_value = TicketAnalysis(
            id="ticket-2", ticket_id="ticket-2",
            store_id="s1", customer_id="c1",
            sentiment="negative", category="shipping",
            summary="Shipping issue", priority="high", status="open",
            suggested_response="We'll check your shipment",
        )

        result = await ticket_service.create_ticket(
            TicketCreateDTO(
                store_id="s1", customer_id="c1",
                conversation_id="conv_1",
                messages=["Where is my order?"],
            )
        )
        assert result is not None
        conv_service.get_conversation_history.assert_called_once_with("conv_1")

    async def test_get_ticket_not_found(self, ticket_service, ticket_repo):
        ticket_repo.find_by_ticket_id.return_value = None
        result = await ticket_service.get_ticket("nonexistent")
        assert result is None

    async def test_list_tickets_empty(self, ticket_service, ticket_repo):
        ticket_repo.paginate.return_value = ([], 0)
        items, total = await ticket_service.list_tickets(store_id="s1")
        assert items == []
        assert total == 0

    async def test_list_tickets_with_filters(self, ticket_service, ticket_repo):
        ticket_repo.paginate.return_value = ([], 0)
        await ticket_service.list_tickets(
            store_id="s1", status="open", priority="high", sentiment="negative",
        )
        ticket_repo.paginate.assert_called_once()
        call_filters = ticket_repo.paginate.call_args[1]["filters"]
        assert call_filters["store_id"] == "s1"
        assert call_filters["status"] == "open"
        assert call_filters["priority"] == "high"
        assert call_filters["sentiment"] == "negative"

    async def test_update_status_not_found(self, ticket_service, ticket_repo):
        ticket_repo.find_by_id.return_value = None
        result = await ticket_service.update_status("nonexistent", TicketStatusUpdateDTO(status="resolved"))
        assert result is None

    async def test_update_status_success(self, ticket_service, ticket_repo):
        entity = TicketAnalysis(
            id="ticket-1", ticket_id="ticket-1",
            store_id="s1", customer_id="c1",
            sentiment="negative", category="billing",
            summary="issue", priority="high", status="open",
            suggested_response="response",
        )
        ticket_repo.find_by_id.return_value = entity
        ticket_repo.update.return_value = entity

        result = await ticket_service.update_status("ticket-1", TicketStatusUpdateDTO(status="resolved"))
        assert result is not None
        assert result.status == "resolved"

    async def test_create_ticket_when_customer_fetch_fails(self, ticket_service, ticket_repo, sentiment_service):
        customer_repo = AsyncMock()
        customer_repo.find_by_id.side_effect = Exception("DB connection error")
        ticket_service._customer_repo = customer_repo

        ticket_repo.create.return_value = TicketAnalysis(
            id="ticket-3", ticket_id="ticket-3",
            store_id="s1", customer_id="c1",
            sentiment="neutral", category="general",
            summary="Test", priority="low", status="open",
            suggested_response="OK",
        )

        result = await ticket_service.create_ticket(
            TicketCreateDTO(store_id="s1", customer_id="c1", messages=["hi"])
        )
        assert result is not None
        assert result.customer is None

    async def test_create_ticket_when_order_fetch_fails(self, ticket_service, ticket_repo, sentiment_service):
        order_repo = AsyncMock()
        order_repo.find_by_customer.side_effect = Exception("Order service down")
        ticket_service._order_repo = order_repo

        ticket_repo.create.return_value = TicketAnalysis(
            id="ticket-4", ticket_id="ticket-4",
            store_id="s1", customer_id="c1",
            sentiment="negative", category="billing",
            summary="Billing issue", priority="high", status="open",
            suggested_response="We'll fix it",
        )

        result = await ticket_service.create_ticket(
            TicketCreateDTO(store_id="s1", customer_id="c1", messages=["billing problem"])
        )
        assert result is not None
        assert result.recent_orders == []
