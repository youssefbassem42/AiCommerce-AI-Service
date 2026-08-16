import asyncio
import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.application.auth.jwt_service import jwt_validation_service
from app.application.widget.token_service import peek_issuer, widget_token_service
from app.core.auth_settings import auth_settings
from app.core.security import ERR_INVALID_FORMAT, ERR_MISSING_HEADER, JWTAuthenticationError

logger = logging.getLogger(__name__)

WHITELIST_PATHS = {
    "/health/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/widget.js",
    "/demo",
    "/demo/",
    # Widget bootstrap exchanges the public widget key for a scoped session
    # token, so it must be reachable without a Bearer token even when
    # JWT_REQUIRED is enabled (its own key + origin checks still apply).
    "/api/v1/widget/bootstrap",
    "/api/v1/widget/bootstrap/",
}

BEARER_PREFIX = "Bearer "


def _sync_plan_policy(claims: dict, store_id, organization_id) -> None:
    """Fire-and-forget ingestion of the trusted plan claims into the policy store.

    Runs on the event loop without blocking the authenticated request; failures
    are logged and never break authentication (the store falls back to its
    persisted/default entitlement).
    """
    from app.api.quota.dependencies import get_plan_policy_service

    store_key = str(store_id) if store_id else ""

    async def _sync():
        try:
            await get_plan_policy_service().sync_from_claims(claims, store_key, str(organization_id or ""))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Plan policy sync failed for store %s: %s", store_key, exc)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_sync())
    except RuntimeError:
        logger.warning("Plan policy sync skipped: no running event loop")


class AuthMiddleware(BaseHTTPMiddleware):
    """Extracts and validates a Bearer access token, then populates request.state.

    Dispatches on the token issuer:
    - `AI-Commerce-Widget`         → widget token path: scoped tenant context
      (`widget_id`, `store_id`, `organization_id`, `scopes`, `session_id`)
      with NO SaaS user identity, so widget tokens cannot be used on SaaS endpoints.
    - anything else                → SaaS access token path (existing contract);
      trusted plan claims are ingested into the plan policy store.

    - No `Authorization` header: pass through when `JWT_REQUIRED` is off (public rag/agent
      mode), otherwise 401 per the contract.
    - A present token is ALWAYS validated; failures return the contract status/message.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path in WHITELIST_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")

        if not auth_header:
            if auth_settings.JWT_REQUIRED:
                return JSONResponse({"detail": ERR_MISSING_HEADER}, status_code=401)
            return await call_next(request)

        if not auth_header.startswith(BEARER_PREFIX):
            return JSONResponse({"detail": ERR_INVALID_FORMAT}, status_code=401)

        token = auth_header[len(BEARER_PREFIX) :].strip()
        if not token:
            return JSONResponse({"detail": ERR_INVALID_FORMAT}, status_code=401)

        if peek_issuer(token) == widget_token_service.ISSUER:
            return await self._dispatch_widget(request, call_next, token)

        try:
            user = jwt_validation_service.validate(token)
        except JWTAuthenticationError as exc:
            logger.warning("JWT validation failed: %s", exc.detail)
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        except Exception as exc:
            logger.warning("Unexpected JWT validation error: %s", exc, exc_info=True)
            return JSONResponse({"detail": ERR_INVALID_FORMAT}, status_code=401)

        request.state.actor_type = "user"
        request.state.user_id = str(user.user_id)
        request.state.email = user.email
        request.state.store_id = str(user.store_id) if user.store_id else None
        request.state.organization_id = str(user.organization_id) if user.organization_id else None
        request.state.roles = user.roles or ([user.role] if user.role else [])
        request.state.permissions = user.permissions
        request.state.security_stamp = user.security_stamp
        request.state.jti = user.jti
        request.state.user = user

        if user.store_id is not None:
            try:
                from app.core.security import decode_jwt

                _sync_plan_policy(decode_jwt(token), user.store_id, user.organization_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Plan claim extraction failed: %s", exc)

        return await call_next(request)

    async def _dispatch_widget(self, request: Request, call_next, token: str):
        try:
            claims = widget_token_service.validate(token)
        except JWTAuthenticationError as exc:
            logger.warning("Widget token validation failed: %s", exc.detail)
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        except Exception as exc:
            logger.warning("Unexpected widget token validation error: %s", exc, exc_info=True)
            return JSONResponse({"detail": ERR_INVALID_FORMAT}, status_code=401)

        request.state.actor_type = "widget"
        request.state.widget_id = claims.widget_id
        request.state.store_id = claims.store_id
        request.state.organization_id = claims.organization_id
        request.state.scopes = claims.scopes
        request.state.widget_session_id = claims.session_id
        request.state.user = None
        request.state.user_id = None
        request.state.email = None
        request.state.roles = []
        request.state.permissions = []
        request.state.security_stamp = None
        request.state.jti = None

        return await call_next(request)
