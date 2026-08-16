from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.agents.recommendation.tools import (
    apply_budget_filter,
    build_product_cards,
    filter_inventory,
    parse_intent,
    search_spec_vectors,
)
from app.application.recommendation.dto.recommendation_dto import (
    RecommendationIntent,
    ScoredProduct,
)
from app.domain.commerce.aggregates.product import Product, Variant
from app.domain.commerce.value_objects.money import Money


class TestParseIntent:
    async def test_parse_intent_success(self, mock_provider):
        query = "I need a laptop for gaming under $1500"
        mock_provider.structured_output.return_value.message.content = (
            '{"product_type": "laptop", "use_case": "gaming", '
            '"required_specs": [{"ram": ">= 16GB"}], '
            '"max_budget": 1500.0, "min_quality": "premium", '
            '"hidden_needs": ["high refresh rate", "dedicated GPU"]}'
        )

        intent = await parse_intent(query, llm=mock_provider)
        assert intent.product_type == "laptop"
        assert intent.use_case == "gaming"
        assert intent.max_budget == 1500.0
        assert intent.required_specs == [{"name": "ram", "value": ">= 16GB"}]
        assert intent.attributes == {"ram": ">= 16GB"}
        assert intent.hidden_needs == ["high refresh rate", "dedicated GPU"]

    async def test_parse_intent_minimal(self, mock_provider):
        query = "phone stand"
        mock_provider.structured_output.return_value.message.content = (
            '{"product_type": "phone stand", "use_case": null, '
            '"required_specs": [], "max_budget": null, '
            '"min_quality": null, "hidden_needs": []}'
        )

        intent = await parse_intent(query, llm=mock_provider)
        assert intent.product_type == "phone stand"
        assert intent.use_case is None
        assert intent.max_budget is None


class TestSearchSpecVectors:
    async def test_empty_intent_returns_empty(self):
        intent = RecommendationIntent()
        retriever = AsyncMock()

        results = await search_spec_vectors(intent, retriever, "store_1")
        assert results == []

    async def test_search_with_product_type(self):
        intent = RecommendationIntent(product_type="laptop", use_case="gaming")
        retriever = AsyncMock()
        retriever.search.return_value.results = []

        results = await search_spec_vectors(intent, retriever, "store_1")
        assert results == []

    async def test_search_requests_entity_type_product(self):
        intent = RecommendationIntent(product_type="laptop")
        retriever = AsyncMock()
        retriever.search.return_value.results = []

        await search_spec_vectors(intent, retriever, "store_1")

        kwargs = retriever.search.call_args.kwargs
        filters = kwargs["filters"]
        assert filters.store_id == "store_1"
        assert filters.entity_type == "product"

    async def test_search_skips_non_product_payloads(self):
        intent = RecommendationIntent(product_type="laptop")
        retriever = AsyncMock()
        retriever.search.return_value.results = [
            SimpleNamespace(
                chunk_id="faq-1",
                score=0.9,
                metadata={"entity_type": "knowledge", "content": "What is a laptop?"},
            ),
            SimpleNamespace(
                chunk_id="prod-1",
                score=0.8,
                metadata={
                    "entity_type": "product",
                    "product_id": "prod-1",
                    "product_title": "Laptop X",
                    "price": 499.0,
                    "content": "Laptop X specs",
                },
            ),
        ]

        results = await search_spec_vectors(intent, retriever, "store_1")

        assert len(results) == 1
        assert results[0].product_id == "prod-1"


class TestFilterInventory:
    async def test_empty_candidates(self):
        results = await filter_inventory([], AsyncMock(), "s1")
        assert results == []

    async def test_filters_out_of_stock(self):
        repo = AsyncMock()
        candidates = [
            ScoredProduct(product_id="p1", title="P1", store_id="s1"),
            ScoredProduct(product_id="p2", title="P2", store_id="s1"),
        ]

        p1 = Product(
            id="p1",
            store_id="s1",
            organization_id="o1",
            title="P1",
            variants=[Variant(id="v1", sku="S1", title="V1", price=Money(amount=Decimal("10")))],
        )
        p1.variants[0].inventory_quantity = 0

        p2 = Product(
            id="p2",
            store_id="s1",
            organization_id="o1",
            title="P2",
            variants=[Variant(id="v2", sku="S2", title="V2", price=Money(amount=Decimal("20")))],
        )
        p2.variants[0].inventory_quantity = 5

        repo.find_by_id.side_effect = [p1, p2]

        filtered = await filter_inventory(candidates, repo, "s1")
        assert len(filtered) == 1
        assert filtered[0].product_id == "p2"

    async def test_discards_candidate_without_catalog_product(self):
        repo = AsyncMock()
        repo.find_by_id.return_value = None
        candidates = [
            ScoredProduct(product_id="ghost-1", title="FAQ chunk", store_id="s1", price=Decimal("0")),
        ]

        filtered = await filter_inventory(candidates, repo, "s1")

        assert filtered == []

    async def test_discards_candidate_when_lookup_fails(self):
        repo = AsyncMock()
        repo.find_by_id.side_effect = RuntimeError("db down")
        candidates = [ScoredProduct(product_id="p1", title="P1", store_id="s1")]

        filtered = await filter_inventory(candidates, repo, "s1")

        assert filtered == []

    async def test_discards_product_without_real_price(self):
        repo = AsyncMock()
        repo.find_by_id.return_value = Product(
            id="p1",
            store_id="s1",
            organization_id="o1",
            title="No price",
            variants=[],
        )
        candidates = [
            ScoredProduct(product_id="p1", title="No price", store_id="s1", price=Decimal("0")),
        ]

        filtered = await filter_inventory(candidates, repo, "s1")

        assert filtered == []

    async def test_enriches_price_from_catalog(self):
        repo = AsyncMock()
        repo.find_by_id.return_value = Product(
            id="p1",
            store_id="s1",
            organization_id="o1",
            title="Laptop",
            variants=[
                Variant(id="v1", sku="S1", title="V1", price=Money(amount=Decimal("499"), currency="USD")),
            ],
        )
        repo.find_by_id.return_value.variants[0].inventory_quantity = 3
        candidates = [
            ScoredProduct(product_id="p1", title="Stale payload title", store_id="s1", price=Decimal("0")),
        ]

        filtered = await filter_inventory(candidates, repo, "s1")

        assert len(filtered) == 1
        assert filtered[0].price == Decimal("499")
        assert filtered[0].title == "Laptop"

    async def test_discards_product_belonging_to_another_store(self):
        repo = AsyncMock()
        repo.find_by_id.return_value = Product(
            id="p1",
            store_id="s2",
            organization_id="o2",
            title="Other store laptop",
            variants=[
                Variant(id="v1", sku="S1", title="V1", price=Money(amount=Decimal("499"), currency="USD")),
            ],
        )
        repo.find_by_id.return_value.variants[0].inventory_quantity = 3
        candidates = [
            ScoredProduct(product_id="p1", title="Other store laptop", store_id="s1", price=Decimal("0")),
        ]

        filtered = await filter_inventory(candidates, repo, "s1")

        assert filtered == []


class TestApplyBudgetFilter:
    async def test_no_budget_returns_all(self):
        repo = AsyncMock()
        candidates = [ScoredProduct(product_id="p1", title="P1", store_id="s1")]
        result = await apply_budget_filter(candidates, None, repo, "s1")
        assert len(result) == 1

    async def test_filters_by_budget(self):
        repo = AsyncMock()
        candidates = [
            ScoredProduct(product_id="p1", title="P1", store_id="s1"),
            ScoredProduct(product_id="p2", title="P2", store_id="s1"),
        ]
        repo.find_by_id.side_effect = [
            Product(
                id="p1",
                store_id="s1",
                organization_id="o1",
                title="P1",
                variants=[Variant(id="v1", sku="S1", title="V1", price=Money(amount=Decimal("1000")))],
            ),
            Product(
                id="p2",
                store_id="s1",
                organization_id="o1",
                title="P2",
                variants=[Variant(id="v2", sku="S2", title="V2", price=Money(amount=Decimal("100")))],
            ),
        ]

        result = await apply_budget_filter(candidates, 500.0, repo, "s1")
        assert len(result) == 1
        assert result[0].product_id == "p2"

    async def test_budget_uses_catalog_price_not_payload_price(self):
        repo = AsyncMock()
        repo.find_by_id.return_value = Product(
            id="p1",
            store_id="s1",
            organization_id="o1",
            title="P1",
            variants=[Variant(id="v1", sku="S1", title="V1", price=Money(amount=Decimal("600")))],
        )
        candidates = [
            ScoredProduct(product_id="p1", title="P1", store_id="s1", price=Decimal("10")),
        ]

        result = await apply_budget_filter(candidates, 500.0, repo, "s1")

        assert result == []

    async def test_discards_zero_price_candidate(self):
        repo = AsyncMock()
        repo.find_by_id.return_value = None
        candidates = [
            ScoredProduct(product_id="ghost-1", title="P1", store_id="s1", price=Decimal("0")),
        ]

        result = await apply_budget_filter(candidates, 500.0, repo, "s1")

        assert result == []


class TestBuildProductCards:
    def test_builds_cards(self):
        products = [
            ScoredProduct(product_id="p1", title="Laptop", store_id="s1", match_score=0.9),
            ScoredProduct(product_id="p2", title="Monitor", store_id="s1", match_score=0.8),
        ]
        cards = build_product_cards(products)
        assert len(cards) == 2
        assert cards[0].product_id == "p1"
        assert cards[1].product_id == "p2"

    def test_empty_list(self):
        cards = build_product_cards([])
        assert cards == []
