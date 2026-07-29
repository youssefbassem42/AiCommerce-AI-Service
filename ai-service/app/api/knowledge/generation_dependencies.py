from fastapi import Depends

from app.application.knowledge.commands.generate_business_summary_handler import (
    GenerateBusinessSummaryHandler,
    RegenerateBusinessSummaryHandler,
)
from app.application.knowledge.generation.config import GenerationConfig
from app.application.knowledge.generation.service import BusinessSummaryGenerationService
from app.application.knowledge.queries.list_business_summary_history_handler import (
    ListBusinessSummaryHistoryHandler,
)
from app.infrastructure.mongodb.repositories.business_summary_repository import (
    BusinessSummaryRepository,
)
from app.infrastructure.mongodb.repositories.knowledge_repository import KnowledgeRepository
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory


def get_knowledge_repository() -> KnowledgeRepository:
    return KnowledgeRepository()


def get_business_summary_repository() -> BusinessSummaryRepository:
    return BusinessSummaryRepository()


def get_provider() -> BaseLLMProvider:
    factory = LLMProviderFactory()
    return factory.get_provider("openai")


def get_generation_service(
    knowledge_repository: KnowledgeRepository = Depends(get_knowledge_repository),
    summary_repository: BusinessSummaryRepository = Depends(get_business_summary_repository),
    provider: BaseLLMProvider = Depends(get_provider),
) -> BusinessSummaryGenerationService:
    return BusinessSummaryGenerationService(
        knowledge_repository=knowledge_repository,
        summary_repository=summary_repository,
        provider=provider,
    )


def get_generate_handler(
    service: BusinessSummaryGenerationService = Depends(get_generation_service),
) -> GenerateBusinessSummaryHandler:
    return GenerateBusinessSummaryHandler(service=service)


def get_regenerate_handler(
    service: BusinessSummaryGenerationService = Depends(get_generation_service),
) -> RegenerateBusinessSummaryHandler:
    return RegenerateBusinessSummaryHandler(service=service)


def get_list_history_handler(
    repository: BusinessSummaryRepository = Depends(get_business_summary_repository),
) -> ListBusinessSummaryHistoryHandler:
    return ListBusinessSummaryHistoryHandler(repository=repository)
