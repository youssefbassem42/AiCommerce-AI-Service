from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.dto.ai_dto import ChatResponse
from app.workflows.conversation.graph import (
    ConversationWorkflow,
    validate_input_node,
)


@pytest.fixture
def llm():
    provider = AsyncMock()
    response = MagicMock()
    response.message.content = "General reply."
    provider.chat.return_value = response
    return provider


@pytest.fixture
def coordinator():
    coordinator = AsyncMock()
    return coordinator


def _coordinator_state(intent: str, content=None, needs_clarification=False, sub_agent=None):
    return {
        "user_input": "hello",
        "intent": intent,
        "confidence": 0.9,
        "sub_agent": sub_agent or intent,
        "conversation_id": None,
        "store_id": "s1",
        "customer_id": None,
        "context": {},
        "response": {
            "content": content,
            "intent": intent,
            "needs_clarification": needs_clarification,
        },
        "needs_clarification": needs_clarification,
        "error": None,
    }


class TestConversationWorkflow:
    async def test_run_passes_through_coordinator_sub_agent_result(self, coordinator, llm):
        coordinator.run.return_value = _coordinator_state(
            "recommendation", content="Top pick: Phone X.", sub_agent="recommendation"
        )
        runner = AsyncMock()
        workflow = ConversationWorkflow(
            coordinator=coordinator,
            llm=llm,
            sub_agents={"recommendation": runner},
        )

        response = await workflow.run(
            user_input="recommend a phone",
            store_id="store_1",
            customer_id="customer_1",
        )

        assert isinstance(response, ChatResponse)
        assert response.message.content == "Top pick: Phone X."
        assert response.metadata["intent"] == "recommendation"
        assert response.metadata["sub_agent"] == "recommendation"
        runner.assert_not_awaited()

    async def test_run_general_intent_uses_llm_chat(self, coordinator, llm):
        coordinator.run.return_value = _coordinator_state("general")

        workflow = ConversationWorkflow(coordinator=coordinator, llm=llm)

        response = await workflow.run(user_input="tell me a joke", store_id="store_1")

        assert response.message.content == "General reply."
        llm.chat.assert_awaited_once()

    async def test_run_coming_soon_intent_keeps_coordinator_response(self, coordinator, llm):
        coordinator.run.return_value = _coordinator_state(
            "marketing", content="Marketing is coming soon.", sub_agent="marketing"
        )
        runner = AsyncMock()
        workflow = ConversationWorkflow(
            coordinator=coordinator,
            llm=llm,
            sub_agents={"recommendation": runner},
        )

        response = await workflow.run(user_input="create a campaign", store_id="store_1")

        assert response.message.content == "Marketing is coming soon."
        runner.assert_not_awaited()
        llm.chat.assert_not_awaited()

    async def test_run_clarifying_question_marks_needs_clarification(self, coordinator, llm):
        coordinator.run.return_value = _coordinator_state(
            "general", content="Did you mean...?", needs_clarification=True
        )

        workflow = ConversationWorkflow(coordinator=coordinator, llm=llm)

        response = await workflow.run(user_input="something vague", store_id="store_1")

        assert response.metadata["trace"]
        assert any(step.get("needs_clarification") for step in response.metadata["trace"])

    async def test_run_empty_input_returns_error_response(self, coordinator, llm):
        workflow = ConversationWorkflow(coordinator=coordinator, llm=llm)

        response = await workflow.run(user_input="   ", store_id="store_1")

        coordinator.run.assert_not_awaited()
        assert "Please provide a message" in response.message.content

    async def test_run_records_agent_trace(self, coordinator, llm):
        coordinator.run.return_value = _coordinator_state("general")

        workflow = ConversationWorkflow(coordinator=coordinator, llm=llm)

        response = await workflow.run(user_input="hello", store_id="store_1")

        assert len(response.metadata["trace"]) >= 2
        assert response.metadata["trace"][0]["step"] == "coordinator"
        assert response.metadata["trace"][-1]["step"] in ("execute_agent", "memory")

    async def test_run_updates_memory_agent(self, coordinator, llm):
        coordinator.run.return_value = _coordinator_state("general")
        memory_agent = AsyncMock()
        memory_agent.store.return_value = {"result": {"stored": True}}
        memory_agent.summarize.return_value = {"summarized": {}}

        workflow = ConversationWorkflow(
            coordinator=coordinator,
            llm=llm,
            memory_agent=memory_agent,
        )

        await workflow.run(
            user_input="hello",
            store_id="store_1",
            customer_id="customer_1",
            conversation_id="convo_1",
            history=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hey"}],
        )

        memory_agent.store.assert_awaited_once()
        assert memory_agent.store.call_args.kwargs["session_id"] == "convo_1"


class TestValidateInputNode:
    async def test_empty_input_sets_error(self):
        result = await validate_input_node({"user_input": "  ", "current_turn": 1, "max_turns": 4})

        assert result["error"] == "user_input is required"
        assert "Please provide a message" in result["response"]["content"]

    async def test_turn_limit_exceeded(self):
        result = await validate_input_node({"user_input": "hi", "current_turn": 5, "max_turns": 4})

        assert result["error"] == "max_turns_exceeded"

    async def test_appends_user_message(self):
        result = await validate_input_node(
            {
                "user_input": "hello",
                "current_turn": 1,
                "max_turns": 4,
                "messages": [{"role": "assistant", "content": "hi"}],
            }
        )

        assert result["messages"][-1] == {"role": "user", "content": "hello"}
