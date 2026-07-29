import time
import uuid
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("ai_service")

class AITracingMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware to trace every request.
    Generates or extracts a correlation ID, tracks execution time, and logs details.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        
        # Attach to request state for reuse in handlers
        request.state.correlation_id = correlation_id
        
        start_time = time.perf_counter()
        
        try:
            response = await call_next(request)
            process_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
            
            # Log successful request
            logger.info(
                f"[Request Success] Path: {request.url.path} | Method: {request.method} | "
                f"Status: {response.status_code} | Latency: {process_time_ms:.2f}ms | Correlation ID: {correlation_id}"
            )
            
            return response
            
        except Exception as e:
            process_time_ms = (time.perf_counter() - start_time) * 1000
            # Log failed request
            logger.error(
                f"[Request Failed] Path: {request.url.path} | Method: {request.method} | "
                f"Error: {str(e)} | Latency: {process_time_ms:.2f}ms | Correlation ID: {correlation_id}",
                exc_info=True
            )
            raise e
