import pytest
from app.infrastructure.providers.factory import LLMProviderFactory
from app.infrastructure.providers.openai_provider import OpenAIProvider
from app.infrastructure.providers.gemini_provider import GeminiProvider
from app.core.ai_exceptions import ProviderNotFoundException

def test_factory_singleton():
    factory1 = LLMProviderFactory()
    factory2 = LLMProviderFactory()
    assert factory1 is factory2


def test_factory_get_provider():
    factory = LLMProviderFactory()
    factory.clear_cache()
    
    openai_provider = factory.get_provider("openai")
    assert isinstance(openai_provider, OpenAIProvider)
    
    # Caching check
    openai_provider_cached = factory.get_provider("openai")
    assert openai_provider is openai_provider_cached
    
    gemini_provider = factory.get_provider("gemini")
    assert isinstance(gemini_provider, GeminiProvider)


def test_factory_invalid_provider():
    factory = LLMProviderFactory()
    with pytest.raises(ProviderNotFoundException):
        factory.get_provider("invalid-provider-name")
