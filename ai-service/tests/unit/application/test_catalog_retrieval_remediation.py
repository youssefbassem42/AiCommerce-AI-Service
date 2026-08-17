"""B1 remediation — catalog retrieval resolves against the store's own taxonomy.

Regression tests for the discovered bug: the catalog stores category names on
``product_type`` ("Electronics") and category ids on ``category_id`` ("1"),
while the parsed phrase is a plain category word ("electronics"). Retrieval
must resolve the phrase against the store's distinct taxonomy values, and
fall back to product-title matching when the taxonomy yields nothing.

Covers:
- Taxonomy retrieval via ``product_type`` distinct values
- Taxonomy retrieval via ``category_id`` when ``product_type`` is absent
- Product-title fallback when the taxonomy yields no candidates
- Budget / availability / brand hard filters on both paths
- Store scoping and query shape
"""

import re
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.application.recommendation.catalog_service import (
    RecommendationCatalogService,
    _taxonomy_match,
)
from app.application.recommendation.dto.recommendation_dto import RecommendationIntent
from app.domain.commerce.aggregates.product import Product
from app.domain.commerce.value_objects.money import Money


def make_product(
    product_id: str,
    title: str,
    store_id: str = "store-a",
    status: str = "active",
    product_type: str | None = None,
    category_id: str | None = None,
    vendor: str | None = None,
    price: Decimal = Decimal("100"),
    inventory_quantity: int = 5,
) -> Product:
    return Product(
        id=product_id,
        store_id=store_id,
        organization_id="org-1",
        title=title,
        product_type=product_type,
        category_id=category_id,
        vendor=vendor,
        status=status,
        variants=[],
        price=Money(amount=price, currency="USD"),
        inventory_quantity=inventory_quantity,
    )


class FakeCatalogRepo:
    """Minimal in-memory ProductRepository for retrieve_candidates."""

    def __init__(self, products: list[Product], distinct: dict[str, list[str]] | None = None):
        self.products = products
        self._distinct = distinct or {}
        self.queries: list[dict] = []

    async def find_many(self, filters: dict, limit: int = 30):
        self.queries.append(filters)
        result = []
        for p in self.products:
            if p.store_id != filters.get("store_id"):
                continue
            if p.status != filters.get("status", "active"):
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
            if title and title["$regex"].lower() not in (p.title or "").lower():
                continue
            result.append(p)
        return result[:limit]

    async def distinct_field_values(self, store_id: str, field: str) -> list[str]:
        if field in self._distinct:
            return list(self._distinct[field])
        return list(
            {getattr(p, field) for p in self.products if p.store_id == store_id and getattr(p, field) is not None}
        )


class TestTaxonomyMatch:
    @pytest.mark.parametrize(
        ("phrase", "value", "expected"),
        [
            ("electronics", "Electronics", True),
            ("Electronics", "Electronics", True),
            ("laptops", "Laptop", True),
            ("laptop", "Laptops", True),
            ("home appliances", "Home Appliances", True),
            ("smart home", "Smart-Home & Gadgets", True),
            ("beauty", "BEAUTY & PERSONAL CARE", True),
            ("electronics", "Fashion", False),
            ("", "Electronics", False),
            ("a", "Electronics", False),
            ("laptop", "L", False),
            ("coffee", "Laptop", False),
        ],
    )
    def test_matches(self, phrase, value, expected):
        assert _taxonomy_match(phrase, value) is expected


class TestCatalogTaxonomyRetrieval:
    def _catalog(self):
        products = [
            make_product("p1", "Gaming Laptop RTX", product_type="Electronics", category_id="1", price=Decimal("1500")),
            make_product("p2", "Laptop Backpack", product_type="Accessories", category_id="5", price=Decimal("55")),
            make_product("p3", "Standing Lamp", product_type="Lighting", category_id="6", price=Decimal("120")),
            make_product("p4", "Wireless Mouse", product_type=None, category_id="1", price=Decimal("30")),
            make_product("p5", "Office Chair", product_type="Furniture", category_id="8", price=Decimal("400")),
        ]
        return FakeCatalogRepo(products)

    async def test_taxonomy_retrieval_matches_store_product_type(self):
        repo = self._catalog()
        intent = RecommendationIntent(product_type="electronics", max_budget=Decimal("2000"), currency="USD")
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-a", repo)
        assert [c.id for c in candidates] == ["p1"]
        assert repo.queries[0]["$or"] == [{"product_type": {"$in": ["Electronics"]}}]

    async def test_phrase_with_suffix_matches_via_containment(self):
        repo = self._catalog()
        repo.products.append(
            make_product("p7", "Fridge", product_type="Home Appliances", category_id="3", price=Decimal("800"))
        )
        intent = RecommendationIntent(product_type="appliances", currency="USD")
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-a", repo)
        assert [c.id for c in candidates] == ["p7"]

    async def test_multi_word_phrase_matches_via_shared_token(self):
        repo = self._catalog()
        repo.products.append(
            make_product("p8", "Candle Holder", product_type="Home Decoration", category_id="4", price=Decimal("60"))
        )
        intent = RecommendationIntent(product_type="home decor", currency="USD")
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-a", repo)
        assert [c.id for c in candidates] == ["p8"]

    async def test_products_without_product_type_resolved_via_category_id(self):
        repo = self._catalog()
        intent = RecommendationIntent(product_type="1", currency="USD")
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-a", repo)
        assert [c.id for c in candidates] == ["p1", "p4"]

    async def test_title_fallback_when_taxonomy_yields_nothing(self):
        repo = self._catalog()
        intent = RecommendationIntent(product_type="laptop", currency="USD")
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-a", repo)
        assert [c.id for c in candidates] == ["p1", "p2"]
        assert "title" in repo.queries[-1]

    async def test_no_title_query_when_taxonomy_matched(self):
        repo = self._catalog()
        intent = RecommendationIntent(product_type="electronics", currency="USD")
        await RecommendationCatalogService.retrieve_candidates(intent, "store-a", repo)
        assert "title" not in repo.queries[0]

    async def test_budget_filter_applied_on_title_path(self):
        repo = self._catalog()
        intent = RecommendationIntent(product_type="laptop", max_budget=Decimal("100"), currency="USD")
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-a", repo)
        assert [c.id for c in candidates] == ["p2"]

    async def test_out_of_stock_excluded_on_taxonomy_path(self):
        repo = self._catalog()
        repo.products.append(
            make_product("p6", "Old TV", product_type="Electronics", category_id="1", inventory_quantity=0)
        )
        intent = RecommendationIntent(product_type="electronics", currency="USD")
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-a", repo)
        assert "p6" not in [c.id for c in candidates]

    async def test_store_isolation(self):
        repo = self._catalog()
        repo.products.append(make_product("p9", "Other Store Phone", store_id="store-b", product_type="Electronics"))
        intent = RecommendationIntent(product_type="electronics", currency="USD")
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-a", repo)
        assert "p9" not in [c.id for c in candidates]

    async def test_vendor_brand_filter_preserved(self):
        repo = self._catalog()
        intent = RecommendationIntent(product_type="electronics", brand="Dell", currency="USD")
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-a", repo)
        assert candidates == []

    async def test_no_product_type_returns_empty_without_querying(self):
        repo = self._catalog()
        intent = RecommendationIntent(product_type="", currency="USD")
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-a", repo)
        assert candidates == []
        assert repo.queries == []

    async def test_taxonomy_repo_error_falls_back_to_title(self):
        repo = self._catalog()

        class BrokenRepo(FakeCatalogRepo):
            async def distinct_field_values(self, store_id, field):
                raise RuntimeError("boom")

        broken = BrokenRepo(repo.products)
        intent = RecommendationIntent(product_type="laptop", currency="USD")
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-a", broken)
        assert [c.id for c in candidates] == ["p1", "p2"]
        assert "title" in broken.queries[-1]

    async def test_non_list_repo_result_returns_empty(self):
        repo = AsyncMock()
        repo.find_many = AsyncMock(return_value="not a list")
        repo.distinct_field_values = AsyncMock(return_value=["Electronics"])
        intent = RecommendationIntent(product_type="electronics", currency="USD")
        candidates = await RecommendationCatalogService.retrieve_candidates(intent, "store-a", repo)
        assert candidates == []
