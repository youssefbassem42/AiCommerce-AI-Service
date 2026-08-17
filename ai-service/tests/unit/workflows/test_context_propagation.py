"""Phase 4 — shared conversation context, history & memory propagation.

Covers the mission test matrix for the widget → ContextBuilder →
ConversationWorkflow → Coordinator → sub-agent → persistence flow:

    - structured conversation context must persist across turns (merge, not replace)
    - shopping state must survive memory loss and reach every sub-agent
    - the current user message must never be duplicated in LLM prompts
    - session summaries must be isolated per conversation
    - tenant isolation for conversation context writes
    - memory failures must not break a turn
    - AIContext serialization round-trips every field
    - long histories must flow through the workflow unchanged
"""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.agents.coordinator.agent import CoordinatorAgent
from app.agents.coordinator.nodes import chat_via_streaming_provider
from app.agents.memory import nodes as memory_nodes
from app.agents.memory.tools import recall_all
from app.api.widget.router import _persist_chat_context
from app.application.context.ai_context import AIContext
from app.application.context.builder import ContextBuilder
from app.application.context.shopping_state import SESSION_STATE_KEY
from app.application.dto.ai_dto import ChatResponse, MessageDTO, UsageDTO
from app.infrastructure.repositories.conversation_repository import ConversationRepository
from app.workflows.conversation.graph import ConversationWorkflow

logger = logging.getLogger(__name__)


class _FakeMemoryAgent:
    """In-memory session memory simulating the MemoryAgent contract (Redis-backed)."""

    def __init__(self, sessions=None):
        self.sessions = sessions if sessions is not None else {}
        self.store_calls = []

    async def recall(self, key=None, session_id=None, user_id=None, store_id=None):
        session = self.sessions.get(session_id, {})
        if key:
            value = session.get(key)
            if value is not None:
                return {"retrieved": {"key": key, "value": value, "source": "session"}}
            return {"retrieved": None}
        return {"retrieved": {"all": session, "source": "session"}}

    async def store(self, key, value, session_id=None, user_id=None, store_id=None, ttl_seconds=None):
        self.store_calls.append({"key": key, "value": value, "session_id": session_id})
        self.sessions.setdefault(session_id, {})[key] = value
        return {"result": {"stored": True, "scope": "session", "key": key}}

    async def summarize(self, transcript, session_id=None, user_id=None, store_id=None):
        return {"summarized": {}, "result": {"stored": False}}


def _message(role: str, content: str) -> dict:
    return {"role": role, "content": content}


class TestStructuredContextPersistence:
    """Bug 1: update_context replaced the whole `context` field with each turn's delta."""

    @staticmethod
    def _repo_with(monkeypatch, existing, collection=None):
        repo = ConversationRepository()
        coll = collection or MagicMock()
        coll.find_one = AsyncMock(
            side_effect=lambda query, projection=None: next(
                (doc for doc in existing if doc.get("conversation_id") == query.get("conversation_id")),
                None,
            )
        )
        coll.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        monkeypatch.setattr(ConversationRepository, "collection", coll)
        return repo, coll

    async def test_update_context_merges_top_level_keys_not_replaces(self, monkeypatch):
        repo, coll = self._repo_with(
            monkeypatch,
            [{"conversation_id": "conv-1", "store_id": "store-A", "context": {"last_recommendation": {"q": 1}}}],
        )

        await repo.update_context("conv-1", {"routing": {"active_intent": "support"}}, store_id="store-A")

        query, update = coll.update_one.call_args[0]
        assert query["conversation_id"] == "conv-1"
        assert query["store_id"] == "store-A"
        assert update["$set"] == {"context.routing": {"active_intent": "support"}}

    async def test_update_context_keeps_prior_keys_end_to_end(self, monkeypatch):
        state = {"context": {"last_recommendation": {"product_ids": ["p1"]}}}

        async def fake_update_one(query, update, upsert=False):
            for key, value in update.get("$set", {}).items():
                if key.startswith("context."):
                    field = key.split(".", 1)[1]
                    state.setdefault("context", {})[field] = value
            return MagicMock(modified_count=1)

        coll = MagicMock()
        coll.find_one = AsyncMock(
            side_effect=lambda query, projection=None: state if query.get("conversation_id") == "conv-1" else None
        )
        coll.update_one = AsyncMock(side_effect=fake_update_one)
        repo, _ = self._repo_with(monkeypatch, [], collection=coll)
        coll.update_one = AsyncMock(side_effect=fake_update_one)

        await repo.update_context("conv-1", {"routing": {"active_intent": "support"}}, store_id="store-A")
        await repo.update_context("conv-1", {"last_bundle": {"id": "b1"}}, store_id="store-A")

        assert state["context"]["last_recommendation"]["product_ids"] == ["p1"]
        assert state["context"]["routing"] == {"active_intent": "support"}
        assert state["context"]["last_bundle"] == {"id": "b1"}

    async def test_persist_chat_context_product_then_non_product_turn(self):
        conversation_service = AsyncMock()

        first = ChatResponse(
            id="1",
            model="m",
            provider="orchestration",
            message=MessageDTO(role="assistant", content="Top pick: X."),
            usage=UsageDTO(),
            latency_ms=0.0,
            metadata={
                "intent": "recommendation",
                "sub_agent": "recommendation",
                "result": {"products": [{"product_id": "p1", "title": "Phone X", "price": "99.0", "currency": "USD"}]},
            },
        )
        await _persist_chat_context(
            conversation_service, "conv-1", "store-A", "show me phones", first, previous_routing=None
        )
        first_delta = conversation_service.update_conversation_context.call_args[0][1]
        assert "last_recommendation" in first_delta
        assert first_delta["routing"]["active_intent"] == "recommendation"

        second = ChatResponse(
            id="2",
            model="m",
            provider="orchestration",
            message=MessageDTO(role="assistant", content="Sure."),
            usage=UsageDTO(),
            latency_ms=0.0,
            metadata={"intent": "support", "sub_agent": "support", "result": None},
        )
        await _persist_chat_context(
            conversation_service,
            "conv-1",
            "store-A",
            "what's your return policy?",
            second,
            previous_routing={"active_intent": "recommendation"},
        )
        second_delta = conversation_service.update_conversation_context.call_args[0][1]
        assert "last_recommendation" not in second_delta
        assert second_delta["routing"]["previous_intent"] == "recommendation"


class TestShoppingStateDurability:
    """Bug 2: shopping state lived only in Redis; now surfaced and persisted durably."""

    def _llm(self, shopping_payload: str):
        llm = AsyncMock()

        def fake_structured(request, out_type):
            system = request.messages[0].content
            if "shopping requirements" in system:
                content = shopping_payload
            else:
                content = '{"key_topics": [], "customer_preferences": [], "store_facts": [], "sentiment": "neutral"}'
            response = MagicMock()
            response.message.content = content
            return response

        llm.structured_output = AsyncMock(side_effect=fake_structured)
        return llm

    async def test_workflow_run_surfaces_shopping_state_in_metadata(self):
        coordinator = AsyncMock()
        coordinator.run.return_value = {
            "intent": "recommendation",
            "confidence": 0.9,
            "sub_agent": "recommendation",
            "response": {"content": "Here you go.", "intent": "recommendation", "needs_clarification": False},
        }
        llm = self._llm(
            '{"intent": "product_recommendation", "category": "laptop", "budget": 3000, '
            '"currency": "USD", "color": null, "size": null, "brand": null, "use_case": null}'
        )
        workflow = ConversationWorkflow(
            coordinator=coordinator,
            llm=llm,
            memory_agent=_FakeMemoryAgent(),
        )

        response = await workflow.run(
            user_input="I want a gaming laptop under 3000",
            store_id="store-A",
            conversation_id="conv-1",
            context={"conversation": {"conversation_id": "conv-1"}, "memory": {"entries": {}}},
        )

        assert (response.metadata or {}).get("shopping_state") == {
            "intent": "product_recommendation",
            "category": "laptop",
            "budget": 3000,
            "currency": "USD",
            "color": None,
            "size": None,
            "brand": None,
            "use_case": None,
        }

    async def test_persist_chat_context_persists_shopping_state(self):
        conversation_service = AsyncMock()
        response = ChatResponse(
            id="1",
            model="m",
            provider="orchestration",
            message=MessageDTO(role="assistant", content="ok"),
            usage=UsageDTO(),
            latency_ms=0.0,
            metadata={
                "intent": "recommendation",
                "sub_agent": "recommendation",
                "result": None,
                "shopping_state": {
                    "intent": "product_recommendation",
                    "category": "laptop",
                    "budget": 3000,
                    "currency": "USD",
                    "color": None,
                    "size": None,
                    "brand": None,
                    "use_case": None,
                },
            },
        )

        await _persist_chat_context(conversation_service, "conv-1", "store-A", "laptop", response)

        delta = conversation_service.update_conversation_context.call_args[0][1]
        assert delta["shopping_state"]["category"] == "laptop"
        assert delta["shopping_state"]["budget"] == 3000

    async def test_context_builder_seeds_shopping_state_from_stored_context(self):
        retriever = AsyncMock()
        retriever.search.return_value = SimpleNamespace(results=[])
        memory_agent = _FakeMemoryAgent()
        builder = ContextBuilder(
            retriever_service=retriever,
            llm=AsyncMock(),
            memory_agent=memory_agent,
        )

        context = await builder.build(
            "Something lighter",
            store_id="store-A",
            conversation_id="conv-1",
            intent="recommendation",
            conversation_context={
                "routing": {"active_intent": "recommendation"},
                "shopping_state": {
                    "intent": "product_recommendation",
                    "category": "laptop",
                    "budget": 3000,
                    "currency": "USD",
                    "color": None,
                    "size": None,
                    "brand": None,
                    "use_case": None,
                },
            },
        )

        assert context.conversation[SESSION_STATE_KEY]["category"] == "laptop"
        assert context.conversation[SESSION_STATE_KEY]["budget"] == 3000

    async def test_context_builder_prefers_recalled_memory_over_stored_context(self):
        retriever = AsyncMock()
        retriever.search.return_value = SimpleNamespace(results=[])
        memory_agent = _FakeMemoryAgent(
            sessions={
                "conv-1": {
                    SESSION_STATE_KEY: {
                        "intent": "product_recommendation",
                        "category": "dress",
                        "budget": 80,
                        "currency": "USD",
                        "color": "black",
                        "size": None,
                        "brand": None,
                        "use_case": None,
                    }
                }
            }
        )
        builder = ContextBuilder(
            retriever_service=retriever,
            llm=AsyncMock(),
            memory_agent=memory_agent,
        )

        context = await builder.build(
            "in black",
            store_id="store-A",
            conversation_id="conv-1",
            intent="recommendation",
            conversation_context={
                "shopping_state": {
                    "intent": "product_recommendation",
                    "category": "laptop",
                    "budget": 3000,
                    "currency": "USD",
                    "color": None,
                    "size": None,
                    "brand": None,
                    "use_case": None,
                }
            },
        )

        assert context.conversation.get(SESSION_STATE_KEY) is None
        assert context.memory["entries"][SESSION_STATE_KEY]["category"] == "dress"

    async def test_update_shopping_state_merges_from_conversation_state_when_memory_missing(self):
        llm = self._llm(
            '{"intent": null, "category": null, "budget": null, "currency": null, '
            '"color": null, "size": null, "brand": null, "use_case": null}'
        )
        memory_agent = _FakeMemoryAgent()
        from app.workflows.conversation.graph import update_shopping_state_node

        result = await update_shopping_state_node(
            {
                "user_input": "Something lighter",
                "store_id": "store-A",
                "conversation_id": "conv-1",
                "messages": [{"role": "user", "content": "Something lighter"}],
                "context": {
                    "conversation": {
                        "conversation_id": "conv-1",
                        SESSION_STATE_KEY: {
                            "intent": "product_recommendation",
                            "category": "laptop",
                            "budget": 3000,
                            "currency": "USD",
                            "color": None,
                            "size": None,
                            "brand": None,
                            "use_case": None,
                        },
                    },
                    "memory": {"entries": {}},
                },
            },
            memory_agent,
            llm,
        )

        state = result["context"]["conversation"][SESSION_STATE_KEY]
        assert state["category"] == "laptop"
        assert state["budget"] == 3000


class TestMessageDeduplication:
    """Bug 3: the streaming path sent the current user message twice to the model."""

    async def test_streaming_provider_request_has_single_current_message(self, monkeypatch):
        captured = {}

        class FakeProvider:
            async def stream(self, request):
                captured["request"] = request
                yield SimpleNamespace(id="c1", model="m1", content="Hello", usage=None, finish_reason=None)

        monkeypatch.setattr(
            "app.agents.coordinator.nodes.LLMProviderFactory",
            lambda: SimpleNamespace(get_provider=lambda name: FakeProvider()),
        )

        messages = [
            _message("user", "I want a gaming laptop under 3000"),
            _message("assistant", "Here you go."),
            _message("user", "Something lighter"),
        ]
        await chat_via_streaming_provider(
            model="bedrock-model",
            messages=messages,
            user_input="Something lighter",
            context={},
        )

        request = captured["request"]
        user_contents = [m.content for m in request.messages if m.role == "user"]
        assert user_contents.count("Something lighter") == 1
        assert user_contents == ["I want a gaming laptop under 3000", "Something lighter"]

    async def test_streaming_provider_still_appends_when_message_missing(self, monkeypatch):
        captured = {}

        class FakeProvider:
            async def stream(self, request):
                captured["request"] = request
                yield SimpleNamespace(id="c1", model="m1", content="Hello", usage=None, finish_reason=None)

        monkeypatch.setattr(
            "app.agents.coordinator.nodes.LLMProviderFactory",
            lambda: SimpleNamespace(get_provider=lambda name: FakeProvider()),
        )

        await chat_via_streaming_provider(
            model="bedrock-model",
            messages=[_message("assistant", "How can I help?")],
            user_input="Show me phones",
            context={},
        )

        request = captured["request"]
        user_contents = [m.content for m in request.messages if m.role == "user"]
        assert user_contents == ["Show me phones"]


class TestSessionSummaryIsolation:
    """Bug 4: summaries were keyed (user, store) so parallel conversations clobbered each other."""

    async def test_summarize_session_writes_session_scoped_key(self, monkeypatch):
        fake_write = AsyncMock(return_value=SimpleNamespace(id="m1"))
        monkeypatch.setattr(memory_nodes, "write_user_memory", fake_write)
        monkeypatch.setattr(
            memory_nodes,
            "summarize_transcript",
            AsyncMock(return_value={"summary": "transcript summary"}),
        )

        result = await memory_nodes.summarize_session_node(
            {
                "action": "summarize",
                "session_id": "conv-A",
                "user_id": "cust-1",
                "store_id": "store-A",
                "value": {"transcript": "user: hi\nassistant: hello"},
            }
        )

        assert result["summarized"] is not None
        assert fake_write.call_args.args[2] == "session_summary:conv-A"
        assert fake_write.call_args.args[0] == "cust-1"
        assert fake_write.call_args.args[1] == "store-A"

    async def test_recall_all_excludes_other_sessions_summaries(self, monkeypatch):
        repo = MagicMock()
        repo.list_active = AsyncMock(
            return_value=[
                SimpleNamespace(key="session_summary:conv-A", value={"summary": "A"}),
                SimpleNamespace(key="session_summary:conv-B", value={"summary": "B"}),
                SimpleNamespace(key="prefers_color", value={"color": "black"}),
            ]
        )
        monkeypatch.setattr("app.agents.memory.tools.get_memory_repo", lambda: repo)
        monkeypatch.setattr("app.agents.memory.tools.list_session_memories", AsyncMock(return_value={}))

        merged = await recall_all(session_id="conv-A", user_id="cust-1", store_id="store-A")

        assert merged["session_summary:conv-A"] == {"summary": "A"}
        assert "session_summary:conv-B" not in merged
        assert merged["prefers_color"] == {"color": "black"}


class TestTenantIsolation:
    async def test_update_context_requires_matching_store(self, monkeypatch):
        repo, coll = TestStructuredContextPersistence._repo_with(
            monkeypatch,
            [{"conversation_id": "conv-b", "store_id": "store-B", "context": {}}],
        )

        await repo.update_context("conv-b", {"routing": {"active_intent": "support"}}, store_id="store-A")

        query = coll.update_one.call_args[0][0]
        assert query["conversation_id"] == "conv-b"
        assert query["store_id"] == "store-A"


class TestMemoryFailureTolerance:
    async def test_shopping_state_persist_failure_does_not_break_turn(self):
        from app.workflows.conversation.graph import update_shopping_state_node

        memory_agent = AsyncMock()
        memory_agent.store.side_effect = RuntimeError("redis down")
        llm = AsyncMock()
        response = MagicMock()
        response.message.content = (
            '{"intent": "product_recommendation", "category": "laptop", "budget": 3000, '
            '"currency": "USD", "color": null, "size": null, "brand": null, "use_case": null}'
        )
        llm.structured_output.return_value = response

        result = await update_shopping_state_node(
            {
                "user_input": "I want a gaming laptop under 3000",
                "store_id": "store-A",
                "conversation_id": "conv-1",
                "messages": [{"role": "user", "content": "I want a gaming laptop under 3000"}],
                "context": {"conversation": {"conversation_id": "conv-1"}, "memory": {"entries": {}}},
            },
            memory_agent,
            llm,
        )

        state = result["context"]["conversation"][SESSION_STATE_KEY]
        assert state["category"] == "laptop"
        assert state["budget"] == 3000

    async def test_update_memory_failure_does_not_break_turn(self):
        coordinator = AsyncMock()
        coordinator.run.return_value = {
            "intent": "general",
            "confidence": 0.9,
            "sub_agent": "general",
            "response": {"content": "ok", "intent": "general", "needs_clarification": False},
        }
        llm = AsyncMock()
        llm.structured_output.return_value.message.content = (
            '{"intent": null, "category": null, "budget": null, "currency": null, '
            '"color": null, "size": null, "brand": null, "use_case": null}'
        )
        memory_agent = _FakeMemoryAgent()
        original_summarize = memory_agent.summarize
        memory_agent.summarize = AsyncMock(side_effect=RuntimeError("memory down"))

        workflow = ConversationWorkflow(
            coordinator=coordinator,
            llm=llm,
            memory_agent=memory_agent,
        )

        response = await workflow.run(
            user_input="hello there",
            store_id="store-A",
            customer_id="cust-1",
            conversation_id="conv-1",
            history=[
                _message("user", "first"),
                _message("assistant", "second"),
                _message("user", "third"),
            ],
            context={"conversation": {"conversation_id": "conv-1"}, "memory": {"entries": {}}},
        )

        assert response.message.content == "ok"
        memory_agent.summarize = original_summarize


class TestSerialization:
    def test_ai_context_round_trip_preserves_all_fields(self):
        original = AIContext(
            tenant={"organization_id": "org-1", "store_id": "store-A"},
            store={"name": "A"},
            conversation={
                "conversation_id": "conv-1",
                "customer_id": "cust-1",
                SESSION_STATE_KEY: {"category": "laptop", "budget": 3000},
                "routing": {"active_intent": "recommendation"},
            },
            history=[{"role": "user", "content": "hi"}],
            memory={"recall_source": "merged", "entries": {"last_exchange": {"user": "hi"}}},
            intent="recommendation",
            confidence=0.9,
            entities={"key_topics": ["laptop"]},
            knowledge_context=[{"chunk_id": "c1", "content": "x", "metadata": {}}],
            products=[{"product_id": "p1"}],
            business_rules={"business_summary": "summary"},
            customer={"id": "cust-1", "email": "a@b.c"},
        )

        restored = AIContext.from_dict(original.to_dict())

        assert restored.to_dict() == original.to_dict()


class TestMultiTurnFlow:
    """End-to-end evidence: two-turn recommendation keeps shopping state and history."""

    def _build_llm(self, shopping_payload_getter):
        llm = AsyncMock()

        def fake_structured(request, out_type):
            system = request.messages[0].content
            if "shopping requirements" in system:
                content = shopping_payload_getter()
            else:
                content = '{"key_topics": [], "customer_preferences": [], "store_facts": [], "sentiment": "neutral"}'
            response = MagicMock()
            response.message.content = content
            return response

        llm.structured_output = AsyncMock(side_effect=fake_structured)
        return llm

    def _context_builder(self, conversation_service, memory_agent):
        retriever = AsyncMock()
        retriever.search.return_value = SimpleNamespace(results=[])
        customer_repo = AsyncMock()
        customer_repo.find_by_id = AsyncMock(return_value=None)
        return ContextBuilder(
            retriever_service=retriever,
            llm=AsyncMock(),
            conversation_service=conversation_service,
            memory_agent=memory_agent,
            customer_repo=customer_repo,
        )

    async def test_recommendation_keeps_shopping_state_and_history_across_turns(self):
        store_id = "store-A"
        conversation_id = "conv-1"
        calls = []

        def shopping_payload():
            return (
                '{"intent": "product_recommendation", "category": "laptop", "budget": 3000, '
                '"currency": "USD", "color": null, "size": null, "brand": null, "use_case": null}'
            )

        llm = self._build_llm(shopping_payload)

        async def runner(query, store_id, customer_id=None, history=None, conversation_id=None, context=None):
            calls.append({"query": query, "history": list(history or []), "context": dict(context or {})})
            return SimpleNamespace(rationale="Top pick: LapX.", products=[])

        coordinator = CoordinatorAgent(llm=llm, sub_agents={"recommendation": runner})
        memory_agent = _FakeMemoryAgent()
        stored_messages = []

        async def fake_history(cid, store_id=None):
            return [MessageDTO(role=m["role"], content=m["content"]) for m in stored_messages]

        conversation_service = AsyncMock()
        conversation_service.get_conversation_history.side_effect = fake_history
        conversation_service.get_conversation_context.return_value = {}

        workflow = ConversationWorkflow(
            coordinator=coordinator,
            llm=llm,
            sub_agents={"recommendation": runner},
            memory_agent=memory_agent,
        )

        # Turn 1: "I want a gaming laptop under 3000"
        builder = self._context_builder(conversation_service, memory_agent)
        ai_context = await builder.build(
            "I want a gaming laptop under 3000",
            store_id=store_id,
            conversation_id=conversation_id,
            customer_id="cust-1",
            intent="recommendation",
        )
        response_1 = await workflow.run(
            user_input="I want a gaming laptop under 3000",
            store_id=store_id,
            customer_id="cust-1",
            conversation_id=conversation_id,
            history=list(ai_context.history),
            context=ai_context.to_dict(),
            metadata={"message_id": "m1"},
        )
        stored_messages.extend(
            [
                _message("user", "I want a gaming laptop under 3000"),
                _message("assistant", response_1.message.content),
            ]
        )

        assert len(calls) == 1
        turn1_shopping = calls[0]["context"]["conversation"][SESSION_STATE_KEY]
        assert turn1_shopping["category"] == "laptop"
        assert turn1_shopping["budget"] == 3000
        assert (response_1.metadata or {}).get("shopping_state", {}).get("budget") == 3000

        # Persisted structured context (as the router would write it after turn 1).
        stored_context = {
            "routing": {"active_intent": "recommendation"},
            "shopping_state": response_1.metadata["shopping_state"],
        }
        conversation_service.get_conversation_context.return_value = stored_context

        # Turn 2: "Something lighter" — memory (Redis) still holds the state.
        ai_context_2 = await builder.build(
            "Something lighter",
            store_id=store_id,
            conversation_id=conversation_id,
            customer_id="cust-1",
            intent="recommendation",
            conversation_context=stored_context,
        )
        response_2 = await workflow.run(
            user_input="Something lighter",
            store_id=store_id,
            customer_id="cust-1",
            conversation_id=conversation_id,
            history=list(ai_context_2.history),
            context=ai_context_2.to_dict(),
            metadata={"message_id": "m2"},
        )

        assert len(calls) == 2
        turn2 = calls[1]
        history_contents = [m.get("content") for m in turn2["history"] if m.get("role") == "user"]
        assert "I want a gaming laptop under 3000" in history_contents
        turn2_shopping = turn2["context"]["conversation"][SESSION_STATE_KEY]
        assert turn2_shopping["category"] == "laptop"
        assert turn2_shopping["budget"] == 3000
        assert (response_2.metadata or {}).get("shopping_state", {}).get("budget") == 3000

    async def test_shopping_state_survives_redis_loss_via_persisted_context(self):
        store_id = "store-A"
        conversation_id = "conv-1"
        calls = []

        def shopping_payload():
            return (
                '{"intent": "product_recommendation", "category": "laptop", "budget": 3000, '
                '"currency": "USD", "color": null, "size": null, "brand": null, "use_case": null}'
            )

        llm = self._build_llm(shopping_payload)

        async def runner(query, store_id, customer_id=None, history=None, conversation_id=None, context=None):
            calls.append({"query": query, "context": dict(context or {})})
            return SimpleNamespace(rationale="Top pick: LapX.", products=[])

        coordinator = CoordinatorAgent(llm=llm, sub_agents={"recommendation": runner})
        memory_agent = _FakeMemoryAgent()
        conversation_service = AsyncMock()
        conversation_service.get_conversation_history.return_value = []
        conversation_service.get_conversation_context.return_value = {}

        workflow = ConversationWorkflow(
            coordinator=coordinator,
            llm=llm,
            sub_agents={"recommendation": runner},
            memory_agent=memory_agent,
        )
        builder = self._context_builder(conversation_service, memory_agent)

        ai_context = await builder.build(
            "I want a gaming laptop under 3000",
            store_id=store_id,
            conversation_id=conversation_id,
            customer_id="cust-1",
            intent="recommendation",
        )
        response_1 = await workflow.run(
            user_input="I want a gaming laptop under 3000",
            store_id=store_id,
            customer_id="cust-1",
            conversation_id=conversation_id,
            history=[],
            context=ai_context.to_dict(),
        )

        # Redis is gone: a fresh session has no memory at all.
        memory_agent.sessions.clear()
        stored_context = {
            "routing": {"active_intent": "recommendation"},
            "shopping_state": response_1.metadata["shopping_state"],
        }
        conversation_service.get_conversation_context.return_value = stored_context
        conversation_service.get_conversation_history.return_value = []

        ai_context_2 = await builder.build(
            "Something lighter",
            store_id=store_id,
            conversation_id=conversation_id,
            customer_id="cust-1",
            intent="recommendation",
            conversation_context=stored_context,
        )
        await workflow.run(
            user_input="Something lighter",
            store_id=store_id,
            customer_id="cust-1",
            conversation_id=conversation_id,
            history=[],
            context=ai_context_2.to_dict(),
        )

        turn2_shopping = calls[1]["context"]["conversation"][SESSION_STATE_KEY]
        assert turn2_shopping["category"] == "laptop"
        assert turn2_shopping["budget"] == 3000


class TestLongContext:
    async def test_workflow_handles_long_history(self):
        calls = []

        async def runner(query, store_id, customer_id=None, history=None, conversation_id=None, context=None):
            calls.append({"history": list(history or []), "context": dict(context or {})})
            return SimpleNamespace(rationale="ok", products=[])

        llm = AsyncMock()
        response = MagicMock()
        response.message.content = (
            '{"intent": null, "category": null, "budget": null, "currency": null, '
            '"color": null, "size": null, "brand": null, "use_case": null}'
        )
        llm.structured_output.return_value = response

        coordinator = CoordinatorAgent(llm=llm, sub_agents={"recommendation": runner})
        history = [_message("user" if i % 2 == 0 else "assistant", f"message {i}") for i in range(30)]
        workflow = ConversationWorkflow(
            coordinator=coordinator,
            llm=llm,
            sub_agents={"recommendation": runner},
            memory_agent=_FakeMemoryAgent(),
        )

        await workflow.run(
            user_input="show me laptops",
            store_id="store-A",
            conversation_id="conv-1",
            history=history,
            context={
                "intent": "recommendation",
                "history": history,
                "conversation": {"conversation_id": "conv-1"},
                "memory": {"entries": {}},
            },
        )

        assert len(calls) == 1
        history_contents = [m.get("content") for m in calls[0]["history"]]
        assert "message 0" in history_contents
        assert "message 29" in history_contents


class TestEmptyContext:
    async def test_workflow_runs_with_no_context(self):
        coordinator = AsyncMock()
        coordinator.run.return_value = {
            "intent": "general",
            "confidence": 0.9,
            "sub_agent": "general",
            "response": {"content": "ok", "intent": "general", "needs_clarification": False},
        }
        llm = AsyncMock()
        llm.structured_output.return_value.message.content = (
            '{"intent": null, "category": null, "budget": null, "currency": null, '
            '"color": null, "size": null, "brand": null, "use_case": null}'
        )
        workflow = ConversationWorkflow(coordinator=coordinator, llm=llm, memory_agent=_FakeMemoryAgent())

        response = await workflow.run(
            user_input="hello",
            store_id="store-A",
            conversation_id="conv-1",
        )

        assert response.message.content == "ok"
