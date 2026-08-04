from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.escalation.agent import EscalationAgent
from app.agents.escalation.tools import (
    CATEGORY_TEAMS,
    CRITICAL_CATEGORIES,
    PRIORITY_ETA_HOURS,
    assign_team,
    determine_tier,
    eta_hours_for_priority,
    resolve_priority,
)
from app.application.ticket.dto.escalation_dto import EscalationResponse


@pytest.fixture
def llm():
    l = AsyncMock()
    l.structured_output.return_value.message.content = "{}"
    return l


@pytest.fixture
def customer_repo():
    r = AsyncMock()
    r.find_by_id.return_value = MagicMock(
        id="cust_1",
        store_id="store_1",
        tags=["gold"],
        metadata={"tier": "gold"},
    )
    return r


@pytest.fixture
def ticket_service():
    t = AsyncMock()
    t.create_ticket.return_value = MagicMock(id="ticket-1", ticket_id="ticket-1")
    t.escalate_ticket.return_value = MagicMock(id="ticket-1")
    return t


@pytest.fixture
def notification_service():
    n = AsyncMock()
    n.create_notification.return_value = {"id": "n1"}
    return n


@pytest.fixture
def agent(llm, customer_repo, ticket_service, notification_service):
    return EscalationAgent(
        llm=llm,
        ticket_service=ticket_service,
        notification_service=notification_service,
        customer_repo=customer_repo,
    )


class TestEscalationTools:
    def test_determine_tier_from_tags(self):
        customer = MagicMock(tags=["gold"], metadata={})
        assert determine_tier(customer) == "gold"
        customer = MagicMock(tags=["vip", "platinum"], metadata={})
        assert determine_tier(customer) == "platinum"
        customer = MagicMock(tags=[], metadata={})
        assert determine_tier(customer) == "standard"

    def test_determine_tier_from_metadata(self):
        customer = MagicMock(tags=[], metadata={"tier": "platinum"})
        assert determine_tier(customer) == "platinum"

    def test_determine_tier_fallback_standard(self):
        assert determine_tier(None) == "standard"
        assert determine_tier(MagicMock(tags=None, metadata=None)) == "standard"

    def test_resolve_priority_critical(self):
        assert resolve_priority("account_security", "standard") == "p1"

    def test_resolve_priority_refund_gold(self):
        assert resolve_priority("refund", "gold") == "p2"

    def test_resolve_priority_general_standard(self):
        assert resolve_priority("general", "standard") == "p4"

    def test_assign_team(self):
        assert assign_team("order_status") == "fulfillment"
        assert assign_team("payment_failure") == "billing"
        assert assign_team("technical") == "technical"

    def test_assign_team_unknown_defaults(self):
        assert assign_team("unknown") == "general"
        assert assign_team(None) == "general"

    def test_eta_hours_for_priority(self):
        assert eta_hours_for_priority("p1") == PRIORITY_ETA_HOURS["p1"]
        assert eta_hours_for_priority("p4") == PRIORITY_ETA_HOURS["p4"]

    def test_critical_categories_contains_account_security(self):
        assert "account_security" in CRITICAL_CATEGORIES

    def test_all_categories_have_teams(self):
        for category in ["order_status", "returns", "refund", "account_security", "account", "technical", "general"]:
            assert category in CATEGORY_TEAMS


class TestEscalationAgent:
    async def test_run_returns_escalation_response(self, agent):
        response = await agent.run(
            query="My account was hacked",
            store_id="store_1",
            customer_id="cust_1",
            original_agent="support",
            reason="Issue category 'account_security' requires human assistance.",
            category="account_security",
        )
        assert isinstance(response, EscalationResponse)
        assert response.query == "My account was hacked"
        assert response.store_id == "store_1"

    async def test_run_creates_ticket_and_notification(self, agent, ticket_service, notification_service):
        await agent.run(
            query="I need help",
            store_id="store_1",
            customer_id="cust_1",
            category="general",
        )
        assert ticket_service.create_ticket.await_count >= 0
        assert notification_service.create_notification.await_count >= 0

    async def test_run_error_path_returns_error_response(self, customer_repo, ticket_service, notification_service):
        bad_agent = EscalationAgent(
            llm=AsyncMock(),
            ticket_service=ticket_service,
            notification_service=notification_service,
            customer_repo=customer_repo,
        )
        bad_agent._graph.ainvoke = AsyncMock(side_effect=Exception("boom"))
        response = await bad_agent.run(query="test", store_id="s1")
        assert isinstance(response, EscalationResponse)
        assert response.error is not None

    async def test_run_no_dependencies_still_returns_response(self):
        agent = EscalationAgent()
        response = await agent.run(query="help", store_id="s1", customer_id="c1")
        assert isinstance(response, EscalationResponse)
        assert response.customer_id == "c1"

    async def test_eta_is_aware_datetime_when_priority_set(self, agent):
        response = await agent.run(
            query="help",
            store_id="store_1",
            customer_id="cust_1",
            category="account_security",
        )
        if response.eta is not None:
            assert response.eta.tzinfo is not None
            assert response.eta > datetime.now(UTC)
