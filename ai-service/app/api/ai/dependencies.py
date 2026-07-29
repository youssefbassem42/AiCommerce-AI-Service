from fastapi import Depends

from app.application.services.chat_service import ChatService
from app.application.services.conversation_service import ConversationService
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


def get_ai_service(
    factory: LLMProviderFactory = Depends(get_provider_factory),
    conv_service: ConversationService = Depends(get_conversation_service),
) -> ChatService:
    return ChatService(provider_factory=factory, conversation_service=conv_service)


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
