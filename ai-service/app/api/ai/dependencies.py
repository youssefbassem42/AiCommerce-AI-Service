from fastapi import Depends, Request

from app.api.recommendation.dependencies import (
    get_bundle_service,
    get_recommendation_service,
)
from app.application.recommendation.services import BundleSuggestionService, RecommendationService
from app.application.services.chat_service import ChatService
from app.application.services.conversation_service import ConversationService
from app.application.services.orchestration_service import OrchestrationService
from app.domain.memory.repositories.memory_repository import MemoryRepository
from app.infrastructure.mongodb.collections import get_user_memories_collection
from app.infrastructure.mongodb.repositories.memory_repository import MongoMemoryRepository
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory
from app.infrastructure.repositories.conversation_repository import ConversationRepository


def get_provider_factory() -> LLMProviderFactory:
    return LLMProviderFactory()


def get_conversation_repository() -> ConversationRepository:
    return ConversationRepository()


def get_conversation_service(
    repo: ConversationRepository = Depends(get_conversation_repository),
) -> ConversationService:
    return ConversationService(repository=repo)


def get_memory_repository() -> MemoryRepository:
    return MongoMemoryRepository(get_user_memories_collection())


def get_orchestration_service(
    conversation_service: ConversationService = Depends(get_conversation_service),
    memory_repo: MemoryRepository = Depends(get_memory_repository),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
    bundle_service: BundleSuggestionService = Depends(get_bundle_service),
) -> OrchestrationService:
    return OrchestrationService(
        provider_factory=LLMProviderFactory(),
        conversation_service=conversation_service,
        memory_repo=memory_repo,
        recommendation_service=recommendation_service,
        bundle_service=bundle_service,
    )


def get_ai_service(
    factory: LLMProviderFactory = Depends(get_provider_factory),
    conv_service: ConversationService = Depends(get_conversation_service),
    orchestration_service: OrchestrationService = Depends(get_orchestration_service),
) -> ChatService:
    return ChatService(
        provider_factory=factory,
        conversation_service=conv_service,
        orchestration_service=orchestration_service,
    )


def get_store_context(request: Request) -> tuple[str | None, str | None]:
    """Extract store_id (tenant) and customer_id from the authenticated request state."""
    return getattr(request.state, "tenant_id", None), getattr(request.state, "user_id", None)


def get_provider(
    provider_name: str,
    factory: LLMProviderFactory = Depends(get_provider_factory),
) -> BaseLLMProvider:
    return factory.get_provider(provider_name)


def get_openai(
    factory: LLMProviderFactory = Depends(get_provider_factory),
) -> BaseLLMProvider:
    return factory.get_provider("openai")


def get_claude(
    factory: LLMProviderFactory = Depends(get_provider_factory),
) -> BaseLLMProvider:
    return factory.get_provider("claude")


def get_gemini(
    factory: LLMProviderFactory = Depends(get_provider_factory),
) -> BaseLLMProvider:
    return factory.get_provider("gemini")


def get_azure(
    factory: LLMProviderFactory = Depends(get_provider_factory),
) -> BaseLLMProvider:
    return factory.get_provider("azure")


def get_ollama(
    factory: LLMProviderFactory = Depends(get_provider_factory),
) -> BaseLLMProvider:
    return factory.get_provider("ollama")


def get_deepseek(
    factory: LLMProviderFactory = Depends(get_provider_factory),
) -> BaseLLMProvider:
    return factory.get_provider("deepseek")


def get_mistral(
    factory: LLMProviderFactory = Depends(get_provider_factory),
) -> BaseLLMProvider:
    return factory.get_provider("mistral")
