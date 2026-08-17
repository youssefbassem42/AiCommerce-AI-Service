"""Phase 4 — Recommendation engine rebuild tests.

Covers:
- Fix 4.1: structured recommendation request (category/budget/currency/use_case/brand/attributes)
- Fix 4.2: deterministic product retrieval with hard filters
- Fix 4.3: deterministic ranking
- Fix 4.4: discount-aware recommendation
- Fix 4.5: structured recommendation result + LLM explanation
"""

import re
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.agents.recommendation.agent import RecommendationAgent
from app.agents.recommendation.nodes import (
    filter_inventory_node,
    format_response_node,
    rank_candidates_node,
)
from app.agents.recommendation.state import RecommendationState
from app.application.recommendation.catalog_service import RecommendationCatalogService
from app.application.recommendation.dto.recommendation_dto import (
    RecommendationIntent,
    RecommendationResponse,
    ScoredProduct,
)
from app.domain.commerce.aggregates.product import Product, ProductOption, Variant
from app.domain.commerce.value_objects.money import Money


def make_product(
    product_id: str,
    title: str,
    product_type: str,
    price: Decimal,
    vendor: str | None = None,
    in_stock: int = 5,
    max_discount_pct: float = 0.0,
    status: str = "active",
) -> Product:
    product = Product(
        id=product_id,
        store_id="store-1",
        organization_id="org-1",
        title=title,
        product_type=product_type,
        vendor=vendor,
        status=status,
        variants=[
            Variant(
                id=f"v-{product_id}",
                sku=f"SKU-{product_id}",
                title="Standard",
                price=Money(amount=price, currency="USD"),
                inventory_quantity=in_stock,
            )
        ],
        metadata={"max_discount_pct": max_discount_pct} if max_discount_pct else {},
    )
    return product


@pytest.fixture
def product_repo():
    repo = AsyncMock()
    repo.find_by_id.return_value = None
    repo.find_many.return_value = []
    return repo


@pytest.fixture
def retriever():
    r = AsyncMock()
    r.search.return_value.results = []
    return r


@pytest.fixture
def llm():
    provider = AsyncMock()
    provider.structured_output.return_value.message.content = (
        '{"category": "laptop", "budget": 800, "currency": "USD", '
        '"use_case": "programming", "brand": null, "attributes": {}, '
        '"required_specs": [], "min_quality": null, "hidden_needs": []}'
    )
    return provider


# ============================================================================
# Fix 4.1 — Structured recommendation request
# ============================================================================


class TestStructuredRequest:
    async def test_canonical_keys_parse_into_intent(self, llm):
        intent = await _parse_intent(llm, "I need a laptop around $800 for programming")
        assert intent.product_type == "laptop"
        assert intent.max_budget == 800.0
        assert intent.currency == "USD"
        assert intent.use_case == "programming"
        assert intent.brand is None
        assert intent.attributes == {}

    async def test_brand_and_attributes_parse(self, llm):
        llm.structured_output.return_value.message.content = (
            '{"category": "laptop", "budget": null, "currency": "EUR", '
            '"use_case": null, "brand": "Dell", '
            '"attributes": {"ram": ">= 16GB", "color": "black"}, '
            '"required_specs": [], "min_quality": null, "hidden_needs": []}'
        )
        intent = await _parse_intent(llm, "A Dell laptop with 16GB RAM in black")
        assert intent.brand == "Dell"
        assert intent.currency == "EUR"
        assert intent.attributes == {"ram": ">= 16GB", "color": "black"}
        assert intent.required_specs == [
            {"name": "ram", "value": ">= 16GB"},
            {"name": "color", "value": "black"},
        ]

    async def test_legacy_output_still_parses(self, llm):
        llm.structured_output.return_value.message.content = (
            '{"product_type": "laptop", "use_case": "gaming", '
            '"required_specs": [{"ram": ">= 16GB"}], "max_budget": 1500.0, '
            '"min_quality": null, "hidden_needs": []}'
        )
        intent = await _parse_intent(llm, "gaming laptop")
        assert intent.product_type == "laptop"
        assert intent.max_budget == 1500.0
        assert intent.required_specs == [{"name": "ram", "value": ">= 16GB"}]

    async def test_shopping_state_fills_currency_and_brand(self, llm):
        llm.structured_output.return_value.message.content = (
            '{"category": null, "budget": null, "currency": null, '
            '"use_case": null, "brand": null, "attributes": {}, '
            '"required_specs": [], "min_quality": null, "hidden_needs": []}'
        )
        from app.agents.recommendation.tools import parse_intent

        intent = await parse_intent(
            "the laptop",
            llm=llm,
            shopping_state={
                "category": "laptop",
                "budget": 800,
                "currency": "USD",
                "brand": "Dell",
                "use_case": "programming",
            },
        )
        assert intent.product_type == "laptop"
        assert intent.max_budget == 800.0
        assert intent.currency == "USD"
        assert intent.brand == "Dell"

    async def test_default_currency(self, llm):
        llm.structured_output.return_value.message.content = (
            '{"category": "laptop", "budget": 800, "currency": null, '
            '"use_case": null, "brand": null, "attributes": {}, '
            '"required_specs": [], "min_quality": null, "hidden_needs": []}'
        )
        intent = await _parse_intent(llm, "laptop")
        assert intent.currency == "USD"

    async def test_to_structured_request_canonical(self):
        intent = RecommendationIntent(
            product_type="laptop",
            max_budget=800,
            currency="USD",
            use_case="programming",
            brand="Dell",
            attributes={"ram": ">= 16GB"},
        )
        assert intent.to_structured_request() == {
            "category": "laptop",
            "budget": 800,
            "currency": "USD",
            "use_case": "programming",
            "brand": "Dell",
            "attributes": {"ram": ">= 16GB"},
        }


async def _parse_intent(llm, query):
    from app.agents.recommendation.tools import parse_intent

    return await parse_intent(query, llm=llm)


# ============================================================================
# Fix 4.2 — Deterministic product retrieval
# ============================================================================


class TestDeterministicRetrieval:
    async def test_hard_filters_apply(self, product_repo):
        laptop_cheap = make_product("p1", "Budget Laptop", "laptop", Decimal("500"))
        laptop_expensive = make_product("p2", "Pro Laptop", "laptop", Decimal("2000"))
        out_of_stock = make_product("p3", "Sold Out Laptop", "laptop", Decimal("600"), in_stock=0)
        other_category = make_product("p4", "Gaming Mouse", "mouse", Decimal("100"))
        all_products = [laptop_cheap, laptop_expensive, out_of_stock, other_category]
        product_repo.distinct_field_values = AsyncMock(
            side_effect=lambda store, field: ["laptop", "mouse"] if field == "product_type" else []
        )

        def simulate(filters, limit=30):
            result = []
            for p in all_products:
                if p.store_id != filters["store_id"] or p.status != filters["status"]:
                    continue
                if "vendor" in filters and not re.search(filters["vendor"]["$regex"], p.vendor or "", re.IGNORECASE):
                    continue
                or_clause = filters.get("$or")
                if or_clause:
                    matched = any(
                        (cond.get("product_type") and p.product_type in cond["product_type"]["$in"])
                        or (cond.get("category_id") and p.category_id in cond["category_id"]["$in"])
                        for cond in or_clause
                    )
                    if not matched:
                        continue
                title = filters.get("title")
                if title and not re.search(title["$regex"], p.title or "", re.IGNORECASE):
                    continue
                result.append(p)
            return result

        product_repo.find_many.side_effect = simulate

        intent = RecommendationIntent(product_type="laptop", max_budget=800, currency="USD")
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-1", product_repo)

        assert [c.id for c in candidates] == ["p1"]
        filters = product_repo.find_many.await_args.args[0]
        assert filters["store_id"] == "store-1"
        assert filters["status"] == "active"
        assert filters["$or"] == [{"product_type": {"$in": ["laptop"]}}]

    async def test_brand_is_a_hard_filter(self, product_repo):
        product_repo.find_many.return_value = [
            make_product("p1", "Dell Laptop", "laptop", Decimal("700"), vendor="Dell"),
            make_product("p2", "HP Laptop", "laptop", Decimal("700"), vendor="HP"),
        ]
        intent = RecommendationIntent(product_type="laptop", brand="Dell", currency="USD")
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-1", product_repo)
        assert [c.id for c in candidates] == ["p1"]

    async def test_explicit_requirements_exclude_contradictions(self, product_repo):
        black_dress = make_product("p1", "Black Dress", "dress", Decimal("50"))
        black_dress.options = [ProductOption(id="o1", name="color", values=["black", "navy"])]
        red_dress = make_product("p2", "Red Dress", "dress", Decimal("50"))
        red_dress.options = [ProductOption(id="o2", name="color", values=["red", "pink"])]
        product_repo.find_many.return_value = [black_dress, red_dress]
        intent = RecommendationIntent(
            product_type="dress",
            currency="USD",
            required_specs=[{"name": "color", "value": "black"}],
        )
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-1", product_repo)
        assert [c.id for c in candidates] == ["p1"]

    async def test_price_filter_is_deterministic(self, product_repo):
        product_repo.find_many.return_value = [
            make_product("p1", "Mouse A", "mouse", Decimal("20")),
            make_product("p2", "Mouse B", "mouse", Decimal("60")),
        ]
        intent = RecommendationIntent(product_type="mouse", max_budget=40, currency="USD")
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-1", product_repo)
        assert [c.id for c in candidates] == ["p1"]

    async def test_availability_is_a_hard_filter(self, product_repo):
        product_repo.find_many.return_value = [
            make_product("p1", "Mouse A", "mouse", Decimal("20"), in_stock=0),
            make_product("p2", "Mouse B", "mouse", Decimal("20"), in_stock=3),
        ]
        intent = RecommendationIntent(product_type="mouse", currency="USD")
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-1", product_repo)
        assert [c.id for c in candidates] == ["p2"]

    async def test_catalog_first_vector_is_fallback(self, retriever, product_repo, llm):
        product_repo.find_many.return_value = [
            make_product("p1", "Laptop X", "laptop", Decimal("799")),
        ]
        agent = RecommendationAgent(retriever_service=retriever, product_repo=product_repo, llm=llm)
        response = await agent.run(
            query="I need a laptop around $800 for programming",
            store_id="store-1",
        )
        assert [p.product_id for p in response.products] == ["p1"]
        assert response.products[0].price == Decimal("799")
        retriever.search.assert_not_awaited()

    async def test_vector_used_when_catalog_empty(self, retriever, product_repo, llm):
        product_repo.find_many.return_value = []
        agent = RecommendationAgent(retriever_service=retriever, product_repo=product_repo, llm=llm)
        await agent.run(query="gaming laptop", store_id="store-1")
        assert retriever.search.await_count == 1


# ============================================================================
# Fix 4.3 — Ranking
# ============================================================================


class TestRanking:
    def _candidate(self, product_id: str, price: Decimal) -> ScoredProduct:
        return ScoredProduct(
            product_id=product_id,
            store_id="store-1",
            title=f"{product_id} title",
            price=price,
            currency="USD",
            in_stock=True,
            stock_quantity=10,
            price_resolved=True,
            match_score=0.0,
        )

    def test_ranked_by_deterministic_weights(self):
        intent = RecommendationIntent(
            product_type="laptop",
            use_case="programming",
            max_budget=800,
            currency="USD",
            required_specs=[{"name": "ram", "value": "16GB"}],
        )
        exact_match = ScoredProduct(
            product_id="exact",
            store_id="store-1",
            title="Programming Laptop 16GB",
            description="16GB ram, for programming",
            price=Decimal("700"),
            currency="USD",
            in_stock=True,
            stock_quantity=10,
            price_resolved=True,
        )
        category_only = ScoredProduct(
            product_id="category-only",
            store_id="store-1",
            title="Some Laptop",
            price=Decimal("750"),
            currency="USD",
            in_stock=True,
            stock_quantity=10,
            price_resolved=True,
        )
        ranked = RecommendationCatalogService.rank_candidates([category_only, exact_match], intent)
        assert [p.product_id for p in ranked] == ["exact", "category-only"]
        assert ranked[0].score > ranked[1].score
        assert ranked[0].rank == 1
        assert ranked[1].rank == 2

    def test_cheaper_product_wins_ties(self):
        intent = RecommendationIntent(product_type="laptop", max_budget=800, currency="USD")
        expensive = self._candidate("expensive", Decimal("750"))
        cheap = self._candidate("cheap", Decimal("650"))
        ranked = RecommendationCatalogService.rank_candidates([expensive, cheap], intent)
        assert ranked[0].product_id == "cheap"

    def test_brand_preference_boosts(self):
        dell = ScoredProduct(
            product_id="dell",
            store_id="store-1",
            title="Dell Laptop",
            price=Decimal("750"),
            currency="USD",
            specs=[],
            in_stock=True,
            stock_quantity=10,
            price_resolved=True,
        )
        hp = ScoredProduct(
            product_id="hp",
            store_id="store-1",
            title="HP Laptop",
            price=Decimal("750"),
            currency="USD",
            specs=[],
            in_stock=True,
            stock_quantity=10,
            price_resolved=True,
        )
        intent = RecommendationIntent(product_type="laptop", brand="Dell", max_budget=800, currency="USD")
        ranked = RecommendationCatalogService.rank_candidates([hp, dell], intent)
        assert ranked[0].product_id == "dell"


# ============================================================================
# Fix 4.4 — Discount-aware recommendation
# ============================================================================


class TestDiscountStrategy:
    def test_discount_brings_price_into_budget(self):
        product = make_product("p1", "Widget", "widget", Decimal("50"), max_discount_pct=20.0)
        candidates = RecommendationCatalogService.build_scored_candidates([product])
        RecommendationCatalogService.apply_discount_strategy(candidates, 40.0)
        assert candidates[0].discount_available is True
        assert candidates[0].discount_pct == 20.0
        assert candidates[0].final_price == Decimal("40.00")

    def test_no_discount_when_max_is_zero(self):
        product = make_product("p1", "Widget", "widget", Decimal("50"))
        candidates = RecommendationCatalogService.build_scored_candidates([product])
        RecommendationCatalogService.apply_discount_strategy(candidates, 40.0)
        assert candidates[0].discount_available is False
        assert candidates[0].final_price is None

    def test_discount_never_applied_when_price_already_fits(self):
        product = make_product("p1", "Widget", "widget", Decimal("30"), max_discount_pct=50.0)
        candidates = RecommendationCatalogService.build_scored_candidates([product])
        RecommendationCatalogService.apply_discount_strategy(candidates, 40.0)
        assert candidates[0].discount_available is False
        assert candidates[0].final_price is None

    def test_discount_not_enough_is_not_applied(self):
        product = make_product("p1", "Widget", "widget", Decimal("50"), max_discount_pct=10.0)
        candidates = RecommendationCatalogService.build_scored_candidates([product])
        RecommendationCatalogService.apply_discount_strategy(candidates, 40.0)
        assert candidates[0].discount_available is False
        assert candidates[0].final_price is None

    async def test_above_budget_discountable_candidate_survives_filter(self, product_repo):
        product = make_product("p1", "Widget", "widget", Decimal("50"), max_discount_pct=20.0)
        product_repo.find_by_id.return_value = product
        candidates = [ScoredProduct(product_id="p1", title="Widget", store_id="store-1")]
        state: RecommendationState = {
            "user_query": "widget",
            "store_id": "store-1",
            "customer_id": None,
            "shopping_state": None,
            "intent": RecommendationIntent(product_type="widget", max_budget=40, currency="USD"),
            "candidates": candidates,
            "filtered": [],
            "ranked": [],
            "clarifying_question": None,
            "response": None,
            "error": None,
        }
        out = await filter_inventory_node(state, product_repo)
        assert len(out["filtered"]) == 1
        assert out["filtered"][0].discount_available is True
        assert out["filtered"][0].final_price == Decimal("40.00")

    async def test_above_budget_not_discountable_is_dropped(self, product_repo):
        product = make_product("p1", "Widget", "widget", Decimal("50"))
        product_repo.find_by_id.return_value = product
        candidates = [ScoredProduct(product_id="p1", title="Widget", store_id="store-1")]
        state: RecommendationState = {
            "user_query": "widget",
            "store_id": "store-1",
            "customer_id": None,
            "shopping_state": None,
            "intent": RecommendationIntent(product_type="widget", max_budget=40, currency="USD"),
            "candidates": candidates,
            "filtered": [],
            "ranked": [],
            "clarifying_question": None,
            "response": None,
            "error": None,
        }
        out = await filter_inventory_node(state, product_repo)
        assert out["filtered"] == []


# ============================================================================
# Fix 4.5 — Structured recommendation result
# ============================================================================


class TestStructuredResult:
    async def test_response_carries_structured_fields(self, retriever, product_repo, llm):
        product_repo.find_many.return_value = [
            make_product("p1", "Widget", "widget", Decimal("50"), max_discount_pct=20.0),
        ]
        llm.structured_output.return_value.message.content = (
            '{"category": "widget", "budget": 40, "currency": "USD", '
            '"use_case": "gadget", "brand": null, "attributes": {}, '
            '"required_specs": [], "min_quality": null, "hidden_needs": []}'
        )
        agent = RecommendationAgent(retriever_service=retriever, product_repo=product_repo, llm=llm)
        llm.chat.return_value.message.content = "The Widget fits your $40 budget at $40 after a 20% discount."
        response = await agent.run(
            query="I need a widget around $40",
            store_id="store-1",
        )
        assert isinstance(response, RecommendationResponse)
        assert response.type == "recommendation"
        assert response.budget == 40.0
        assert response.discount_available is True
        assert response.discount == 20.0
        assert response.final_price == 40.0
        assert response.rationale is not None
        assert len(response.products) == 1

    async def test_rationale_falls_back_without_llm(self):
        intent = RecommendationIntent(product_type="laptop", max_budget=800, currency="USD")
        ranked = [
            ScoredProduct(
                product_id="p1",
                store_id="store-1",
                title="Laptop",
                price=Decimal("700"),
                currency="USD",
                price_resolved=True,
            )
        ]
        state: RecommendationState = {
            "user_query": "laptop",
            "store_id": "store-1",
            "customer_id": None,
            "shopping_state": None,
            "intent": intent,
            "candidates": [],
            "filtered": [],
            "ranked": ranked,
            "clarifying_question": None,
            "response": None,
            "error": None,
        }
        out = await format_response_node(state, llm=None)
        response = out["response"]
        assert response.type == "recommendation"
        assert response.budget == 800.0
        assert response.discount_available is False
        assert response.final_price is None
        assert "Laptop" in response.rationale

    async def test_rank_node_orders_results(self):
        intent = RecommendationIntent(product_type="laptop", max_budget=800, currency="USD")
        expensive = ScoredProduct(
            product_id="p2",
            store_id="store-1",
            title="Laptop Pro",
            price=Decimal("799"),
            currency="USD",
            price_resolved=True,
            in_stock=True,
            stock_quantity=10,
        )
        cheap = ScoredProduct(
            product_id="p1",
            store_id="store-1",
            title="Laptop Basic",
            price=Decimal("500"),
            currency="USD",
            price_resolved=True,
            in_stock=True,
            stock_quantity=10,
        )
        state: RecommendationState = {
            "user_query": "laptop",
            "store_id": "store-1",
            "customer_id": None,
            "shopping_state": None,
            "intent": intent,
            "candidates": [],
            "filtered": [expensive, cheap],
            "ranked": [],
            "clarifying_question": None,
            "response": None,
            "error": None,
        }
        out = await rank_candidates_node(state)
        assert [p.product_id for p in out["ranked"]] == ["p1", "p2"]
