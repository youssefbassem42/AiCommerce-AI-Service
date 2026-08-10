import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("ai_service")


class AITracingMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware to trace every request.
    Uses the correlation ID established by RequestContextMiddleware (outermost),
    tracks execution time, and logs every request.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # RequestContextMiddleware always runs before this middleware; fall back to a
        # fresh ID defensively (e.g. if middleware order changes).
        correlation_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            process_time_ms = (time.perf_counter() - start_time) * 1000

            # Add processing time to response headers
            response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"

            # Log successful request
            logger.info(
                f"[Request Success] Path: {request.url.path} | Method: {request.method} | "
                f"Status: {response.status_code} | Latency: {process_time_ms:.2f}ms | Request ID: {correlation_id}"
            )

            return response

        except Exception as e:
            process_time_ms = (time.perf_counter() - start_time) * 1000
            # Log failed request
            logger.error(
                f"[Request Failed] Path: {request.url.path} | Method: {request.method} | "
                f"Error: {str(e)} | Latency: {process_time_ms:.2f}ms | Request ID: {correlation_id}",
                exc_info=True,
            )
            raise e
