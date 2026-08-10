"""CORS handling for merchant-hosted widget origins.

The widget runs on arbitrary merchant domains that are not part of the static
`CORS_ORIGINS` allowlist. This middleware serves CORS for widget API paths only,
resolving allowed origins from ACTIVE widget installations (never a wildcard):

- OPTIONS preflight for an allowed dynamic origin → answered with CORS headers.
- Actual widget requests from an allowed dynamic origin → `Access-Control-Allow-Origin`
  echoed back with `Vary: Origin`.

Origins are cached with a short TTL; a failed lookup denies (no CORS headers),
matching the bootstrap origin policy.
"""

import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.infrastructure.mongodb.repositories.widget_installation_repository import (
    WidgetInstallationMongoRepository,
)

WIDGET_PATH_PREFIX = "/api/v1/widget"

CACHE_TTL_SECONDS = 60
PREFLIGHT_MAX_AGE = 3600

ALLOW_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
ALLOW_HEADERS = "Authorization, Content-Type, Accept, Origin, X-Widget-Key, X-Correlation-ID"
EXPOSE_HEADERS = "X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset, Retry-After, X-Correlation-ID"


class WidgetCorsMiddleware(BaseHTTPMiddleware):
    _allowed_origins: set[str] = set()
    _fetched_at: float = 0.0

    async def _get_allowed_origins(self) -> set[str]:
        now = time.monotonic()
        if now - self._fetched_at > CACHE_TTL_SECONDS:
            try:
                self._allowed_origins = await WidgetInstallationMongoRepository().find_allowed_origins()
            except Exception:
                self._allowed_origins = set()
            self._fetched_at = now
        return self._allowed_origins

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith(WIDGET_PATH_PREFIX):
            return await call_next(request)

        origin = request.headers.get("Origin")
        if not origin:
            return await call_next(request)

        allowed = await self._get_allowed_origins()
        if origin not in allowed:
            return await call_next(request)

        if request.method == "OPTIONS":
            return self._preflight_response(origin)

        response = await call_next(request)
        if "access-control-allow-origin" not in response.headers:
            response.headers["access-control-allow-origin"] = origin
            existing_vary = response.headers.get("vary")
            response.headers["vary"] = f"{existing_vary}, Origin" if existing_vary else "Origin"
        return response

    @staticmethod
    def _preflight_response(origin: str) -> Response:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Vary": "Origin",
            "Access-Control-Allow-Methods": ALLOW_METHODS,
            "Access-Control-Allow-Headers": ALLOW_HEADERS,
            "Access-Control-Expose-Headers": EXPOSE_HEADERS,
            "Access-Control-Max-Age": str(PREFLIGHT_MAX_AGE),
        }
        return Response(status_code=200, headers=headers)
