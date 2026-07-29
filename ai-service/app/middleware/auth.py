import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.auth_settings import auth_settings
from app.core.security import decode_jwt, get_tenant_id_from_token, get_user_id_from_token, get_roles_from_token, get_scopes_from_token

logger = logging.getLogger(__name__)

WHITELIST_PATHS = {"/health/", "/health", "/docs", "/redoc", "/openapi.json", "/api/v1/auth/api-keys"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in WHITELIST_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            if auth_settings.JWT_REQUIRED:
                return Response("Missing or invalid Authorization header", status_code=401)
            return await call_next(request)

        token = auth_header.removeprefix("Bearer ")

        try:
            payload = decode_jwt(token)
            request.state.user_id = get_user_id_from_token(payload)
            request.state.tenant_id = get_tenant_id_from_token(payload)
            request.state.roles = get_roles_from_token(payload)
            request.state.scopes = get_scopes_from_token(payload)
        except Exception as exc:
            logger.warning("JWT validation failed: %s", exc)
            return Response("Invalid or expired token", status_code=401)

        return await call_next(request)
