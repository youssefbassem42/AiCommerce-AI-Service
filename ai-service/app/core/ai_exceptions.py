from typing import Any


class AIException(Exception):
    """Base exception for all AI-related errors."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ProviderNotFoundException(AIException):
    """Raised when the requested provider is not supported or found."""

    def __init__(self, provider: str):
        super().__init__(f"Provider '{provider}' was not found or is not supported.", 404)


class ProviderCredentialsError(AIException):
    """Raised when a provider is constructed without production credentials.

    Missing credentials must fail loudly at construction time — never silently
    fall back to a placeholder key, which would send unauthenticated requests
    and mask misconfiguration.
    """

    def __init__(self, provider: str, env_var: str, extra_hint: str | None = None):
        hint = f" Set {env_var} to a valid key before starting the service."
        if extra_hint:
            hint += f" {extra_hint}"
        super().__init__(f"Provider '{provider}' requires credential env var {env_var}.{hint}", 500)


class ModelNotFoundException(AIException):
    """Raised when the requested model is not supported or found for a provider."""

    def __init__(self, model: str, provider: str):
        super().__init__(f"Model '{model}' is not supported by provider '{provider}'.", 404)


class ProviderUnavailableException(AIException):
    """Raised when the provider is down, timed out, or returning 5xx errors."""

    def __init__(self, provider: str, details: str):
        super().__init__(f"Provider '{provider}' is currently unavailable: {details}", 503)


class RateLimitException(AIException):
    """Raised when the provider rate limit is exceeded (HTTP 429)."""

    def __init__(self, provider: str, details: str):
        super().__init__(f"Rate limit exceeded for provider '{provider}': {details}", 429)


class AuthenticationException(AIException):
    """Raised when API key or credentials for a provider are invalid (HTTP 401/403)."""

    def __init__(self, provider: str, details: str):
        super().__init__(f"Authentication failed for provider '{provider}': {details}", 401)


class StreamingException(AIException):
    """Raised when an error occurs during streaming response generation."""

    def __init__(self, provider: str, details: str):
        super().__init__(f"Streaming error occurred with provider '{provider}': {details}", 500)


class ToolCallingException(AIException):
    """Raised when tool calling fails or configuration is incorrect."""

    def __init__(self, provider: str, details: str):
        super().__init__(f"Tool calling failed with provider '{provider}': {details}", 400)


class StructuredOutputException(AIException):
    """Raised when structured output schema validation or parsing fails."""

    def __init__(self, provider: str, details: str):
        super().__init__(f"Structured output generation failed with provider '{provider}': {details}", 422)


class AllProvidersFailedException(AIException):
    """Every plan-allowed provider failed; no fallback remains."""

    code = "AI_PROVIDER_UNAVAILABLE"

    def __init__(self, details: str = ""):
        super().__init__("No plan-allowed provider could complete the request", 503)
        self.details = details or "all plan-allowed providers failed"


class StoreTokenQuotaExceededException(AIException):
    """Store token quota exhausted for the current billing period."""

    code = "STORE_TOKEN_QUOTA_EXCEEDED"

    def __init__(self, limit: int, used: int, details: Any = None):
        super().__init__("This store has reached its AI usage limit for the current billing period", 429)
        self.limit = limit
        self.used = used
        self.details = details


class ConsumerDailyLimitExceededException(AIException):
    """Consumer daily message limit reached."""

    code = "CONSUMER_DAILY_LIMIT_EXCEEDED"

    def __init__(self, limit: int, used: int, reset_at: str, details: Any = None):
        super().__init__("You have reached today's AI message limit", 429)
        self.limit = limit
        self.used = used
        self.reset_at = reset_at
        self.details = details


class QuotaUnavailableException(AIException):
    """Quota enforcement degraded (Redis unavailable) — failed closed."""

    code = "QUOTA_UNAVAILABLE"

    def __init__(self, details: str = "quota engine unavailable"):
        super().__init__("AI quota enforcement is temporarily unavailable", 503)
        self.details = details


class PlanNotAvailableException(AIException):
    """The store has no usable plan entitlement (fail closed)."""

    code = "PLAN_NOT_AVAILABLE"

    def __init__(self, reason: str = "plan_not_available"):
        super().__init__("Plan not available for AI execution", 403)
        self.reason = reason
