from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.recommendation.dto.recommendation_dto import (
    BundleCandidate,
    BundleResponse,
    DiscountInfo,
)
from app.application.recommendation.services import BundleSuggestionService


@pytest.fixture
def product_repo():
    r = AsyncMock()
    r.find_many.return_value = []
    return r


@pytest.fixture
def llm():
    l = AsyncMock()
    l.structured_output.return_value.message.content = (
        '{"budget": 300.0, "desired_items": ["monitor"], "use_case": "office"}'
    )
    return l


@pytest.fixture
def capabilities_repo():
    repo = AsyncMock()
    repo.get_or_detect.return_value = MagicMock(capabilities={"has_promo_codes": False})
    return repo


@pytest.fixture
def recommendation_repo():
    return AsyncMock()


@pytest.fixture
def service(product_repo, llm, capabilities_repo, recommendation_repo):
    return BundleSuggestionService(
        product_repo=product_repo,
        llm=llm,
        capabilities_repo=capabilities_repo,
        recommendation_repo=recommendation_repo,
    )


def _bundle_response(**overrides):
    response = BundleResponse(
        query="gaming setup",
        store_id="store_1",
        customer_id="cust_1",
        bundles=[
            BundleCandidate(
                products=[DiscountInfo(product_id="p1", product_title="GPU")],
                total_original=Decimal("200"),
                total_discount=Decimal("40"),
                total_after_discount=Decimal("160"),
                rank=1,
            ),
            BundleCandidate(
                products=[DiscountInfo(product_id="p2", product_title="Mouse")],
                total_original=Decimal("50"),
                total_discount=Decimal("5"),
                total_after_discount=Decimal("45"),
                rank=2,
            ),
        ],
    )
    return response.model_copy(update=overrides)


class TestBundleSuggestionService:
    async def test_suggest_returns_response(self, service):
        result = await service.suggest(
            query="I have $300 and want a monitor",
            store_id="store_1",
            customer_id="cust_1",
        )
        assert isinstance(result, BundleResponse)
        assert result.query == "I have $300 and want a monitor"
        assert result.store_id == "store_1"
        assert result.customer_id == "cust_1"

    async def test_suggest_without_customer_id(self, service):
        result = await service.suggest(
            query="$500 for a gaming setup",
            store_id="store_1",
        )
        assert result.customer_id is None

    async def test_suggest_persists_top_bundle(self, service, recommendation_repo):
        service._workflow.run = AsyncMock(return_value=_bundle_response())
        result = await service.suggest(
            query="gaming setup",
            store_id="store_1",
            customer_id="cust_1",
        )
        assert result is not None
        recommendation_repo.save_bundle_suggestion.assert_awaited_once()
        saved = recommendation_repo.save_bundle_suggestion.await_args.args[0]
        assert saved.store_id == "store_1"
        assert saved.product_ids == ["p1"]
        assert saved.total_price == 160.0
        assert saved.discount_percentage == 20.0
        assert saved.status == "active"

    async def test_suggest_skips_persistence_without_products(self, service, recommendation_repo):
        service._workflow.run = AsyncMock(return_value=_bundle_response(bundles=[BundleCandidate(products=[], rank=1)]))
        await service.suggest(query="nothing", store_id="store_1")
        recommendation_repo.save_bundle_suggestion.assert_not_awaited()

    async def test_suggest_ignores_persistence_failure(self, service, recommendation_repo):
        service._workflow.run = AsyncMock(return_value=_bundle_response())
        recommendation_repo.save_bundle_suggestion.side_effect = Exception("db down")
        result = await service.suggest(query="gaming setup", store_id="store_1")
        assert isinstance(result, BundleResponse)
