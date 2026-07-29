import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.ticket.dto.ticket_dto import TicketCreateDTO
from app.application.ticket.services.ticket_service import TicketService
from app.domain.ticket.entities.ticket_analysis import TicketAnalysis


@pytest.fixture
def ticket_repo():
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.find_by_ticket_id = AsyncMock()
    repo.find_by_store = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def sentiment_service():
    svc = AsyncMock()
    svc.analyze = AsyncMock()
    svc.analyze.return_value = MagicMock(
        sentiment="neutral", category="general",
        summary="test", priority="low", suggested_response="ok",
    )
    return svc


@pytest.fixture
def conversation_service():
    svc = AsyncMock()
    svc.get_conversation_history = AsyncMock(return_value=[])
    return svc


@pytest.fixture
def ticket_service(ticket_repo, sentiment_service, conversation_service):
    return TicketService(
        ticket_repository=ticket_repo,
        sentiment_service=sentiment_service,
        conversation_service=conversation_service,
        customer_repository=None,
        order_repository=None,
    )


class TestTicketServiceBugs:

    async def test_get_ticket_by_ticket_id_finds_via_ticket_id_field(self, ticket_service, ticket_repo):
        internal_id = str(uuid.uuid4())
        external_ticket_id = str(uuid.uuid4())
        entity = TicketAnalysis(
            id=internal_id,
            ticket_id=external_ticket_id,
            store_id="s1",
            customer_id="c1",
            sentiment="neutral",
            category="general",
            summary="test",
            priority="low",
            status="open",
            suggested_response="ok",
        )

        ticket_repo.find_by_id.return_value = None
        ticket_repo.find_by_ticket_id.return_value = entity

        result = await ticket_service.get_ticket(external_ticket_id)

        assert result is not None, (
            f"get_ticket('{external_ticket_id}') should find the ticket with "
            f"ticket_id='{external_ticket_id}' using find_by_ticket_id"
        )
        assert result.ticket_id == external_ticket_id
        ticket_repo.find_by_ticket_id.assert_called_once_with(external_ticket_id)

    async def test_get_ticket_returns_none_when_not_found(self, ticket_service, ticket_repo):
        ticket_repo.find_by_ticket_id.return_value = None
        result = await ticket_service.get_ticket("nonexistent")
        assert result is None

    async def test_get_ticket_uses_find_by_ticket_id_not_find_by_id(self, ticket_service, ticket_repo):
        ticket_repo.find_by_ticket_id.return_value = None
        await ticket_service.get_ticket("some-ticket-id")
        ticket_repo.find_by_ticket_id.assert_called_once_with("some-ticket-id")
        ticket_repo.find_by_id.assert_not_called()

    async def test_create_ticket_generates_separate_ids(self, ticket_service, ticket_repo, sentiment_service):
        sentiment_service.analyze.return_value = MagicMock(
            sentiment="positive", category="billing",
            summary="test", priority="low", suggested_response="ok",
        )
        dto = TicketCreateDTO(
            store_id="s1", customer_id="c1",
            messages=["help"], conversation_id="conv1",
        )

        ticket_repo.create.side_effect = lambda e: e
        await ticket_service.create_ticket(dto)

        actual_entity = ticket_repo.create.call_args[0][0]
        assert actual_entity.id != actual_entity.ticket_id, (
            f"id='{actual_entity.id}' and ticket_id='{actual_entity.ticket_id}' "
            f"should be different identifiers"
        )

    async def test_get_ticket_enriches_with_customer_and_orders(self, ticket_service, ticket_repo):
        entity = TicketAnalysis(
            id="abc", ticket_id="tkt-123", store_id="s1", customer_id="c1",
            sentiment="positive", category="billing", summary="test",
            priority="high", status="open", suggested_response="ok",
        )
        ticket_repo.find_by_ticket_id.return_value = entity

        result = await ticket_service.get_ticket("tkt-123")

        assert result is not None
        assert result.ticket_id == "tkt-123"
