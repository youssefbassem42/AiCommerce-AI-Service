from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.coordinator.agent import CoordinatorAgent, route_after_classify, route_after_route
from app.agents.coordinator.nodes import (
    INTEGRATION_GUIDANCE,
    classify_intent_node,
    execute_sub_agent_node,
    extract_context_node,
    format_knowledge_context,
)
from app.agents.coordinator.state import CoordinatorState


@pytest.fixture
def llm():
    provider = AsyncMock()

    def structured_side_effect(request, response_schema):
        prompt = request.messages[-1].content
        if "classify" in prompt.lower():
            content = '{"intent": "bundle", "confidence": 0.92}'
        else:
            content = (
                '{"key_topics": ["laptops"], "customer_preferences": ["gaming"], '
                '"store_facts": [], "sentiment": "positive"}'
            )
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
def conversation_repo():
    repo = AsyncMock()
    conversation = MagicMock()
    conversation.messages = [
        MagicMock(role="user", content="Hi"),
        MagicMock(role="assistant", content="Hello!"),
    ]
    repo.find_by_id.return_value = conversation
    return repo


@pytest.fixture
def agent(llm, conversation_repo):
    return CoordinatorAgent(llm=llm, conversation_repo=conversation_repo)


class TestCoordinatorAgent:
    async def test_run_routes_to_executable_sub_agent(self, agent):
        runner = AsyncMock()
        runner.return_value.rationale = "Top pick: Gaming Laptop X."
        agent._sub_agents["bundle"] = runner

        result = await agent.run(
            user_input="bundle a laptop and a mouse",
            store_id="store_1",
            conversation_id="507f1f77bcf86cd799439011",
            customer_id="customer_1",
        )

        assert result["intent"] == "bundle"
        assert result["sub_agent"] == "bundle"
        assert result["response"]["content"] == "Top pick: Gaming Laptop X."
        assert result["response"]["needs_clarification"] is False
        runner.assert_awaited_once()
        call_kwargs = runner.await_args.kwargs
        assert call_kwargs["query"] == "bundle a laptop and a mouse"
        assert call_kwargs["store_id"] == "store_1"
        assert call_kwargs["customer_id"] == "customer_1"
        assert call_kwargs["conversation_id"] == "507f1f77bcf86cd799439011"
        assert call_kwargs["history"] == [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        assert call_kwargs["context"]["history"] == [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]

    async def test_run_coming_soon_intent_uses_fallback(self, llm, conversation_repo):
        llm.structured_output.side_effect = lambda request, schema: _json_response(
            '{"intent": "marketing", "confidence": 0.85}'
        )
        agent = CoordinatorAgent(llm=llm, conversation_repo=conversation_repo)

        result = await agent.run(user_input="create a campaign", store_id="store_1")

        assert result["intent"] == "marketing"
        assert result["sub_agent"] == "marketing"
        assert result["response"]["needs_clarification"] is False
        assert result["response"]["content"] == "Fallback answer."

    async def test_run_integration_intent_uses_static_guidance(self, llm, conversation_repo):
        llm.structured_output.side_effect = lambda request, schema: _json_response(
            '{"intent": "integration", "confidence": 0.9}'
        )
        agent = CoordinatorAgent(llm=llm, conversation_repo=conversation_repo)

        result = await agent.run(user_input="how do I connect my shopify?", store_id="store_1")

        assert result["intent"] == "integration"
        assert result["response"]["content"] == INTEGRATION_GUIDANCE
        assert result["response"]["needs_clarification"] is False

    async def test_run_unknown_intent_normalized_to_general(self, llm, conversation_repo):
        llm.structured_output.side_effect = lambda request, schema: _json_response(
            '{"intent": "weird_thing", "confidence": 0.2}'
        )
        agent = CoordinatorAgent(llm=llm, conversation_repo=conversation_repo)

        result = await agent.run(user_input="what is the meaning of life", store_id="store_1")

        assert result["intent"] == "general"
        assert result["sub_agent"] == "general"
        assert result["response"]["content"] is None
        assert result["response"]["needs_clarification"] is False

    async def test_run_classification_error_falls_back(self, llm, conversation_repo):
        llm.structured_output.side_effect = Exception("provider down")
        agent = CoordinatorAgent(llm=llm, conversation_repo=conversation_repo)

        result = await agent.run(user_input="hello", store_id="store_1")

        assert result["intent"] is None
        assert result["response"]["needs_clarification"] is True
        assert "error" in result

    async def test_run_adds_latency_metric(self, agent):
        runner = AsyncMock()
        runner.return_value.rationale = "Done."
        agent._sub_agents["recommendation"] = runner

        result = await agent.run(user_input="recommend a phone", store_id="store_1")

        assert result["response"]["latency_ms"] >= 0


class TestCoordinatorRouting:
    def test_route_after_classify_valid_intent(self):
        state: CoordinatorState = {
            "user_input": "hi",
            "intent": "bundle",
            "confidence": 0.9,
            "sub_agent": None,
            "conversation_id": None,
            "store_id": "s1",
            "customer_id": None,
            "context": {},
            "response": None,
            "needs_clarification": False,
            "error": None,
        }
        assert route_after_classify(state) == "route_to_agent"

    def test_route_after_classify_error(self):
        state: CoordinatorState = {
            "user_input": "hi",
            "intent": None,
            "confidence": None,
            "sub_agent": None,
            "conversation_id": None,
            "store_id": "s1",
            "customer_id": None,
            "context": {},
            "response": None,
            "needs_clarification": False,
            "error": "boom",
        }
        assert route_after_classify(state) == "handle_fallback"

    def test_route_after_route_executable(self):
        state = {"sub_agent": "recommendation"}
        assert route_after_route(state) == "execute_sub_agent"

    def test_route_after_route_deferred_general(self):
        state = {"sub_agent": "general"}
        assert route_after_route(state) == "format_response"

    def test_route_after_route_fallback(self):
        state = {"sub_agent": "marketing"}
        assert route_after_route(state) == "handle_fallback"


class TestExtractContextNode:
    async def test_loads_history_from_conversation_repo(self, llm, conversation_repo):
        state: CoordinatorState = {
            "user_input": "find a laptop",
            "intent": None,
            "confidence": None,
            "sub_agent": None,
            "conversation_id": "507f1f77bcf86cd799439011",
            "store_id": "s1",
            "customer_id": None,
            "context": {},
            "response": None,
            "needs_clarification": False,
            "error": None,
        }

        result = await extract_context_node(state, conversation_repo=conversation_repo, llm=llm)

        assert result["context"]["history"][0] == {"role": "user", "content": "Hi"}
        assert result["context"]["entities"]["sentiment"] == "positive"
        assert result["error"] is None

    async def test_invalid_conversation_id_skips_repo(self, llm, conversation_repo):
        state: CoordinatorState = {
            "user_input": "find a laptop",
            "intent": None,
            "confidence": None,
            "sub_agent": None,
            "conversation_id": "not-an-object-id",
            "store_id": "s1",
            "customer_id": None,
            "context": {},
            "response": None,
            "needs_clarification": False,
            "error": None,
        }

        result = await extract_context_node(state, conversation_repo=conversation_repo, llm=llm)

        conversation_repo.find_by_id.assert_not_awaited()
        assert result["context"]["history"] == []


def _json_response(content: str):
    response = MagicMock()
    response.message.content = content
    return response


ROUTER_BUILT_CONTEXT = {
    "tenant": {"organization_id": "org-1", "store_id": "store-1"},
    "store": {"currency": "USD"},
    "conversation": {"conversation_id": "convo-1"},
    "history": [{"role": "user", "content": "What is your return policy?"}],
    "memory": {},
    "intent": "support",
    "confidence": 0.95,
    "entities": {},
    "knowledge_context": [
        {
            "chunk_id": "chunk-1",
            "document_id": "doc-1",
            "document_title": "Return Policy",
            "chunk_index": 0,
            "content": "Returns are accepted within 30 days of delivery.",
            "score": 0.87,
            "rank": 1,
            "metadata": {"entity_type": "policy", "document_title": "Return Policy"},
        }
    ],
    "products": [],
    "business_rules": {"business_summary": "Store summary.", "business_summary_version": 2},
    "customer": None,
}


class TestCoordinatorContextMerge:
    """Fix 2.2: the coordinator merges router-built context instead of overwriting it."""

    async def test_extract_context_preserves_router_rag_context(self, llm):
        state: CoordinatorState = {
            "user_input": "What is your return policy?",
            "intent": None,
            "confidence": None,
            "sub_agent": None,
            "conversation_id": None,
            "store_id": "store-1",
            "customer_id": None,
            "context": dict(ROUTER_BUILT_CONTEXT),
            "response": None,
            "needs_clarification": False,
            "error": None,
        }

        result = await extract_context_node(state, llm=llm)

        context = result["context"]
        assert context["intent"] == "support"
        assert context["knowledge_context"] == ROUTER_BUILT_CONTEXT["knowledge_context"]
        assert context["business_rules"]["business_summary_version"] == 2
        assert context["history"] == [{"role": "user", "content": "What is your return policy?"}]

    async def test_extract_context_does_not_reload_mongo_when_history_provided(self, llm, conversation_repo):
        state: CoordinatorState = {
            "user_input": "What is your return policy?",
            "intent": None,
            "confidence": None,
            "sub_agent": None,
            "conversation_id": "507f1f77bcf86cd799439011",
            "store_id": "store-1",
            "customer_id": None,
            "context": dict(ROUTER_BUILT_CONTEXT),
            "response": None,
            "needs_clarification": False,
            "error": None,
        }

        await extract_context_node(state, conversation_repo=conversation_repo, llm=llm)

        conversation_repo.find_by_id.assert_not_awaited()

    async def test_classify_node_reuses_context_intent(self, llm):
        state: CoordinatorState = {
            "user_input": "What is your return policy?",
            "intent": None,
            "confidence": None,
            "sub_agent": None,
            "conversation_id": None,
            "store_id": "store-1",
            "customer_id": None,
            "context": dict(ROUTER_BUILT_CONTEXT),
            "response": None,
            "needs_clarification": False,
            "error": None,
        }

        result = await classify_intent_node(state, llm=llm)

        assert result["intent"] == "support"
        assert result["confidence"] == 0.95
        assert result["error"] is None
        llm.structured_output.assert_not_awaited()

    async def test_execute_sub_agent_receives_knowledge_context(self, llm):
        runner = AsyncMock()
        runner.return_value.rationale = "30-day return policy applies."

        result = await execute_sub_agent_node(
            {
                "user_input": "What is your return policy?",
                "store_id": "store-1",
                "customer_id": "customer-1",
                "conversation_id": "convo-1",
                "intent": "support",
                "sub_agent": "support",
                "context": dict(ROUTER_BUILT_CONTEXT),
            },
            sub_agents={"support": runner},
        )

        assert result["error"] is None
        kwargs = runner.await_args.kwargs
        assert kwargs["conversation_id"] == "convo-1"
        history = kwargs["history"]
        assert history[0]["role"] == "system"
        assert "Return Policy" in history[0]["content"]
        assert "30 days of delivery" in history[0]["content"]
        assert history[1:] == ROUTER_BUILT_CONTEXT["history"]


class TestFormatKnowledgeContext:
    def test_renders_chunks_and_summary(self):
        text = format_knowledge_context(ROUTER_BUILT_CONTEXT)
        assert "Return Policy" in text
        assert "30 days of delivery" in text
        assert "Store summary." in text

    def test_empty_context_renders_empty(self):
        assert format_knowledge_context({}) == ""

    def test_missing_chunks_renders_summary_only(self):
        context = {"business_rules": {"business_summary": "Summary only."}}
        text = format_knowledge_context(context)
        assert "Summary only." in text
        assert "[1]" not in text
