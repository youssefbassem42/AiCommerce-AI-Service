from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.application.ticket.dto.ticket_dto import TicketCreateDTO
from app.application.ticket.services.ticket_service import TicketService
from app.domain.ticket.entities.ticket_analysis import TicketAnalysis, TicketMessage


@pytest.fixture
def ticket_repo():
    repo = AsyncMock()
    repo.find_by_ticket_id = AsyncMock()
    repo.update = AsyncMock()
    repo.find_open_by_conversation = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def sentiment_service():
    ss = AsyncMock()
    ss.analyze.return_value.sentiment = "neutral"
    ss.analyze.return_value.confidence = 0.8
    ss.analyze.return_value.category = "general"
    ss.analyze.return_value.priority = "medium"
    ss.analyze.return_value.summary = "Summary"
    ss.analyze.return_value.suggested_response = "Suggested"
    return ss


@pytest.fixture
def ticket_service(ticket_repo, sentiment_service):
    return TicketService(
        ticket_repository=ticket_repo,
        sentiment_service=sentiment_service,
    )


def make_ticket(**overrides):
    defaults = {
        "id": "ticket-1",
        "ticket_id": "ticket-1",
        "store_id": "s1",
        "customer_id": "c1",
        "sentiment": "neutral",
        "category": "general",
        "summary": "Summary",
        "priority": "medium",
        "status": "open",
        "suggested_response": "Suggested response",
        "resolution_type": "unresolved",
        "messages": [
            TicketMessage(
                id="m1",
                sender="customer",
                content="Hello",
                created_at=datetime.now(UTC),
            )
        ],
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return TicketAnalysis(**defaults)


class TestTicketServiceExtensions:
    async def test_add_message_appends_to_thread(self, ticket_repo, ticket_service):
        ticket_repo.find_by_ticket_id.return_value = make_ticket()
        ticket_repo.update.side_effect = lambda entity: entity

        dto = await ticket_service.add_message("ticket-1", sender="agent", content="We are on it")

        assert dto is not None
        assert len(dto.messages) == 2
        assert dto.messages[-1].sender == "agent"
        assert dto.messages[-1].content == "We are on it"
        updated = ticket_repo.update.call_args[0][0]
        assert updated.messages[-1].sender == "agent"

    async def test_add_message_rejects_invalid_sender(self, ticket_service):
        with pytest.raises(ValueError):
            await ticket_service.add_message("ticket-1", sender="alien", content="hi")

    async def test_add_message_missing_ticket_returns_none(self, ticket_repo, ticket_service):
        ticket_repo.find_by_ticket_id.return_value = None
        assert await ticket_service.add_message("missing", sender="agent", content="hi") is None

    async def test_resolve_ticket_sets_status_and_resolution(self, ticket_repo, ticket_service):
        ticket_repo.find_by_ticket_id.return_value = make_ticket()
        ticket_repo.update.side_effect = lambda entity: entity

        dto = await ticket_service.resolve_ticket("ticket-1", resolution_type="human", message="Done")

        assert dto is not None
        assert dto.status == "resolved"
        assert dto.resolution_type == "human"
        updated = ticket_repo.update.call_args[0][0]
        assert updated.messages[-1].sender == "system"
        assert updated.messages[-1].content == "Done"

    async def test_resolve_ticket_invalid_resolution_type_falls_back(self, ticket_repo, ticket_service):
        ticket_repo.find_by_ticket_id.return_value = make_ticket()
        ticket_repo.update.side_effect = lambda entity: entity

        dto = await ticket_service.resolve_ticket("ticket-1", resolution_type="banana")

        assert dto.resolution_type == "human"

    async def test_escalate_ticket_sets_priority_team_eta(self, ticket_repo, ticket_service):
        ticket_repo.find_by_ticket_id.return_value = make_ticket()
        ticket_repo.update.side_effect = lambda entity: entity
        eta = datetime.now(UTC) + timedelta(hours=8)

        dto = await ticket_service.escalate_ticket(
            "ticket-1",
            priority="p2",
            assigned_to="finance",
            eta=eta,
            message="Escalated to finance",
        )

        assert dto is not None
        assert dto.resolution_type == "escalated"
        assert dto.priority == "p2"
        assert dto.assigned_to == "finance"
        assert dto.eta == eta
        updated = ticket_repo.update.call_args[0][0]
        assert updated.status == "in_progress"

    async def test_escalate_missing_ticket_returns_none(self, ticket_repo, ticket_service):
        ticket_repo.find_by_ticket_id.return_value = None
        assert await ticket_service.escalate_ticket("missing") is None

    async def test_has_open_ticket_true_when_found(self, ticket_repo, ticket_service):
        ticket_repo.find_open_by_customer.return_value = make_ticket()
        assert await ticket_service.has_open_ticket("s1", "c1") is True

    async def test_has_open_ticket_false_when_none(self, ticket_repo, ticket_service):
        ticket_repo.find_open_by_customer.return_value = None
        assert await ticket_service.has_open_ticket("s1", "c1") is False

    async def test_create_ticket_persists_initial_messages(self, ticket_repo, sentiment_service, ticket_service):
        ticket_repo.create.return_value = make_ticket()
        dto = await ticket_service.create_ticket(
            TicketCreateDTO(
                store_id="s1",
                customer_id="c1",
                messages=["first line", "second line"],
            )
        )
        assert dto is not None
        created = ticket_repo.create.call_args[0][0]
        assert isinstance(created.messages, list)
        assert all(isinstance(m, TicketMessage) for m in created.messages)
        assert created.messages[0].content == "first line"
        assert created.messages[0].sender == "customer"
