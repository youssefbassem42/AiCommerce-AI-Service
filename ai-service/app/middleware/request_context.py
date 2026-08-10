"""Request correlation middleware.

Establishes a single correlation identifier per HTTP request:

- Incoming `X-Request-ID` is honored; `X-Correlation-ID` is accepted as a legacy
  alias (identical concept, canonical name `request_id`).
- When neither header is present, a UUID is generated.
- The identifier is exposed as `request.state.request_id` (and legacy
  `request.state.correlation_id`), as a contextvar for the whole stack, and echoed
  back on the response as `X-Request-ID` and `X-Correlation-ID` (legacy header
  behavior preserved).

No secrets are ever put in the header.
"""

import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.request_context import new_request_id, set_request_id

logger = logging.getLogger(__name__)

HEADER_PRIMARY = "X-Request-ID"
HEADER_LEGACY = "X-Correlation-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(HEADER_PRIMARY) or request.headers.get(HEADER_LEGACY) or new_request_id()
        request_id = request_id.strip()
        if not request_id:
            request_id = new_request_id()

        request.state.request_id = request_id
        request.state.correlation_id = request_id
        set_request_id(request_id)

        try:
            response = await call_next(request)
        except Exception:
            logger.error("Request %s failed", request_id, exc_info=True)
            raise
        finally:
            set_request_id("")

        response.headers[HEADER_PRIMARY] = request_id
        response.headers[HEADER_LEGACY] = request_id
        return response
