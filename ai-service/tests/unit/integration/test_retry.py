import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from app.infrastructure.http.retry import RetryHandler, RetryExhaustedError


@pytest.fixture
def retry_handler() -> RetryHandler:
    return RetryHandler(max_retries=2, base_delay=0.01, max_delay=0.05)


class TestRetryHandler:
    async def test_successful_request(self, retry_handler: RetryHandler) -> None:
        mock_response = httpx.Response(200, json={"data": "ok"})
        mock_request = AsyncMock(return_value=mock_response)
        response = await retry_handler.execute(mock_request)
        assert response.status_code == 200
        mock_request.assert_called_once()

    async def test_non_retryable_status_immediate(self, retry_handler: RetryHandler) -> None:
        mock_response = httpx.Response(400, json={"error": "bad request"})
        mock_request = AsyncMock(return_value=mock_response)
        response = await retry_handler.execute(mock_request)
        assert response.status_code == 400
        mock_request.assert_called_once()

    async def test_retryable_status_retries(self, retry_handler: RetryHandler) -> None:
        mock_error = httpx.Response(503)
        mock_success = httpx.Response(200, json={"data": "ok"})
        mock_request = AsyncMock(side_effect=[mock_error, mock_success])
        response = await retry_handler.execute(mock_request)
        assert response.status_code == 200
        assert mock_request.call_count == 2

    async def test_429_is_retryable(self, retry_handler: RetryHandler) -> None:
        mock_too_many = httpx.Response(429)
        mock_success = httpx.Response(200, json={"data": "ok"})
        mock_request = AsyncMock(side_effect=[mock_too_many, mock_success])
        response = await retry_handler.execute(mock_request)
        assert response.status_code == 200

    async def test_transport_error_retries(self, retry_handler: RetryHandler) -> None:
        mock_request = AsyncMock(side_effect=httpx.TransportError("connection failed"))
        with pytest.raises(RetryExhaustedError):
            await retry_handler.execute(mock_request)
        assert mock_request.call_count == 3  # initial + 2 retries

    async def test_max_retries_exhausted(self, retry_handler: RetryHandler) -> None:
        mock_error = httpx.Response(503)
        mock_request = AsyncMock(return_value=mock_error)
        with pytest.raises(RetryExhaustedError):
            await retry_handler.execute(mock_request)
        assert mock_request.call_count == 3  # initial + 2 retries

    async def test_401_immediate_no_retry(self, retry_handler: RetryHandler) -> None:
        mock_response = httpx.Response(401, json={"error": "unauthorized"})
        mock_request = AsyncMock(return_value=mock_response)
        response = await retry_handler.execute(mock_request)
        assert response.status_code == 401
        mock_request.assert_called_once()

    async def test_403_immediate_no_retry(self, retry_handler: RetryHandler) -> None:
        mock_response = httpx.Response(403)
        mock_request = AsyncMock(return_value=mock_response)
        response = await retry_handler.execute(mock_request)
        assert response.status_code == 403
        mock_request.assert_called_once()

    async def test_backoff_with_jitter(self, retry_handler: RetryHandler) -> None:
        delay = retry_handler._backoff(0)
        assert 0.01 <= delay < 0.02
        delay = retry_handler._backoff(1)
        assert 0.02 <= delay < 0.05