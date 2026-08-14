from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.dto.ai_dto import ChatResponse
from app.workflows.conversation.graph import (
    ConversationWorkflow,
    evaluate_escalation_node,
    recall_memory_node,
    update_shopping_state_node,
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
        assert response.metadata["trace"][-1]["step"] in ("execute_agent", "evaluate_escalation", "memory")

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


class TestEvaluateEscalationNode:
    def _escalation_agent(self, ticket_id="ticket-9"):
        agent = AsyncMock()
        agent.run.return_value = MagicMock(
            ticket_id=ticket_id,
            priority="p3",
            assigned_to="support",
            eta=None,
            notification_message=f"Your request has been escalated (ticket {ticket_id}).",
            summary="summary",
        )
        return agent

    def _state(self, user_input="hello", messages=None, response=None, context=None, customer_id="c1"):
        return {
            "user_input": user_input,
            "store_id": "s1",
            "customer_id": customer_id,
            "conversation_id": "convo_1",
            "messages": messages or [{"role": "user", "content": user_input}],
            "context": context or {},
            "response": response or {"content": "ok", "intent": "general"},
            "agent_trace": [],
        }

    async def test_explicit_human_request_creates_ticket(self):
        escalation_agent = self._escalation_agent()
        result = await evaluate_escalation_node(
            self._state(user_input="I want to talk to a human.", response={"content": "ok", "intent": "support"}),
            escalation_agent,
        )
        assert result["escalation"]["should_escalate"] is True
        assert result["escalation"]["ticket_id"] == "ticket-9"
        assert result["response"]["escalation_needed"] is True
        escalation_agent.run.assert_awaited_once()

    async def test_repeated_failure_escalates(self):
        escalation_agent = self._escalation_agent()
        messages = [
            {"role": "user", "content": "Where is my order? It's been a week."},
            {"role": "assistant", "content": "Let me check."},
            {"role": "user", "content": "Where is my order? Still nothing."},
        ]
        result = await evaluate_escalation_node(
            self._state(
                user_input="I've asked this three times and nobody helps me!",
                messages=[*messages, {"role": "user", "content": "I've asked this three times and nobody helps me!"}],
                response={"content": "ok", "intent": "order_status"},
            ),
            escalation_agent,
        )
        assert result["escalation"]["should_escalate"] is True
        assert "repeated_failure" in result["escalation"]["signals"]

    async def test_vague_venting_does_not_escalate(self):
        escalation_agent = self._escalation_agent()
        result = await evaluate_escalation_node(
            self._state(user_input="Your product is terrible.", response={"content": "ok", "intent": "general"}),
            escalation_agent,
        )
        assert result["escalation"]["should_escalate"] is False
        escalation_agent.run.assert_not_awaited()

    async def test_policy_question_with_knowledge_does_not_escalate(self):
        escalation_agent = self._escalation_agent()
        result = await evaluate_escalation_node(
            self._state(
                user_input="What's your return policy?",
                response={"content": "Returns accepted within 14 days.", "intent": "support"},
                context={
                    "knowledge_context": [
                        {
                            "document_title": "Return Policy",
                            "content": "Returns accepted within 14 days.",
                            "metadata": {},
                        }
                    ]
                },
            ),
            escalation_agent,
        )
        assert result["escalation"]["should_escalate"] is False
        escalation_agent.run.assert_not_awaited()

    async def test_skips_when_sub_agent_already_escalated(self):
        escalation_agent = self._escalation_agent()
        result = await evaluate_escalation_node(
            self._state(
                user_input="My account was hacked",
                response={
                    "content": "I'm handing this over.",
                    "intent": "escalation",
                    "ticket_id": "ticket-1",
                    "priority": "p1",
                },
            ),
            escalation_agent,
        )
        assert result["escalation"]["should_escalate"] is True
        assert result["escalation"]["ticket_id"] == "ticket-1"
        escalation_agent.run.assert_not_awaited()

    async def test_anonymous_customer_does_not_escalate(self):
        escalation_agent = self._escalation_agent()
        result = await evaluate_escalation_node(
            self._state(
                user_input="Where is my order?",
                customer_id=None,
                response={"content": "Let me look that up for you.", "intent": "order_status"},
            ),
            escalation_agent,
        )
        assert result["escalation"]["should_escalate"] is False
        escalation_agent.run.assert_not_awaited()


class TestConversationWorkflowEscalation:
    async def test_run_talk_to_human_creates_ticket(self, coordinator, llm):
        coordinator.run.return_value = _coordinator_state(
            "support", content="I'll check that for you.", sub_agent="support"
        )
        escalation_agent = AsyncMock()
        escalation_agent.run.return_value = MagicMock(
            ticket_id="ticket-7",
            priority="p3",
            assigned_to="support",
            eta=None,
            notification_message="Your request has been escalated (ticket ticket-7).",
        )
        workflow = ConversationWorkflow(
            coordinator=coordinator,
            llm=llm,
            escalation_agent=escalation_agent,
        )

        response = await workflow.run(
            user_input="I want to talk to a human.",
            store_id="store_1",
            customer_id="customer_1",
        )

        assert response.metadata["escalation"]["should_escalate"] is True
        assert response.metadata["escalation"]["ticket_id"] == "ticket-7"
        escalation_agent.run.assert_awaited_once()

    async def test_run_product_terrible_does_not_escalate(self, coordinator, llm):
        coordinator.run.return_value = _coordinator_state("general", content="ok")
        escalation_agent = AsyncMock()
        workflow = ConversationWorkflow(
            coordinator=coordinator,
            llm=llm,
            escalation_agent=escalation_agent,
        )

        response = await workflow.run(user_input="Your product is terrible.", store_id="store_1")

        assert response.metadata["escalation"]["should_escalate"] is False
        escalation_agent.run.assert_not_awaited()

    async def test_run_repeated_failure_escalates(self, coordinator, llm):
        coordinator.run.return_value = _coordinator_state(
            "order_status", content="I couldn't find tracking.", sub_agent="support"
        )
        escalation_agent = AsyncMock()
        escalation_agent.run.return_value = MagicMock(
            ticket_id="ticket-8",
            priority="p2",
            assigned_to="fulfillment",
            eta=None,
            notification_message="Your request has been escalated (ticket ticket-8).",
        )
        workflow = ConversationWorkflow(
            coordinator=coordinator,
            llm=llm,
            escalation_agent=escalation_agent,
        )

        response = await workflow.run(
            user_input="I've asked this three times and nobody helps me!",
            store_id="store_1",
            history=[
                {"role": "user", "content": "Where is my order?"},
                {"role": "assistant", "content": "Let me check."},
            ],
        )

        assert response.metadata["escalation"]["should_escalate"] is True
        assert "repeated_failure" in response.metadata["escalation"]["signals"]


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


class TestRecallMemoryNode:
    async def test_recalls_memory_into_context(self):
        memory_agent = AsyncMock()
        memory_agent.recall.return_value = {
            "retrieved": {
                "source": "merged",
                "all": {"last_exchange": {"user": "hi"}},
            }
        }

        result = await recall_memory_node(
            {
                "user_input": "hi",
                "store_id": "s1",
                "customer_id": "c1",
                "conversation_id": "convo_1",
                "context": {},
            },
            memory_agent,
        )

        assert result["context"]["memory"]["recall_source"] == "merged"
        assert result["context"]["memory"]["entries"]["last_exchange"] == {"user": "hi"}
        memory_agent.recall.assert_awaited_once_with(
            session_id="convo_1",
            user_id="c1",
            store_id="s1",
        )

    async def test_skips_recall_when_memory_already_present(self):
        memory_agent = AsyncMock()

        result = await recall_memory_node(
            {
                "user_input": "hi",
                "store_id": "s1",
                "conversation_id": "convo_1",
                "context": {"memory": {"recall_source": "session", "entries": {}}},
            },
            memory_agent,
        )

        assert result == {}
        memory_agent.recall.assert_not_awaited()

    async def test_skips_without_conversation_id(self):
        memory_agent = AsyncMock()

        result = await recall_memory_node(
            {"user_input": "hi", "store_id": "s1", "context": {}},
            memory_agent,
        )

        assert result == {}
        memory_agent.recall.assert_not_awaited()


class TestUpdateShoppingStateNode:
    def _llm_returning(self, payload: str):
        llm = AsyncMock()
        response = MagicMock()
        response.message.content = payload
        llm.structured_output.return_value = response
        return llm

    async def test_extracts_and_persists_session_state(self):
        memory_agent = AsyncMock()
        llm = self._llm_returning(
            '{"intent": "product_recommendation", "category": "dress", "budget": null, '
            '"currency": "USD", "color": null, "size": null, "brand": null, "use_case": null}'
        )

        result = await update_shopping_state_node(
            {
                "user_input": "I want a dress",
                "store_id": "s1",
                "conversation_id": "convo_1",
                "messages": [{"role": "user", "content": "I want a dress"}],
                "context": {"conversation": {"conversation_id": "convo_1"}, "memory": {"entries": {}}},
            },
            memory_agent,
            llm,
        )

        state = result["context"]["conversation"]["shopping_state"]
        assert state["category"] == "dress"
        assert state["currency"] == "USD"
        memory_agent.store.assert_awaited_once()
        assert memory_agent.store.call_args.kwargs["key"] == "shopping_state"
        assert memory_agent.store.call_args.kwargs["session_id"] == "convo_1"
        assert memory_agent.store.call_args.kwargs["value"]["category"] == "dress"

    async def test_merges_incrementally_with_recalled_state(self):
        memory_agent = AsyncMock()
        llm = self._llm_returning(
            '{"intent": null, "category": null, "budget": 50, "currency": "USD", '
            '"color": "black", "size": null, "brand": null, "use_case": null}'
        )

        result = await update_shopping_state_node(
            {
                "user_input": "$50 black",
                "store_id": "s1",
                "conversation_id": "convo_1",
                "messages": [{"role": "assistant", "content": "What's your budget?"}],
                "context": {
                    "conversation": {"conversation_id": "convo_1"},
                    "memory": {
                        "entries": {
                            "shopping_state": {
                                "intent": "product_recommendation",
                                "category": "dress",
                                "budget": None,
                                "currency": None,
                                "color": None,
                                "size": None,
                                "brand": None,
                                "use_case": None,
                            }
                        }
                    },
                },
            },
            memory_agent,
            llm,
        )

        state = result["context"]["conversation"]["shopping_state"]
        assert state["category"] == "dress"
        assert state["budget"] == 50
        assert state["color"] == "black"

    async def test_no_op_when_extraction_is_empty(self):
        memory_agent = AsyncMock()
        llm = self._llm_returning(
            '{"intent": null, "category": null, "budget": null, "currency": null, '
            '"color": null, "size": null, "brand": null, "use_case": null}'
        )

        result = await update_shopping_state_node(
            {
                "user_input": "thanks",
                "store_id": "s1",
                "conversation_id": "convo_1",
                "messages": [],
                "context": {},
            },
            memory_agent,
            llm,
        )

        assert result == {}
        memory_agent.store.assert_not_awaited()

    async def test_persists_through_full_workflow(self, coordinator, llm):
        coordinator.run.return_value = {
            "intent": "general",
            "confidence": 0.9,
            "sub_agent": "general",
            "response": {"content": "ok", "intent": "general", "needs_clarification": False},
        }
        memory_agent = AsyncMock()
        memory_agent.recall.return_value = {"retrieved": {"source": "merged", "all": {}}}
        memory_agent.store.return_value = {"result": {"stored": True}}
        memory_agent.summarize.return_value = {"summarized": {}}
        llm.structured_output.return_value.message.content = (
            '{"intent": "product_recommendation", "category": "laptop", "budget": 800, '
            '"currency": "USD", "color": null, "size": null, "brand": null, "use_case": "programming"}'
        )

        workflow = ConversationWorkflow(
            coordinator=coordinator,
            llm=llm,
            memory_agent=memory_agent,
        )

        await workflow.run(
            user_input="I need a laptop for programming under $800",
            store_id="store_1",
            customer_id="customer_1",
            conversation_id="convo_1",
            history=[{"role": "assistant", "content": "Hi"}],
        )

        assert memory_agent.recall.await_count == 1
        store_calls = [c for c in memory_agent.store.await_args_list if c.kwargs.get("key") == "shopping_state"]
        assert store_calls
        assert store_calls[0].kwargs["session_id"] == "convo_1"
        assert store_calls[0].kwargs["value"]["category"] == "laptop"
        assert store_calls[0].kwargs["value"]["budget"] == 800
