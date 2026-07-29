import pytest
from unittest.mock import MagicMock, patch
from app.api.ai.dependencies import (
    get_provider_factory,
    get_ai_service,
    get_provider,
    get_openai,
    get_claude,
    get_gemini,
    get_azure,
    get_ollama,
    get_deepseek,
    get_mistral,
)
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory


def test_get_provider_factory():
    factory = get_provider_factory()
    assert isinstance(factory, LLMProviderFactory)


def test_get_openai():
    factory = get_provider_factory()
    factory.clear_cache()

    openai_provider = get_openai(factory)
    assert isinstance(openai_provider, BaseLLMProvider)


def test_get_claude():
    factory = get_provider_factory()
    factory.clear_cache()

    claude_provider = get_claude(factory)
    assert isinstance(claude_provider, BaseLLMProvider)


def test_get_gemini():
    factory = get_provider_factory()
    factory.clear_cache()

    gemini_provider = get_gemini(factory)
    assert isinstance(gemini_provider, BaseLLMProvider)


def test_get_azure():
    factory = get_provider_factory()
    factory.clear_cache()

    azure_provider = get_azure(factory)
    assert isinstance(azure_provider, BaseLLMProvider)


def test_get_ollama():
    factory = get_provider_factory()
    factory.clear_cache()

    ollama_provider = get_ollama(factory)
    assert isinstance(ollama_provider, BaseLLMProvider)


def test_get_deepseek():
    factory = get_provider_factory()
    factory.clear_cache()

    deepseek_provider = get_deepseek(factory)
    assert isinstance(deepseek_provider, BaseLLMProvider)


def test_get_mistral():
    factory = get_provider_factory()
    factory.clear_cache()

    mistral_provider = get_mistral(factory)
    assert isinstance(mistral_provider, BaseLLMProvider)


def test_get_provider_by_name():
    factory = get_provider_factory()
    factory.clear_cache()

    provider = get_provider("openai", factory)
    assert isinstance(provider, BaseLLMProvider)


def test_get_ai_service():
    with patch("app.api.ai.dependencies.get_conversation_service") as mock_conv:
        mock_conv.return_value = MagicMock()
        service = get_ai_service()
        assert service is not None
        assert hasattr(service, "chat")
        assert hasattr(service, "stream")
