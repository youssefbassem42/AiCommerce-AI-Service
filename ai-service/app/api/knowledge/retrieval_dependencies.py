from fastapi import Depends

from app.application.knowledge.retrieval.config import RetrievalConfig
from app.application.knowledge.retrieval.reranker import LLMCrossEncoderReRanker, ReRanker
from app.application.knowledge.retrieval.service import RetrieverService
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory
from app.infrastructure.qdrant.provider import QdrantProvider


def get_vector_store() -> QdrantProvider:
    return QdrantProvider()


async def get_chat_provider() -> BaseLLMProvider:
    factory = LLMProviderFactory()
    from app.core.ai_settings import ai_settings

    provider_name = ai_settings.DEFAULT_PROVIDER
    return factory.get_provider(provider_name)


def get_reranker(
    provider: BaseLLMProvider = Depends(get_chat_provider),
) -> ReRanker:
    return LLMCrossEncoderReRanker(provider=provider)


def get_retrieval_config() -> RetrievalConfig:
    return RetrievalConfig()


async def get_embedding_provider() -> BaseLLMProvider:
    factory = LLMProviderFactory()
    try:
        return factory.get_provider("gemini")
    except Exception:
        pass
    try:
        return factory.get_provider("openai")
    except Exception:
        pass
    return factory.get_provider("mock")


async def get_retriever_service(
    vector_store: QdrantProvider = Depends(get_vector_store),
    chat_provider: BaseLLMProvider = Depends(get_chat_provider),
    embed_provider: BaseLLMProvider = Depends(get_embedding_provider),
    reranker: ReRanker = Depends(get_reranker),
    config: RetrievalConfig = Depends(get_retrieval_config),
) -> RetrieverService:
    await vector_store.connect()
    return RetrieverService(
        vector_store=vector_store,
        llm_provider=embed_provider,
        reranker=reranker,
        default_config=config,
    )
