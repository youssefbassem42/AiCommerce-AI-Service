from unittest.mock import AsyncMock

import pytest

from app.application.recommendation.dto.recommendation_dto import BundleResponse
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
def service(product_repo, llm):
    return BundleSuggestionService(product_repo=product_repo, llm=llm)


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
