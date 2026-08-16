import logging

from app.application.knowledge.retrieval.service import RetrieverService
from app.application.recommendation.dto.recommendation_dto import (
    BundleResponse,
    RecommendationResponse,
)
from app.application.recommendation.promo_service import PromoCodeService
from app.domain.commerce.repositories import ProductRepository
from app.domain.recommendation.entities.bundle_suggestion import BundleSuggestion
from app.domain.recommendation.repositories.recommendation_repository import (
    RecommendationRepository as IRecommendationRepository,
)
from app.domain.recommendation.repositories.store_capabilities_repository import (
    StoreCapabilitiesRepository,
)
from app.infrastructure.mongodb.repositories.recommendation_repository import (
    RecommendationRepository,
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
        customer_id: str | None = None,
        history: list | None = None,  # noqa: ARG002 - kept for uniform sub-agent runner contract
        conversation_id: str | None = None,  # noqa: ARG002 - kept for uniform sub-agent runner contract
        context: dict | None = None,
    ) -> RecommendationResponse:
        logger.info(
            "Recommendation requested: query='%s', store_id='%s', customer_id='%s'",
            query,
            store_id,
            customer_id,
        )
        from app.application.context.shopping_state import shopping_state_from_context

        shopping_state = shopping_state_from_context(context)
        return await self._workflow.run(
            query=query,
            store_id=store_id,
            customer_id=customer_id,
            history=history,
            conversation_id=conversation_id,
            shopping_state=shopping_state.to_dict() if not shopping_state.is_empty() else None,
        )


class BundleSuggestionService:
    def __init__(
        self,
        product_repo: ProductRepository,
        llm: BaseLLMProvider,
        capabilities_repo: StoreCapabilitiesRepository,
        promo_service: PromoCodeService | None = None,
        recommendation_repo: IRecommendationRepository | None = None,
    ):
        self._capabilities_repo = capabilities_repo
        self._recommendation_repo = recommendation_repo or RecommendationRepository()
        self._workflow = BundleSuggestionWorkflow(
            product_repo=product_repo,
            llm=llm,
            promo_service=promo_service or PromoCodeService(),
        )

    async def suggest(
        self,
        query: str,
        store_id: str,
        customer_id: str | None = None,
        history: list | None = None,  # noqa: ARG002 - kept for uniform sub-agent runner contract
        conversation_id: str | None = None,  # noqa: ARG002 - kept for uniform sub-agent runner contract
        context: dict | None = None,  # noqa: ARG002 - kept for uniform sub-agent runner contract
    ) -> BundleResponse:
        logger.info(
            "Bundle suggestion requested: query='%s', store_id='%s', customer_id='%s'",
            query,
            store_id,
            customer_id,
        )

        caps = await self._capabilities_repo.get_or_detect(store_id)
        store_capabilities = dict(caps.capabilities)

        result = await self._workflow.run(
            query=query,
            store_id=store_id,
            customer_id=customer_id,
            store_capabilities=store_capabilities,
        )

        await self._persist_top_bundle(result)

        return result

    async def _persist_top_bundle(self, result: BundleResponse) -> None:
        top = next((b for b in result.bundles if b.rank == 0), None)
        if top is None or not top.products:
            return
        total_original = float(top.total_original)
        discount_pct = (float(top.total_discount) / total_original * 100.0) if total_original > 0 else 0.0
        bundle = BundleSuggestion(
            id="",
            store_id=result.store_id,
            title=f"Bundle: {result.query}",
            product_ids=[p.product_id for p in top.products],
            total_price=float(top.total_after_discount),
            discount_percentage=round(discount_pct, 2),
        )
        try:
            await self._recommendation_repo.save_bundle_suggestion(bundle)
        except Exception as exc:
            logger.warning("Failed to persist bundle suggestion for store %s: %s", result.store_id, exc)
