from unittest.mock import AsyncMock

import pytest

from app.application.recommendation.dto.recommendation_dto import (
    RecommendationResponse,
)
from app.application.recommendation.services import RecommendationService


@pytest.fixture
def retriever():
    r = AsyncMock()
    r.search.return_value.results = []
    return r


@pytest.fixture
def product_repo():
    r = AsyncMock()
    r.find_by_id.return_value = None
    return r


@pytest.fixture
def llm():
    l = AsyncMock()
    l.structured_output.return_value.message.content = (
        '{"product_type": "laptop", "use_case": "gaming", '
        '"required_specs": [], "max_budget": 1500.0, '
        '"min_quality": null, "hidden_needs": []}'
    )
    return l


@pytest.fixture
def service(retriever, product_repo, llm):
    return RecommendationService(
        retriever_service=retriever,
        product_repo=product_repo,
        llm=llm,
    )


class TestRecommendationService:
    async def test_recommend_returns_response(self, service):
        result = await service.recommend(
            query="gaming laptop under $1500",
            store_id="store_1",
            customer_id="cust_1",
        )
        assert isinstance(result, RecommendationResponse)
        assert result.query == "gaming laptop under $1500"
        assert result.store_id == "store_1"
        assert result.customer_id == "cust_1"

    async def test_recommend_without_customer_id(self, service):
        result = await service.recommend(
            query="laptop",
            store_id="store_1",
        )
        assert result.customer_id is None
        assert result.total_count >= 0

    async def test_recommend_empty_query(self, service, llm):
        llm.structured_output.return_value.message.content = (
            '{"product_type": null, "use_case": null, '
            '"required_specs": [], "max_budget": null, '
            '"min_quality": null, "hidden_needs": []}'
        )
        result = await service.recommend(
            query="",
            store_id="store_1",
        )
        assert result.total_count == 0

    async def test_recommend_passes_shopping_state_from_context(self, service, retriever, llm):
        """The coordinator's context must carry the recalled state to the search (Fix 3.5)."""
        llm.structured_output.return_value.message.content = (
            '{"product_type": null, "use_case": null, "required_specs": [], '
            '"max_budget": null, "min_quality": null, "hidden_needs": []}'
        )
        await service.recommend(
            query="Programming",
            store_id="store_1",
            context={
                "conversation": {
                    "shopping_state": {
                        "intent": "product_recommendation",
                        "category": "laptop",
                        "budget": 800,
                        "currency": "USD",
                        "color": None,
                        "size": None,
                        "brand": None,
                        "use_case": "programming",
                    }
                },
                "memory": {},
            },
        )

        search_query = retriever.search.await_args.kwargs["query"]
        assert "laptop" in search_query
        assert "programming" in search_query

    async def test_recommend_reads_state_from_recalled_memory_entries(self, service, retriever, llm):
        llm.structured_output.return_value.message.content = (
            '{"product_type": null, "use_case": null, "required_specs": [], '
            '"max_budget": null, "min_quality": null, "hidden_needs": []}'
        )
        await service.recommend(
            query="Programming",
            store_id="store_1",
            context={
                "conversation": {},
                "memory": {
                    "recall_source": "merged",
                    "entries": {
                        "shopping_state": {
                            "intent": "product_recommendation",
                            "category": "laptop",
                            "budget": 800,
                            "use_case": "programming",
                        }
                    },
                },
            },
        )

        search_query = retriever.search.await_args.kwargs["query"]
        assert "laptop" in search_query
        assert "programming" in search_query
