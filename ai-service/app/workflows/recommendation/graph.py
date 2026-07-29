import logging
from typing import Optional

from app.agents.recommendation.agent import RecommendationAgent
from app.agents.recommendation.state import RecommendationState
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
        customer_id: Optional[str] = None,
    ) -> RecommendationResponse:
        return await self._agent.run(
            query=query,
            store_id=store_id,
            customer_id=customer_id,
        )
