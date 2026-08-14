"""Phase 0 exit criterion (widget path): a single message_id correlates the hops
store -> conversation -> retrieval -> orchestration -> response, and is echoed
back in the widget chat response."""

import json
import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.ai.dependencies import get_conversation_service, get_orchestration_service
from app.api.knowledge.retrieval_dependencies import get_retriever_service
from app.api.quota.dependencies import get_quota_enforcer
from app.api.rag.dependencies import get_summary_repository
from app.api.widget.dependencies import get_widget_bootstrap_service, get_widget_tenant_context
from app.application.dto.ai_dto import ChatResponse, MessageDTO, UsageDTO
from app.application.quota.plan_policy import PlanPolicy
from app.application.recommendation.dto.recommendation_dto import RecommendationResponse
from app.core.ai_settings import ai_settings


@pytest.fixture
def llm():
    from unittest.mock import AsyncMock, MagicMock

    provider = AsyncMock()

    def structured_side_effect(request, response_schema):
        prompt = request.messages[-1].content
        if "classify" in prompt.lower():
            content = '{"intent": "recommendation", "confidence": 0.9}'
        else:
            content = '{"key_topics": [], "customer_preferences": [], "store_facts": [], "sentiment": "neutral"}'
        response = MagicMock()
        response.message.content = content
        return response

    provider.structured_output.side_effect = structured_side_effect

    def chat_side_effect(request):
        response = MagicMock()
        response.message.content = "Fallback answer."
        return response

    provider.chat.side_effect = chat_side_effect
    return provider


@pytest.fixture
def recommendation_service():
    from unittest.mock import AsyncMock

    service = AsyncMock()
    service.recommend.return_value = RecommendationResponse(
        query="recommend a phone",
        store_id="store_1",
        customer_id="customer_1",
        rationale="Top pick: Phone X.",
    )
    return service


@pytest.fixture
def client(llm):
    from fastapi.testclient import TestClient

    from app.main import app

    class _Context:
        async def __call__(self):
            return SimpleNamespace(
                organization_id="org-1",
                store_id="store-1",
                language="en",
                scopes=["rag:chat", "recommendations:read"],
            )

    app.dependency_overrides[get_widget_tenant_context] = _Context()
    app.dependency_overrides[get_widget_bootstrap_service] = lambda: AsyncMock()

    def _plain_response():
        return ChatResponse(
            id="x",
            model=ai_settings.DEFAULT_MODEL,
            provider="orchestration",
            message=MessageDTO(role="assistant", content="Let me help you with that."),
            usage=UsageDTO(),
            latency_ms=10.0,
            metadata={"intent": "general", "sub_agent": None, "result": None},
        )

    orchestration = MagicMock()
    orchestration.chat = AsyncMock(return_value=_plain_response())
    retriever = MagicMock()
    retriever.search = AsyncMock(return_value=SimpleNamespace(results=[]))
    summary_repo = MagicMock()
    summary_repo.find_by_document_id = AsyncMock(return_value=[])
    conversation_service = MagicMock()
    conversation_service.get_or_create_conversation = AsyncMock()
    conversation_service.save_interaction = AsyncMock()
    conversation_service.update_conversation_context = AsyncMock()
    conversation_service.get_conversation_context = AsyncMock(return_value={})
    conversation_service.conversation_owned_by_store = AsyncMock(return_value=True)
    conversation_service.get_conversation_history = AsyncMock(return_value=[])

    now = datetime.now(UTC)
    fake_plan = PlanPolicy(
        id="store-1:bp",
        store_id="store-1",
        organization_id="org-1",
        subscription_status="Active",
        token_limit=1_000_000,
        allowed_models=(ai_settings.DEFAULT_MODEL,),
        allowed_providers=("openai",),
        billing_period="bp-1",
        period_start=now,
        period_end=now + timedelta(days=30),
        consumer_daily_message_limit_max=15,
        billing_period_days=30,
    )

    async def fake_run(**kw):
        return await kw["execute"]()

    fake_enforcer = SimpleNamespace(
        resolve_plan=AsyncMock(return_value=fake_plan),
        run=fake_run,
    )

    app.dependency_overrides[get_orchestration_service] = lambda: orchestration
    app.dependency_overrides[get_retriever_service] = lambda: retriever
    app.dependency_overrides[get_summary_repository] = lambda: summary_repo
    app.dependency_overrides[get_conversation_service] = lambda: conversation_service
    app.dependency_overrides[get_quota_enforcer] = lambda: fake_enforcer

    from app.api.widget.dependencies import get_context_builder
    from app.application.context.builder import ContextBuilder

    app.dependency_overrides[get_context_builder] = lambda: ContextBuilder(
        retriever_service=retriever,
        llm=llm,
        conversation_service=conversation_service,
        summary_repository=summary_repo,
    )

    from app.application.widget.token_service import WidgetTokenService

    token, _ = WidgetTokenService().create_session_token(
        widget_id="wid_abc",
        store_id="store-1",
        organization_id="org-1",
        scopes=["rag:chat", "recommendations:read"],
    )

    with TestClient(app) as test_client:
        test_client._orchestration = orchestration
        test_client._retriever = retriever
        test_client._conversation = conversation_service
        test_client._token = token
        yield test_client

    app.dependency_overrides.clear()


def _post(client, message, message_id=None):
    body = {"message": message}
    if message_id:
        body["message_id"] = message_id
    return client.post(
        "/api/v1/widget/chat",
        json=body,
        headers={"Authorization": f"Bearer {client._token}"},
    )


def _flow_events(caplog):
    events = []
    for record in caplog.records:
        if record.name == "ai.flow":
            events.append(json.loads(record.getMessage()))
    return events


class TestWidgetChatTrace:
    def test_message_id_correlates_all_hops_and_is_echoed(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="ai.flow"):
            resp = _post(client, "Do you have headphones?", message_id="msg-widget-1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["message_id"] == "msg-widget-1"
        assert isinstance(data["request_id"], str)

        events = _flow_events(caplog)
        event_names = [e["event"] for e in events]
        assert "widget.chat.start" in event_names
        assert "retrieval.complete" in event_names
        assert "orchestration.complete" in event_names
        assert "widget.chat.complete" in event_names

        for event in events:
            if "message_id" in event:
                assert event["message_id"] == "msg-widget-1"

        start = next(e for e in events if e["event"] == "widget.chat.start")
        assert start["store_id"] == "store-1"
        assert start["organization_id"] == "org-1"
        assert start["conversation_id"] is not None

        retrieval = next(e for e in events if e["event"] == "retrieval.complete")
        assert retrieval["chunk_count"] == 0

        complete = next(e for e in events if e["event"] == "widget.chat.complete")
        assert complete["response_type"] == "text"
        assert complete["product_count"] == 0

        client._retriever.search.assert_awaited_once()
        client._orchestration.chat.assert_awaited_once()

    def test_server_generates_message_id_when_absent(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="ai.flow"):
            resp = _post(client, "Do you have headphones?")

        assert resp.status_code == 200
        generated = resp.json()["message_id"]
        assert generated

        events = _flow_events(caplog)
        for event in events:
            if "message_id" in event:
                assert event["message_id"] == generated

    def test_greeting_short_circuit_still_emits_start_and_complete(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="ai.flow"):
            resp = _post(client, "Hello", message_id="msg-widget-2")

        assert resp.status_code == 200
        assert resp.json()["message_id"] == "msg-widget-2"

        events = _flow_events(caplog)
        event_names = [e["event"] for e in events]
        assert "widget.chat.start" in event_names
        assert "widget.chat.complete" in event_names
        complete = next(e for e in events if e["event"] == "widget.chat.complete")
        assert complete["message_id"] == "msg-widget-2"
        assert complete["gate"] == "greeting"
        client._retriever.search.assert_not_called()


class TestWidgetChatFullChainTrace:
    """Exit criterion: one message_id traces store -> conversation -> intent ->
    retrieval -> agent -> result -> response, and the final answer is explainable."""

    @pytest.fixture
    def client(self, llm, recommendation_service):
        from fastapi.testclient import TestClient

        from app.api.ai.dependencies import get_conversation_service, get_orchestration_service
        from app.api.knowledge.retrieval_dependencies import get_retriever_service
        from app.api.quota.dependencies import get_quota_enforcer
        from app.api.rag.dependencies import get_summary_repository
        from app.api.widget.dependencies import get_widget_bootstrap_service, get_widget_tenant_context
        from app.application.quota.plan_policy import PlanPolicy
        from app.application.services.orchestration_service import OrchestrationService
        from app.infrastructure.providers.factory import LLMProviderFactory
        from app.main import app

        class _Context:
            async def __call__(self):
                return SimpleNamespace(
                    organization_id="org-1",
                    store_id="store-1",
                    language="en",
                    scopes=["rag:chat", "recommendations:read"],
                )

        app.dependency_overrides[get_widget_tenant_context] = _Context()
        app.dependency_overrides[get_widget_bootstrap_service] = lambda: AsyncMock()

        retriever = MagicMock()
        retriever.search = AsyncMock(return_value=SimpleNamespace(results=[]))
        summary_repo = MagicMock()
        summary_repo.find_by_document_id = AsyncMock(return_value=[])
        conversation_service = MagicMock()
        conversation_service.get_or_create_conversation = AsyncMock()
        conversation_service.save_interaction = AsyncMock()
        conversation_service.update_conversation_context = AsyncMock()
        conversation_service.get_conversation_context = AsyncMock(return_value={})
        conversation_service.conversation_owned_by_store = AsyncMock(return_value=True)
        conversation_service.get_conversation_history = AsyncMock(return_value=[])

        now = datetime.now(UTC)
        fake_plan = PlanPolicy(
            id="store-1:bp",
            store_id="store-1",
            organization_id="org-1",
            subscription_status="Active",
            token_limit=1_000_000,
            allowed_models=(ai_settings.DEFAULT_MODEL,),
            allowed_providers=("openai",),
            billing_period="bp-1",
            period_start=now,
            period_end=now + timedelta(days=30),
            consumer_daily_message_limit_max=15,
            billing_period_days=30,
        )

        async def fake_run(**kw):
            return await kw["execute"]()

        fake_enforcer = SimpleNamespace(
            resolve_plan=AsyncMock(return_value=fake_plan),
            run=fake_run,
        )

        orchestration = OrchestrationService(
            provider_factory=LLMProviderFactory(),
            conversation_service=conversation_service,
            memory_repo=AsyncMock(),
            recommendation_service=recommendation_service,
            bundle_service=AsyncMock(),
            llm=llm,
        )

        app.dependency_overrides[get_orchestration_service] = lambda: orchestration
        app.dependency_overrides[get_retriever_service] = lambda: retriever
        app.dependency_overrides[get_summary_repository] = lambda: summary_repo
        app.dependency_overrides[get_conversation_service] = lambda: conversation_service
        app.dependency_overrides[get_quota_enforcer] = lambda: fake_enforcer

        from app.api.widget.dependencies import get_context_builder
        from app.application.context.builder import ContextBuilder

        app.dependency_overrides[get_context_builder] = lambda: ContextBuilder(
            retriever_service=retriever,
            llm=llm,
            conversation_service=conversation_service,
            summary_repository=summary_repo,
        )

        from app.application.widget.token_service import WidgetTokenService

        token, _ = WidgetTokenService().create_session_token(
            widget_id="wid_abc",
            store_id="store-1",
            organization_id="org-1",
            scopes=["rag:chat", "recommendations:read"],
        )

        with TestClient(app) as test_client:
            test_client._retriever = retriever
            test_client._conversation = conversation_service
            test_client._token = token
            yield test_client

        app.dependency_overrides.clear()

    def test_full_chain_shares_one_message_id(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="ai.flow"):
            resp = _post(client, "recommend a phone under $500", message_id="msg-chain-1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["message_id"] == "msg-chain-1"
        assert data["response"] == "Top pick: Phone X."
        # No product cards in the fixture response -> plain-text answer backed by
        # the agent's rationale (type=products would require products present).
        assert data["type"] == "text"

        events = _flow_events(caplog)
        by_name = {e["event"]: e for e in events}
        for hop in (
            "widget.chat.start",
            "retrieval.complete",
            "intent.classified",
            "agent.result",
            "orchestration.complete",
            "widget.chat.complete",
        ):
            assert hop in by_name, f"missing hop {hop}"
            assert by_name[hop]["message_id"] == "msg-chain-1", f"hop {hop} lost message_id"

        # Why the final response was produced: intent=recommendation routed to the
        # recommendation sub-agent, which returned the canonical rationale.
        assert by_name["widget.chat.start"]["store_id"] == "store-1"
        assert by_name["intent.classified"]["intent"] == "recommendation"
        assert by_name["agent.result"]["sub_agent"] == "recommendation"
        assert by_name["orchestration.complete"]["intent"] == "recommendation"
        assert by_name["widget.chat.complete"]["response_type"] == "text"
        assert by_name["widget.chat.complete"]["product_count"] == 0

        # request_id is attached to every structured event from the flow logger
        # and echoed back on the response.
        assert isinstance(data["request_id"], str)
