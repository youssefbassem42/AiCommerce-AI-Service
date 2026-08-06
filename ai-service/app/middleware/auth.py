import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.application.auth.jwt_service import jwt_validation_service
from app.core.auth_settings import auth_settings
from app.core.security import ERR_INVALID_FORMAT, ERR_MISSING_HEADER, JWTAuthenticationError

logger = logging.getLogger(__name__)

WHITELIST_PATHS = {"/health/", "/health", "/docs", "/redoc", "/openapi.json"}

BEARER_PREFIX = "Bearer "


class AuthMiddleware(BaseHTTPMiddleware):
    """Extracts and validates a Bearer access token, then populates request.state.

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

        try:
            user = jwt_validation_service.validate(token)
        except JWTAuthenticationError as exc:
            logger.warning("JWT validation failed: %s", exc.detail)
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        except Exception as exc:
            logger.warning("Unexpected JWT validation error: %s", exc, exc_info=True)
            return JSONResponse({"detail": ERR_INVALID_FORMAT}, status_code=401)

        request.state.user_id = str(user.user_id)
        request.state.email = user.email
        request.state.store_id = str(user.store_id) if user.store_id else None
        request.state.organization_id = str(user.organization_id) if user.organization_id else None
        request.state.roles = user.roles or ([user.role] if user.role else [])
        request.state.permissions = user.permissions
        request.state.security_stamp = user.security_stamp
        request.state.jti = user.jti
        request.state.user = user

        return await call_next(request)
