import logging
from typing import Optional

from app.core.ai_exceptions import ProviderNotFoundException
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger("ai_service")


class LLMProviderFactory:
    """Singleton provider factory with lazy provider loading and instance caching."""

    _instance: Optional["LLMProviderFactory"] = None
    _cache: dict[str, BaseLLMProvider] = {}

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._cache = {}
        return cls._instance

    def get_provider(self, provider_name: str) -> BaseLLMProvider:
        provider_key = provider_name.strip().lower()
        if provider_key in self._cache:
            return self._cache[provider_key]

        logger.info("Instantiating provider: %s", provider_key)

        if provider_key == "openai":
            from app.infrastructure.providers.openai_provider import OpenAIProvider

            provider_instance: BaseLLMProvider = OpenAIProvider()
        elif provider_key == "gemini":
            from app.infrastructure.providers.gemini_provider import GeminiProvider

            provider_instance = GeminiProvider()
        elif provider_key == "claude":
            from app.infrastructure.providers.claude_provider import ClaudeProvider

            provider_instance = ClaudeProvider()
        elif provider_key == "azure":
            from app.infrastructure.providers.azure_provider import AzureOpenAIProvider

            provider_instance = AzureOpenAIProvider()
        elif provider_key == "ollama":
            from app.infrastructure.providers.ollama_provider import OllamaProvider

            provider_instance = OllamaProvider()
        elif provider_key == "openrouter":
            from app.infrastructure.providers.openrouter_provider import OpenRouterProvider

            provider_instance = OpenRouterProvider()
        elif provider_key == "deepseek":
            from app.infrastructure.providers.deepseek_provider import DeepSeekProvider

            provider_instance = DeepSeekProvider()
        elif provider_key == "mistral":
            from app.infrastructure.providers.mistral_provider import MistralProvider

            provider_instance = MistralProvider()
        elif provider_key == "mock":
            from app.infrastructure.providers.mock_provider import MockProvider

            provider_instance = MockProvider()
        else:
            raise ProviderNotFoundException(provider_name)

        self._cache[provider_key] = provider_instance
        return provider_instance

    @classmethod
    def clear_cache(cls) -> None:
        if cls._instance:
            cls._instance._cache.clear()
