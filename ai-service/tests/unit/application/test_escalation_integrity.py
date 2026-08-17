"""Domain 3 regression tests: escalation durability, truthfulness, and idempotency.

Covers the three production incidents:
- B11: `replace_one`/`ReplaceOne` replacements must never carry `_id` (Mongo error 66).
- B10: persistence failures must never produce a false "handing over" claim.
- B9: ticket_id must propagate through the coordinator serializer and the workflow
  must not re-escalate (duplicate tickets) once a durable ticket exists.
"""

import types
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from app.agents.coordinator.nodes import execute_sub_agent_node
from app.agents.escalation.nodes import format_escalation_response_node, notify_customer_node, notify_human_node
from app.agents.support.nodes import escalate_if_needed_node, generate_response_node
from app.application.ticket.dto.ticket_dto import TicketCreateDTO
from app.application.ticket.services.ticket_service import TicketService
from app.core.exceptions import ConcurrencyException
from app.domain.ticket.entities.ticket_analysis import TicketAnalysis
from app.infrastructure.mongodb.repositories.ticket_repository import TicketRepository
from app.workflows.conversation.graph import evaluate_escalation_node


def make_ticket(
    *,
    ticket_id: str = "tkt-1",
    conversation_id: str | None = None,
    store_id: str = "s1",
    status: str = "open",
) -> TicketAnalysis:
    return TicketAnalysis(
        id=str(ObjectId()),
        ticket_id=ticket_id,
        store_id=store_id,
        customer_id="c1",
        sentiment="negative",
        category="billing",
        summary="test",
        priority="high",
        status=status,
        suggested_response="ok",
        resolution_type="unresolved",
        analyzed_at=datetime.now(UTC),
        conversation_id=conversation_id,
    )


@pytest.fixture
def fake_collection():
    calls = []

    async def replace_one(filter_, replacement, **kwargs):
        calls.append({"filter": filter_, "replacement": replacement, "kwargs": kwargs})

    async def bulk_write(operations, **kwargs):
        calls.append({"operations": operations, "kwargs": kwargs})
        return types.SimpleNamespace(modified_count=len(operations))

    async def find_one(*args, **kwargs):
        return None

    fake = types.SimpleNamespace()
    fake.replace_one = replace_one
    fake.bulk_write = bulk_write
    fake.find_one = find_one
    fake.find = find_one
    return fake, calls


@pytest.fixture
def ticket_repo():
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.find_open_by_conversation = AsyncMock(return_value=None)
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


@pytest.mark.asyncio
async def test_ticket_update_replacement_never_contains_id(fake_collection):
    collection, calls = fake_collection
    repo = TicketRepository.__new__(TicketRepository)
    repo.collection = collection
    repo._event_bus = None
    from app.infrastructure.mongodb.documents.ticket_document import TicketAnalysisDocument

    repo.doc_class = TicketAnalysisDocument
    entity = make_ticket()

    await repo.update(entity)

    assert len(calls) == 1
    replacement = calls[0]["replacement"]
    assert "_id" not in replacement, f"replacement must not alter _id, got: {replacement}"
    assert calls[0]["filter"] == {"_id": ObjectId(entity.id)}
    assert calls[0]["kwargs"].get("upsert") is True
    assert replacement["ticket_id"] == "tkt-1"


@pytest.mark.asyncio
async def test_ticket_bulk_update_replacements_never_contain_id(fake_collection):
    collection, calls = fake_collection
    repo = TicketRepository.__new__(TicketRepository)
    repo.collection = collection
    repo._event_bus = None
    from app.infrastructure.mongodb.documents.ticket_document import TicketAnalysisDocument

    repo.doc_class = TicketAnalysisDocument

    await repo.bulk_update([make_ticket(ticket_id="tkt-a"), make_ticket(ticket_id="tkt-b")])

    assert len(calls) == 1
    ops = calls[0]["operations"]
    assert len(ops) == 2
    for op in ops:
        assert "_id" not in op._doc, f"replacement must not alter _id, got: {op._doc}"
        assert "_id" in op._filter and isinstance(op._filter["_id"], ObjectId)


@pytest.mark.asyncio
async def test_create_ticket_reuses_open_ticket_for_same_conversation(ticket_repo, ticket_service, sentiment_service):
    existing = make_ticket(ticket_id="tkt-existing", conversation_id="conv-1")
    ticket_repo.find_open_by_conversation.return_value = existing

    dto = TicketCreateDTO(
        store_id="s1",
        customer_id="c1",
        conversation_id="conv-1",
        messages=["help"],
    )
    result = await ticket_service.create_ticket(dto)

    assert result.ticket_id == "tkt-existing"
    ticket_repo.find_open_by_conversation.assert_awaited_once_with("s1", "conv-1")
    ticket_repo.create.assert_not_awaited()
    sentiment_service.analyze.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_ticket_persists_conversation_id(ticket_repo, ticket_service):
    ticket_repo.create.side_effect = lambda e: e

    dto = TicketCreateDTO(
        store_id="s1",
        customer_id="c1",
        conversation_id="conv-1",
        messages=["help"],
    )
    await ticket_service.create_ticket(dto)

    created = ticket_repo.create.call_args[0][0]
    assert created.conversation_id == "conv-1"


@pytest.mark.asyncio
async def test_create_ticket_does_not_reuse_across_conversations(ticket_repo, ticket_service):
    ticket_repo.create.side_effect = lambda e: e

    await ticket_service.create_ticket(
        TicketCreateDTO(store_id="s1", customer_id="c1", conversation_id="conv-a", messages=["m"])
    )
    await ticket_service.create_ticket(
        TicketCreateDTO(store_id="s1", customer_id="c1", conversation_id="conv-b", messages=["m"])
    )

    assert ticket_repo.create.await_count == 2
    assert ticket_repo.create.await_args_list[0][0][0].conversation_id == "conv-a"
    assert ticket_repo.create.await_args_list[1][0][0].conversation_id == "conv-b"


@pytest.mark.asyncio
async def test_create_ticket_race_duplicate_reuses_existing(ticket_repo, ticket_service):
    ticket_repo.create.side_effect = ConcurrencyException("unique key violation")
    existing = make_ticket(ticket_id="tkt-race", conversation_id="conv-1")
    ticket_repo.find_open_by_conversation.side_effect = [None, existing]

    result = await ticket_service.create_ticket(
        TicketCreateDTO(store_id="s1", customer_id="c1", conversation_id="conv-1", messages=["m"])
    )

    assert result.ticket_id == "tkt-race"
    assert ticket_repo.find_open_by_conversation.await_count == 2


@pytest.mark.asyncio
async def test_create_ticket_race_without_duplicate_re_raises(ticket_repo, ticket_service):
    ticket_repo.create.side_effect = ConcurrencyException("unique key violation")
    ticket_repo.find_open_by_conversation.return_value = None

    with pytest.raises(ConcurrencyException):
        await ticket_service.create_ticket(
            TicketCreateDTO(store_id="s1", customer_id="c1", conversation_id="conv-1", messages=["m"])
        )


def support_state(**overrides):
    state = {
        "user_query": "I want to talk to a human.",
        "store_id": "s1",
        "customer_id": "c1",
        "conversation_id": "conv-1",
        "issue_category": "general",
        "history": [],
        "verified_facts": [],
        "resolution_steps": [],
        "escalation_needed": False,
        "ticket_id": None,
        "error": None,
        "persistence_success": True,
    }
    state.update(overrides)
    return state


@pytest.mark.asyncio
async def test_support_node_failed_persistence_never_claims_handoff(ticket_repo, sentiment_service):
    failing = TicketService(ticket_repository=ticket_repo, sentiment_service=sentiment_service)
    ticket_repo.create.side_effect = RuntimeError("db down")
    escalation_agent = AsyncMock()

    result = await escalate_if_needed_node(support_state(), escalation_agent=escalation_agent, ticket_service=failing)

    assert result["escalation_needed"] is True
    assert result["ticket_id"] is None
    assert result["persistence_success"] is False
    assert result["error"] is not None
    escalation_agent.run.assert_not_awaited()


@pytest.mark.asyncio
async def test_support_node_success_marks_persistence(ticket_repo, sentiment_service):
    ok = TicketService(ticket_repository=ticket_repo, sentiment_service=sentiment_service)
    ticket_repo.create.side_effect = lambda e: e
    escalation_agent = AsyncMock()
    escalation_agent.run.return_value = MagicMock(
        ticket_id="tkt-1",
        priority="p2",
        assigned_to="support",
        eta=None,
    )

    result = await escalate_if_needed_node(support_state(), escalation_agent=escalation_agent, ticket_service=ok)

    assert result["persistence_success"] is True
    assert result["ticket_id"] == "tkt-1"
    escalation_agent.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_response_honest_when_persistence_failed():
    result = await generate_response_node(support_state(escalation_needed=True, persistence_success=False), llm=None)

    content = result["response"].rationale or ""
    assert "handing this over" not in content
    assert "trouble submitting" in content


@pytest.mark.asyncio
async def test_generate_response_handoff_only_when_persisted():
    result = await generate_response_node(
        support_state(escalation_needed=True, persistence_success=True, assigned_to="support"),
        llm=None,
    )

    assert "handing this over" in (result["response"].rationale or "")


def _escalation_result():
    return MagicMock(
        escalation_needed=True,
        ticket_id="tkt-9",
        rationale="Customer requested human support.",
        priority="p2",
        assigned_to="support",
        eta=None,
        persistence_success=True,
        error=None,
    )


@pytest.mark.asyncio
async def test_coordinator_propagates_ticket_id_top_level():
    async def runner(**kwargs):
        return _escalation_result()

    state = {
        "user_input": "I want to talk to a human.",
        "store_id": "s1",
        "customer_id": "c1",
        "conversation_id": "conv-1",
        "sub_agent": "support",
        "intent": "support",
        "confidence": 0.9,
        "metadata": {},
        "context": {},
    }
    result = await execute_sub_agent_node(state, sub_agents={"support": runner})

    response = result["response"]
    assert response["escalation_needed"] is True
    assert response["ticket_id"] == "tkt-9"
    assert response["escalation_reason"] == "Customer requested human support."
    assert response["persistence_success"] is True
    assert response["result"]["ticket_id"] == "tkt-9"
    assert response["result"]["priority"] == "p2"
    assert response["result"]["persistence_success"] is True


@pytest.mark.asyncio
async def test_workflow_keeps_durable_escalation_without_re_run():
    escalation_agent = AsyncMock()
    state = {
        "user_input": "hello",
        "store_id": "s1",
        "customer_id": "c1",
        "conversation_id": "conv-1",
        "messages": [{"role": "user", "content": "hello"}],
        "context": {},
        "response": {
            "content": "I'll check that for you.",
            "intent": "support",
            "escalation_needed": True,
            "ticket_id": "tkt-9",
            "escalation_reason": "Customer requested human support.",
            "persistence_success": True,
        },
        "agent_trace": [],
    }

    result = await evaluate_escalation_node(state, escalation_agent=escalation_agent)

    assert result["escalation"]["should_escalate"] is True
    assert result["escalation"]["ticket_id"] == "tkt-9"
    escalation_agent.run.assert_not_awaited()


@pytest.mark.asyncio
async def test_workflow_does_not_claim_unpersisted_escalation():
    escalation_agent = AsyncMock()
    state = {
        "user_input": "hello",
        "store_id": "s1",
        "customer_id": "c1",
        "conversation_id": "conv-1",
        "messages": [{"role": "user", "content": "hello"}],
        "context": {},
        "response": {
            "content": "I'd like to have a specialist follow up with you, but I'm having trouble submitting the request.",
            "intent": "support",
            "escalation_needed": True,
            "ticket_id": None,
            "escalation_reason": "Customer requested human support.",
            "persistence_success": False,
            "error": "Ticket creation failed: db down",
        },
        "agent_trace": [],
    }

    result = await evaluate_escalation_node(state, escalation_agent=escalation_agent)

    assert result["escalation"]["should_escalate"] is False
    assert result["escalation"]["ticket_id"] is None
    escalation_agent.run.assert_not_awaited()


@pytest.mark.asyncio
async def test_workflow_recognizes_coordinator_result_dict_escalation():
    escalation_agent = AsyncMock()
    state = {
        "user_input": "hello",
        "store_id": "s1",
        "customer_id": "c1",
        "conversation_id": "conv-1",
        "messages": [{"role": "user", "content": "hello"}],
        "context": {},
        "response": {
            "content": "I'll check that for you.",
            "intent": "support",
            "result": {"escalation_needed": True, "ticket_id": "tkt-9", "persistence_success": True},
        },
        "agent_trace": [],
    }

    result = await evaluate_escalation_node(state, escalation_agent=escalation_agent)

    assert result["escalation"]["should_escalate"] is True
    assert result["escalation"]["ticket_id"] == "tkt-9"
    escalation_agent.run.assert_not_awaited()


@pytest.mark.asyncio
async def test_workflow_downgrades_when_escalation_agent_not_durable():
    escalation_agent = AsyncMock()
    escalation_agent.run.return_value = MagicMock(
        ticket_id=None,
        priority=None,
        assigned_to=None,
        eta=None,
        notification_message=None,
        persistence_success=False,
        error="Failed to escalate ticket: db down",
    )
    state = {
        "user_input": "I want to talk to a human.",
        "store_id": "s1",
        "customer_id": "c1",
        "conversation_id": "conv-1",
        "messages": [{"role": "user", "content": "I want to talk to a human."}],
        "context": {},
        "response": {"content": "ok", "intent": "support"},
        "agent_trace": [],
    }

    result = await evaluate_escalation_node(state, escalation_agent=escalation_agent)

    assert result["escalation"]["should_escalate"] is False
    assert result["response"].get("escalation_needed") is not True
    assert "handing" not in (result["response"].get("content") or "")


@pytest.mark.asyncio
async def test_notify_human_failure_marks_persistence_false():
    ticket_service = AsyncMock()
    ticket_service.create_ticket.side_effect = RuntimeError("db down")

    result = await notify_human_node(
        {"store_id": "s1", "customer_id": "c1", "conversation_id": "conv-1", "ticket_id": None},
        ticket_service=ticket_service,
    )

    assert result["persistence_success"] is False
    assert result["error"] is not None


@pytest.mark.asyncio
async def test_notify_human_success_marks_persistence_true():
    ticket_service = AsyncMock()
    ticket_service.create_ticket.return_value = MagicMock(ticket_id="tkt-1")

    result = await notify_human_node(
        {"store_id": "s1", "customer_id": "c1", "conversation_id": "conv-1", "ticket_id": None},
        ticket_service=ticket_service,
    )

    assert result["persistence_success"] is True
    assert result["ticket_id"] == "tkt-1"


@pytest.mark.asyncio
async def test_format_response_strips_claims_when_not_persisted():
    state = {
        "user_query": "q",
        "store_id": "s1",
        "customer_id": "c1",
        "ticket_id": "tkt-1",
        "notification_message": "Your request has been escalated (ticket tkt-1).",
        "error": "Failed to escalate ticket: db down",
        "persistence_success": False,
    }
    result = await format_escalation_response_node(state)

    response = result["response"]
    assert response.persistence_success is False
    assert response.ticket_id is None
    assert response.notification_message is None


@pytest.mark.asyncio
async def test_notify_customer_skipped_when_not_persisted():
    notification_service = AsyncMock()
    result = await notify_customer_node(
        {"store_id": "s1", "customer_id": "c1", "persistence_success": False},
        notification_service=notification_service,
    )

    assert result["error"] is not None
    notification_service.create_notification.assert_not_awaited()
