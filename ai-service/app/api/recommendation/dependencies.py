from fastapi import Depends

from app.api.commerce.dependencies import get_product_repository
from app.api.knowledge.retrieval_dependencies import get_retriever_service
from app.application.knowledge.retrieval.service import RetrieverService
from app.application.recommendation.services import (
    BundleSuggestionService,
    RecommendationService,
)
from app.domain.recommendation.repositories.store_capabilities_repository import (
    StoreCapabilitiesRepository,
)
from app.infrastructure.mongodb.repositories.commerce_product_repository import (
    CommerceProductRepository,
)
from app.infrastructure.mongodb.repositories.store_capabilities_repository import (
    StoreCapabilitiesMongoRepository,
)
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory


def get_recommendation_llm() -> BaseLLMProvider:
    return LLMProviderFactory().get_provider("openrouter")


def get_capabilities_repository() -> StoreCapabilitiesRepository:
    return StoreCapabilitiesMongoRepository()


async def get_recommendation_service(
    retriever_service: RetrieverService = Depends(get_retriever_service),
    product_repo: CommerceProductRepository = Depends(get_product_repository),
    llm: BaseLLMProvider = Depends(get_recommendation_llm),
) -> RecommendationService:
    return RecommendationService(
        retriever_service=retriever_service,
        product_repo=product_repo,
        llm=llm,
    )


async def get_bundle_service(
    product_repo: CommerceProductRepository = Depends(get_product_repository),
    llm: BaseLLMProvider = Depends(get_recommendation_llm),
    capabilities_repo: StoreCapabilitiesRepository = Depends(get_capabilities_repository),
) -> BundleSuggestionService:
    return BundleSuggestionService(
        product_repo=product_repo,
        llm=llm,
        capabilities_repo=capabilities_repo,
    )
