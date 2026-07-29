import pytest
from app.utils.ai_error_handler import map_provider_exception, execute_with_retry
from app.core.ai_exceptions import (
    AuthenticationException,
    RateLimitException,
    ProviderUnavailableException,
    AIException,
)


class GeminiResourceExhausted(Exception):
    pass


class GeminiUnauthenticated(Exception):
    pass


class ClaudeRateLimitError(Exception):
    pass


class OllamaConnectionRefused(Exception):
    pass


class TimeoutError(Exception):
    pass


class TestMapProviderException:
    def test_openai_authentication_error(self):
        exc = Exception("401 Unauthorized")
        mapped = map_provider_exception("openai", exc)
        assert isinstance(mapped, AuthenticationException)

    def test_openai_rate_limit_error(self):
        exc = Exception("429 Too Many Requests")
        mapped = map_provider_exception("openai", exc)
        assert isinstance(mapped, RateLimitException)

    def test_openai_timeout_error(self):
        exc = Exception("timeout error")
        mapped = map_provider_exception("openai", exc)
        assert isinstance(mapped, ProviderUnavailableException)
        assert "Timeout" in mapped.message

    def test_gemini_rate_limit(self):
        exc = GeminiResourceExhausted("Quota exceeded")
        mapped = map_provider_exception("gemini", exc)
        assert isinstance(mapped, RateLimitException)

    def test_gemini_auth_error(self):
        exc = GeminiUnauthenticated("Invalid credentials")
        mapped = map_provider_exception("gemini", exc)
        assert isinstance(mapped, AuthenticationException)

    def test_claude_rate_limit(self):
        exc = ClaudeRateLimitError("too many requests")
        mapped = map_provider_exception("claude", exc)
        assert isinstance(mapped, RateLimitException)

    def test_mistral_auth_error(self):
        exc = Exception("HTTP 401: Invalid API key")
        mapped = map_provider_exception("mistral", exc)
        assert isinstance(mapped, AuthenticationException)

    def test_ollama_connection_refused(self):
        exc = OllamaConnectionRefused("No connection could be made")
        mapped = map_provider_exception("ollama", exc)
        assert isinstance(mapped, ProviderUnavailableException)

    def test_generic_http_timeout(self):
        exc = TimeoutError("The read operation timed out")
        mapped = map_provider_exception("any_provider", exc)
        assert isinstance(mapped, ProviderUnavailableException)

    def test_fallback_to_ai_exception(self):
        exc = Exception("Some unknown error occurred")
        mapped = map_provider_exception("unknown_provider", exc)
        assert isinstance(mapped, AIException)


class TestExecuteWithRetry:
    @pytest.mark.asyncio
    async def test_retry_success_on_second_attempt(self):
        call_count = 0

        async def failing_then_succeeding():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("429 Rate limit")
            return "success"

        result = await execute_with_retry("openai", failing_then_succeeding, max_retries=2, base_delay=0.01)
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        async def always_fails():
            raise Exception("429 Rate limit")

        with pytest.raises(RateLimitException):
            await execute_with_retry("openai", always_fails, max_retries=2, base_delay=0.01)

    @pytest.mark.asyncio
    async def test_no_retry_on_authentication_error(self):
        async def auth_fails():
            raise Exception("401 Unauthorized")

        with pytest.raises(AuthenticationException):
            await execute_with_retry("openai", auth_fails, max_retries=3, base_delay=0.01)
