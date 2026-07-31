from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.coordinator.agent import CoordinatorAgent, route_after_classify, route_after_route
from app.agents.coordinator.nodes import INTEGRATION_GUIDANCE, extract_context_node
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
        runner.assert_awaited_once_with(
            query="bundle a laptop and a mouse",
            store_id="store_1",
            customer_id="customer_1",
        )

    async def test_run_coming_soon_intent_uses_fallback(self, llm, conversation_repo):
        llm.structured_output.side_effect = lambda request, schema: _json_response(
            '{"intent": "support", "confidence": 0.85}'
        )
        agent = CoordinatorAgent(llm=llm, conversation_repo=conversation_repo)

        result = await agent.run(user_input="my order is late", store_id="store_1")

        assert result["intent"] == "support"
        assert result["sub_agent"] == "support"
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
        state = {"sub_agent": "support"}
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
        assert result["context"]["extracted"]["sentiment"] == "positive"
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
