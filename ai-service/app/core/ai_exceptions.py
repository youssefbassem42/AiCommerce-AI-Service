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
