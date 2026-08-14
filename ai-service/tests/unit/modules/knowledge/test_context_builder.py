"""Phase 2 tests: Context Builder (Fix 2.1/2.3) — intent-specific retrieval."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.context.builder import ContextBuilder
from app.application.context.retrieval_planner import plan_for_intent
from app.application.knowledge.retrieval.dto import RetrievedChunkDTO, UnifiedRetrievalResult


def make_chunk(chunk_id: str, entity_type: str = "knowledge", score: float = 0.8, title: str = "Doc") -> dict:
    return RetrievedChunkDTO(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        document_title=title,
        chunk_index=0,
        content=f"Content of {chunk_id}",
        score=score,
        rank=1,
        metadata={"entity_type": entity_type, "product_id": chunk_id},
    ).model_dump()


class TestRetrievalPlanner:
    def test_support_plan_uses_faq_policy_knowledge(self):
        plan = plan_for_intent("support")
        assert set(plan.entity_types) == {"knowledge", "policy", "faq"}
        assert plan.include_products is False

    def test_escalation_plan_uses_faq_policy_knowledge(self):
        plan = plan_for_intent("escalation")
        assert "policy" in plan.entity_types

    def test_recommendation_plan_uses_products(self):
        plan = plan_for_intent("recommendation")
        assert plan.entity_types == ("product",)
        assert plan.include_products is True

    def test_sales_plan_uses_products(self):
        plan = plan_for_intent("sales")
        assert plan.entity_types == ("product",)

    def test_bundle_plan_uses_products_with_business_rules(self):
        plan = plan_for_intent("bundle")
        assert plan.entity_types == ("product",)
        assert plan.include_business_summary is True

    def test_general_plan_unfiltered(self):
        plan = plan_for_intent("general")
        assert plan.entity_types is None
        assert plan.include_business_summary is True

    def test_unknown_intent_uses_general_plan(self):
        assert plan_for_intent(None).entity_types is None
        assert plan_for_intent("weird").entity_types is None


class TestContextBuilder:
    @pytest.fixture
    def builder(self):
        retriever = MagicMock()
        retriever.search = AsyncMock(
            return_value=UnifiedRetrievalResult(
                query="q",
                results=[],
                total_count=0,
                strategy="hybrid",
                latency_ms=1.0,
                filters_applied={},
            )
        )
        llm = AsyncMock()
        return ContextBuilder(retriever_service=retriever, llm=llm), retriever

    @pytest.mark.asyncio
    async def test_support_intent_retrieves_policy_faq_only(self, builder):
        context_builder, retriever = builder
        with patch(
            "app.application.context.builder.classify_intent",
            AsyncMock(return_value=("support", 0.95)),
        ):
            context = await context_builder.build(
                "What is your return policy?",
                store_id="store-1",
                organization_id="org-1",
            )

        assert context.intent == "support"
        assert context.confidence == 0.95
        filters = retriever.search.await_args.kwargs["filters"]
        assert set(filters.entity_types) == {"knowledge", "policy", "faq"}
        assert filters.store_id == "store-1"
        assert filters.organization_id == "org-1"
        config = retriever.search.await_args.kwargs["config"]
        assert config.rerank is True

    @pytest.mark.asyncio
    async def test_want_laptop_uses_product_retrieval(self, builder):
        context_builder, retriever = builder
        retriever.search.return_value = UnifiedRetrievalResult(
            query="laptop",
            results=[
                RetrievedChunkDTO.model_validate(
                    make_chunk("laptop-1", entity_type="product", score=0.9, title="Gaming Laptop")
                )
            ],
            total_count=1,
            strategy="hybrid",
            latency_ms=1.0,
            filters_applied={},
        )
        with patch(
            "app.application.context.builder.classify_intent",
            AsyncMock(return_value=("recommendation", 0.9)),
        ):
            context = await context_builder.build(
                "I want a laptop.",
                store_id="store-1",
                organization_id="org-1",
            )

        filters = retriever.search.await_args.kwargs["filters"]
        assert filters.entity_types == ["product"]
        assert filters.entity_type is None
        assert len(context.knowledge_context) == 1
        assert context.products[0]["product_id"] == "laptop-1"

    @pytest.mark.asyncio
    async def test_faq_retrieval_never_leaks_products_for_support(self, builder):
        context_builder, retriever = builder
        with patch(
            "app.application.context.builder.classify_intent",
            AsyncMock(return_value=("support", 0.9)),
        ):
            await context_builder.build(
                "I want a laptop.",
                store_id="store-1",
            )

        filters = retriever.search.await_args.kwargs["filters"]
        assert "product" not in (filters.entity_types or [])

    @pytest.mark.asyncio
    async def test_explicit_intent_is_reused_without_classification(self, builder):
        context_builder, retriever = builder
        with patch("app.application.context.builder.classify_intent") as classify:
            context = await context_builder.build(
                "What are the specs of this laptop?",
                store_id="store-1",
                intent="sales",
            )

        classify.assert_not_awaited()
        assert context.intent == "sales"
        assert retriever.search.await_args.kwargs["filters"].entity_types == ["product"]

    @pytest.mark.asyncio
    async def test_classification_failure_falls_back_to_general(self, builder):
        context_builder, retriever = builder
        with patch(
            "app.application.context.builder.classify_intent",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            context = await context_builder.build("hello", store_id="store-1")

        assert context.intent == "general"
        assert retriever.search.await_args.kwargs["filters"].entity_types is None

    @pytest.mark.asyncio
    async def test_business_rules_loaded_from_summary_repo(self, builder):
        context_builder, _ = builder

        context_builder._summary_repo = MagicMock()
        context_builder._summary_repo.find_by_document_id = AsyncMock(
            return_value=[
                SimpleNamespace(version_number=3, created_at=None, summary="Store return policy: 30 days.")
            ]
        )

        with patch(
            "app.application.context.builder.classify_intent",
            AsyncMock(return_value=("general", 0.5)),
        ):
            context = await context_builder.build("hello", store_id="store-1")

        assert context.business_rules["business_summary_version"] == 3
        assert "return policy" in context.business_rules["business_summary"]

    @pytest.mark.asyncio
    async def test_history_memory_customer_wired(self, builder):
        context_builder, _ = builder
        context_builder._conversation_service = MagicMock()
        context_builder._conversation_service.get_conversation_history = AsyncMock(
            return_value=[MagicMock(role="user", content="hi")]
        )
        context_builder._memory_agent = AsyncMock()
        context_builder._memory_agent.recall = AsyncMock(
            return_value={"retrieved": {"source": "session", "all": {"budget": "1000"}}}
        )
        context_builder._customer_repo = MagicMock()
        context_builder._customer_repo.find_by_id = AsyncMock(
            return_value=SimpleNamespace(id="c1", email="a@b.com", first_name="Ada")
        )

        with patch(
            "app.application.context.builder.classify_intent",
            AsyncMock(return_value=("general", 0.5)),
        ):
            context = await context_builder.build(
                "hello",
                store_id="store-1",
                conversation_id="convo-1",
                customer_id="c1",
            )

        assert context.history[0]["role"] == "user"
        assert context.memory["recall_source"] == "session"
        assert context.customer["email"] == "a@b.com"

    @pytest.mark.asyncio
    async def test_provided_history_wins_over_repo(self, builder):
        context_builder, _ = builder
        context_builder._conversation_service = MagicMock()
        context_builder._conversation_service.get_conversation_history = AsyncMock()

        with patch(
            "app.application.context.builder.classify_intent",
            AsyncMock(return_value=("general", 0.5)),
        ):
            context = await context_builder.build(
                "hello",
                store_id="store-1",
                history=[{"role": "user", "content": "previous turn"}],
            )

        assert context.history == [{"role": "user", "content": "previous turn"}]
        context_builder._conversation_service.get_conversation_history.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_to_dict_roundtrip(self, builder):
        context_builder, _ = builder
        with patch(
            "app.application.context.builder.classify_intent",
            AsyncMock(return_value=("general", 0.5)),
        ):
            context = await context_builder.build("hello", store_id="store-1")

        data = context.to_dict()
        assert data["intent"] == "general"
        assert data["store"] == {}
        restored = context.from_dict(data)
        assert restored.intent == "general"
