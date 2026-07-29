import asyncio
import logging
import time
from typing import Any, Callable, Coroutine, TypeVar, Union
from app.core.ai_exceptions import (
    AuthenticationException,
    RateLimitException,
    ProviderUnavailableException,
    StreamingException,
    ToolCallingException,
    StructuredOutputException,
    AIException,
)

logger = logging.getLogger("ai_service")

T = TypeVar("T")

def map_provider_exception(provider: str, e: Exception) -> Exception:
    """
    Maps third-party provider exceptions to unified AI module exceptions.
    """
    err_msg = str(e)
    err_class = e.__class__.__name__

    # Log error context
    logger.error(f"Error from provider '{provider}': {err_class} - {err_msg}", exc_info=True)

    # 1. OpenAI / Azure OpenAI / DeepSeek (which uses OpenAI client)
    if provider in ["openai", "azure", "deepseek"]:
        if "AuthenticationError" in err_class or "401" in err_msg or "403" in err_msg:
            return AuthenticationException(provider, err_msg)
        if "RateLimitError" in err_class or "429" in err_msg:
            return RateLimitException(provider, err_msg)
        if "APITimeoutError" in err_class or "timeout" in err_msg.lower():
            return ProviderUnavailableException(provider, f"Timeout: {err_msg}")
        if "APIStatusError" in err_class or "APIConnectionError" in err_msg or "50" in err_msg:
            return ProviderUnavailableException(provider, f"API Connection/Status Error: {err_msg}")

    # 2. Anthropic Claude
    if provider == "claude":
        if "AuthenticationError" in err_class or "401" in err_msg or "403" in err_msg:
            return AuthenticationException(provider, err_msg)
        if "RateLimitError" in err_class or "429" in err_msg:
            return RateLimitException(provider, err_msg)
        if "APITimeoutError" in err_class or "timeout" in err_msg.lower():
            return ProviderUnavailableException(provider, f"Timeout: {err_msg}")
        if "APIStatusError" in err_class or "APIConnectionError" in err_class:
            return ProviderUnavailableException(provider, f"API Connection/Status Error: {err_msg}")

    # 3. Google Gemini
    if provider == "gemini":
        if "InvalidArgument" in err_class or "400" in err_msg:
            return AIException(f"Invalid argument sent to Gemini: {err_msg}", 400)
        if "ResourceExhausted" in err_class or "429" in err_msg:
            return RateLimitException(provider, err_msg)
        if "PermissionDenied" in err_class or "Unauthenticated" in err_class or "401" in err_msg or "403" in err_msg:
            return AuthenticationException(provider, err_msg)
        if "GoogleAPICallError" in err_class or "InternalServerError" in err_class or "50" in err_msg:
            return ProviderUnavailableException(provider, f"Gemini API Error: {err_msg}")

    # 4. Mistral
    if provider == "mistral":
        if "401" in err_msg or "403" in err_msg:
            return AuthenticationException(provider, err_msg)
        if "429" in err_msg:
            return RateLimitException(provider, err_msg)
        if "timeout" in err_msg.lower():
            return ProviderUnavailableException(provider, f"Timeout: {err_msg}")
        if "50" in err_msg or "MistralAPIException" in err_class:
            return ProviderUnavailableException(provider, f"Mistral API Error: {err_msg}")

    # 5. Ollama
    if provider == "ollama":
        if "timeout" in err_msg.lower():
            return ProviderUnavailableException(provider, f"Timeout: {err_msg}")
        if "ConnectionRefused" in err_class or "404" in err_msg or "50" in err_msg:
            return ProviderUnavailableException(provider, f"Ollama is unreachable: {err_msg}")

    # Generic HTTP Exceptions from httpx
    if "Timeout" in err_class or "ConnectTimeout" in err_class or "ReadTimeout" in err_class:
        return ProviderUnavailableException(provider, f"HTTP Timeout: {err_msg}")
    if "ConnectError" in err_class or "NetworkError" in err_class:
        return ProviderUnavailableException(provider, f"Network connection error: {err_msg}")

    return AIException(f"AI operation failed on provider '{provider}': {err_msg}", 500)


async def execute_with_retry(
    provider: str,
    operation: Callable[[], Coroutine[Any, Any, T]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
) -> T:
    """
    Executes an async operation with exponential backoff retry.
    Only retries on transient exceptions (RateLimit, ProviderUnavailable).
    """
    last_exception = None
    delay = base_delay

    for attempt in range(1, max_retries + 1):
        try:
            return await operation()
        except Exception as e:
            mapped_exc = map_provider_exception(provider, e)
            
            # Do not retry on authentication or schema validation issues
            if isinstance(mapped_exc, (AuthenticationException, StructuredOutputException, ToolCallingException)):
                raise mapped_exc
            
            # Save the mapped exception
            last_exception = mapped_exc
            
            if attempt == max_retries:
                logger.error(f"Failed after {max_retries} attempts on provider '{provider}'.")
                raise last_exception

            logger.warning(
                f"Attempt {attempt}/{max_retries} failed for provider '{provider}'. "
                f"Retrying in {delay:.2f}s... Error: {str(e)}"
            )
            await asyncio.sleep(delay)
            delay *= backoff_factor

    raise last_exception or AIException(f"Retry execution failed on provider '{provider}'")
