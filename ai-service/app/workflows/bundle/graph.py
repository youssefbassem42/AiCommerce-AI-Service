import logging
from typing import Optional

from app.agents.bundle.agent import BundleSuggestionAgent
from app.application.recommendation.dto.recommendation_dto import BundleResponse
from app.application.recommendation.promo_service import PromoCodeService
from app.domain.commerce.repositories import ProductRepository
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class BundleSuggestionWorkflow:
    def __init__(
        self,
        product_repo: ProductRepository,
        llm: BaseLLMProvider,
        promo_service: Optional[PromoCodeService] = None,
    ):
        self._agent = BundleSuggestionAgent(
            product_repo=product_repo,
            llm=llm,
            promo_service=promo_service,
        )

    async def run(
        self,
        query: str,
        store_id: str,
        customer_id: Optional[str] = None,
        store_capabilities: Optional[dict[str, bool]] = None,
    ) -> BundleResponse:
        return await self._agent.run(
            query=query,
            store_id=store_id,
            customer_id=customer_id,
            store_capabilities=store_capabilities,
        )
