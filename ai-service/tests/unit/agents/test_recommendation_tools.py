from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.agents.recommendation.tools import (
    build_product_cards,
    parse_intent,
    search_spec_vectors,
    filter_inventory,
    apply_budget_filter,
)
from app.application.recommendation.dto.recommendation_dto import (
    ProductCard,
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
        assert intent.required_specs == [{"ram": ">= 16GB"}]
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


class TestFilterInventory:
    async def test_empty_candidates(self):
        results = await filter_inventory([], AsyncMock())
        assert results == []

    async def test_filters_out_of_stock(self):
        repo = AsyncMock()
        candidates = [
            ScoredProduct(product_id="p1", title="P1", store_id="s1"),
            ScoredProduct(product_id="p2", title="P2", store_id="s1"),
        ]

        p1 = Product(id="p1", store_id="s1", organization_id="o1", title="P1",
                     variants=[Variant(id="v1", sku="S1", title="V1",
                                       price=Money(amount=Decimal("10")))])
        p1.variants[0].inventory_quantity = 0

        p2 = Product(id="p2", store_id="s1", organization_id="o1", title="P2",
                     variants=[Variant(id="v2", sku="S2", title="V2",
                                       price=Money(amount=Decimal("20")))])
        p2.variants[0].inventory_quantity = 5

        repo.find_by_id.side_effect = [p1, p2]

        filtered = await filter_inventory(candidates, repo)
        assert len(filtered) == 1
        assert filtered[0].product_id == "p2"


class TestApplyBudgetFilter:
    async def test_no_budget_returns_all(self):
        repo = AsyncMock()
        candidates = [ScoredProduct(product_id="p1", title="P1", store_id="s1")]
        result = await apply_budget_filter(candidates, None, repo)
        assert len(result) == 1

    async def test_filters_by_budget(self):
        repo = AsyncMock()
        candidates = [
            ScoredProduct(product_id="p1", title="P1", store_id="s1"),
            ScoredProduct(product_id="p2", title="P2", store_id="s1"),
        ]
        repo.find_by_id.side_effect = [
            Product(id="p1", store_id="s1", organization_id="o1", title="P1",
                    variants=[Variant(id="v1", sku="S1", title="V1",
                                      price=Money(amount=Decimal("1000")))],
                    ),
            Product(id="p2", store_id="s1", organization_id="o1", title="P2",
                    variants=[Variant(id="v2", sku="S2", title="V2",
                                      price=Money(amount=Decimal("100")))],
                    ),
        ]

        result = await apply_budget_filter(candidates, 500.0, repo)
        assert len(result) == 1
        assert result[0].product_id == "p2"


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
