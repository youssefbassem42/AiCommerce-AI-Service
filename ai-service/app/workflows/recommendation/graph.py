import logging
from typing import Any

from app.agents.recommendation.agent import RecommendationAgent
from app.application.knowledge.retrieval.service import RetrieverService
from app.application.recommendation.dto.recommendation_dto import RecommendationResponse
from app.domain.commerce.repositories import ProductRepository
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class RecommendationWorkflow:
    def __init__(
        self,
        retriever_service: RetrieverService,
        product_repo: ProductRepository,
        llm: BaseLLMProvider,
    ):
        self._agent = RecommendationAgent(
            retriever_service=retriever_service,
            product_repo=product_repo,
            llm=llm,
        )

    async def run(
        self,
        query: str,
        store_id: str,
        customer_id: str | None = None,
        history: list[dict[str, Any]] | None = None,  # noqa: ARG002 - uniform sub-agent runner contract
        conversation_id: str | None = None,  # noqa: ARG002 - uniform sub-agent runner contract
        shopping_state: dict[str, Any] | None = None,
    ) -> RecommendationResponse:
        return await self._agent.run(
            query=query,
            store_id=store_id,
            customer_id=customer_id,
            shopping_state=shopping_state,
        )
