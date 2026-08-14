"""Phase 9: provider credentials must fail loudly — no "mock-key" fallbacks.

Regression guard for the P1 finding: constructing a provider without a real
API key must raise ProviderCredentialsError instead of silently using a
placeholder key that would mask misconfiguration.
"""

import pytest

from app.core.ai_exceptions import ProviderCredentialsError
from app.infrastructure.security.key_manager import KeyManager


class TestKeyManagerRequireApiKey:
    def test_returns_key_when_set(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-real-key")
        assert KeyManager().require_provider_api_key("openai") == "sk-real-key"

    def test_returns_custom_env_var_when_set(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_KEY", "az-real-key")
        assert KeyManager().require_provider_api_key("azure", env_var="AZURE_OPENAI_KEY") == "az-real-key"

    def test_missing_key_raises_loudly(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ProviderCredentialsError) as exc:
            KeyManager().require_provider_api_key("openai")
        assert "OPENAI_API_KEY" in str(exc.value)
        assert "mock-key" not in str(exc.value)

    def test_mock_key_placeholder_raises(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "mock-key")
        with pytest.raises(ProviderCredentialsError):
            KeyManager().require_provider_api_key("openai")

    def test_empty_string_raises(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        with pytest.raises(ProviderCredentialsError):
            KeyManager().require_provider_api_key("openai")


class TestProviderConstructionFailsLoudly:
    """Providers themselves must not fall back to placeholder keys."""

    def test_openai_provider_without_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from app.infrastructure.providers.openai_provider import OpenAIProvider

        with pytest.raises(ProviderCredentialsError):
            OpenAIProvider()

    def test_openai_provider_with_explicit_key_constructs(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from app.infrastructure.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key="sk-explicit")
        assert provider.api_key == "sk-explicit"

    def test_gemini_provider_without_key_raises(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        from app.infrastructure.providers.gemini_provider import GeminiProvider

        with pytest.raises(ProviderCredentialsError):
            GeminiProvider()

    def test_openrouter_provider_without_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        from app.infrastructure.providers.openrouter_provider import OpenRouterProvider

        with pytest.raises(ProviderCredentialsError):
            OpenRouterProvider()

    def test_azure_provider_without_key_raises(self, monkeypatch):
        monkeypatch.delenv("AZURE_OPENAI_KEY", raising=False)
        monkeypatch.delenv("AZURE_ENDPOINT", raising=False)
        from app.infrastructure.providers.azure_provider import AzureOpenAIProvider

        with pytest.raises(ProviderCredentialsError):
            AzureOpenAIProvider()

    def test_azure_provider_mock_endpoint_raises(self, monkeypatch):
        from app.core import ai_settings as ai_settings_module
        from app.infrastructure.providers.azure_provider import AzureOpenAIProvider

        monkeypatch.setenv("AZURE_OPENAI_KEY", "az-real-key")
        monkeypatch.setenv("AZURE_DEPLOYMENT", "gpt-4o")
        monkeypatch.setattr(ai_settings_module.ai_settings, "AZURE_ENDPOINT", "https://mock-endpoint.openai.azure.com/")

        with pytest.raises(ProviderCredentialsError):
            AzureOpenAIProvider()

    def test_claude_provider_without_key_raises(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
        from app.infrastructure.providers.claude_provider import ClaudeProvider

        with pytest.raises(ProviderCredentialsError):
            ClaudeProvider()

    def test_deepseek_provider_without_key_raises(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        from app.infrastructure.providers.deepseek_provider import DeepSeekProvider

        with pytest.raises(ProviderCredentialsError):
            DeepSeekProvider()

    def test_mistral_provider_without_key_raises(self, monkeypatch):
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        from app.infrastructure.providers.mistral_provider import MistralProvider

        with pytest.raises(ProviderCredentialsError):
            MistralProvider()