import asyncio
import logging
import random
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 405, 422}


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted."""


class RetryHandler:
    """Exponential backoff with jitter for async HTTP requests.

    - Retryable statuses: 429, 502, 503, 504 + httpx.TransportError
    - Non-retryable statuses: 400, 401, 403, 404, 405, 422 (raised immediately)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def execute(
        self,
        request_func,
        *args,
        **kwargs,
    ) -> "httpx.Response":
        last_exception: Optional[Exception] = None
        last_response: Optional[httpx.Response] = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await request_func(*args, **kwargs)
                last_response = response
                if response.status_code in NON_RETRYABLE_STATUS_CODES:
                    return response
                if response.status_code in RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    delay = self._backoff(attempt)
                    logger.warning(
                        "Retryable status %d on attempt %d/%d. "
                        "Retrying in %.2fs...",
                        response.status_code,
                        attempt + 1,
                        self.max_retries,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                if response.status_code in RETRYABLE_STATUS_CODES:
                    raise RetryExhaustedError(
                        f"Request failed with retryable status {response.status_code} "
                        f"after {self.max_retries} retries."
                    )
                return response
            except httpx.TransportError as e:
                last_exception = e
                if attempt >= self.max_retries:
                    logger.error(
                        "Transport error after %d retries: %s",
                        self.max_retries,
                        str(e),
                    )
                    raise RetryExhaustedError(
                        f"Request failed after {self.max_retries} retries: {e}"
                    ) from e
                delay = self._backoff(attempt)
                logger.warning(
                    "Transport error on attempt %d/%d: %s. Retrying in %.2fs...",
                    attempt + 1,
                    self.max_retries,
                    str(e),
                    delay,
                )
                await asyncio.sleep(delay)

        if last_exception:
            raise RetryExhaustedError(
                f"Request failed after {self.max_retries} retries."
            ) from last_exception

        if last_response and last_response.status_code in RETRYABLE_STATUS_CODES:
            raise RetryExhaustedError(
                f"Request failed with retryable status {last_response.status_code} "
                f"after {self.max_retries} retries."
            )

        raise RetryExhaustedError(
            f"Request failed after {self.max_retries} retries (exhausted)."
        )

    def _backoff(self, attempt: int) -> float:
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter