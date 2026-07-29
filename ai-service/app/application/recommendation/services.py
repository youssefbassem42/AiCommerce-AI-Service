import logging
from typing import Optional

from app.application.knowledge.retrieval.service import RetrieverService
from app.application.recommendation.dto.recommendation_dto import (
    BundleResponse,
    RecommendationResponse,
)
from app.application.recommendation.promo_service import PromoCodeService
from app.domain.commerce.repositories import ProductRepository
from app.domain.recommendation.repositories.store_capabilities_repository import (
    StoreCapabilitiesRepository,
)
from app.infrastructure.providers.base import BaseLLMProvider
from app.workflows.bundle.graph import BundleSuggestionWorkflow
from app.workflows.recommendation.graph import RecommendationWorkflow

logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(
        self,
        retriever_service: RetrieverService,
        product_repo: ProductRepository,
        llm: BaseLLMProvider,
    ):
        self._workflow = RecommendationWorkflow(
            retriever_service=retriever_service,
            product_repo=product_repo,
            llm=llm,
        )

    async def recommend(
        self,
        query: str,
        store_id: str,
        customer_id: Optional[str] = None,
    ) -> RecommendationResponse:
        logger.info(
            "Recommendation requested: query='%s', store_id='%s', customer_id='%s'",
            query, store_id, customer_id,
        )
        return await self._workflow.run(
            query=query,
            store_id=store_id,
            customer_id=customer_id,
        )


class BundleSuggestionService:
    def __init__(
        self,
        product_repo: ProductRepository,
        llm: BaseLLMProvider,
        capabilities_repo: StoreCapabilitiesRepository,
        promo_service: Optional[PromoCodeService] = None,
    ):
        self._capabilities_repo = capabilities_repo
        self._workflow = BundleSuggestionWorkflow(
            product_repo=product_repo,
            llm=llm,
            promo_service=promo_service or PromoCodeService(),
        )

    async def suggest(
        self,
        query: str,
        store_id: str,
        customer_id: Optional[str] = None,
    ) -> BundleResponse:
        logger.info(
            "Bundle suggestion requested: query='%s', store_id='%s', customer_id='%s'",
            query, store_id, customer_id,
        )

        caps = await self._capabilities_repo.get_or_detect(store_id)
        store_capabilities = dict(caps.capabilities)

        return await self._workflow.run(
            query=query,
            store_id=store_id,
            customer_id=customer_id,
            store_capabilities=store_capabilities,
        )
