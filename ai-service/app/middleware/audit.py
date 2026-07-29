import json
import logging
from datetime import datetime, UTC
from bson import ObjectId

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.domain.auth.entities.audit_log import AuditLog
from app.infrastructure.mongodb.repositories.audit_log_repository import AuditLogRepository
from app.infrastructure.mongodb.uow import get_unit_of_work

logger = logging.getLogger(__name__)

WHITELIST_PATHS = {"/health/", "/health", "/docs", "/redoc", "/openapi.json"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in WHITELIST_PATHS:
            return await call_next(request)

        if request.method == "GET":
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None)
        user_id = getattr(request.state, "user_id", None)

        start_time = datetime.now(UTC)

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            status_code = 500
            raise
        finally:
            try:
                await self._log_audit_entry(
                    tenant_id=tenant_id,
                    actor_id=user_id,
                    action=f"{request.method} {request.url.path}",
                    resource_type=request.url.path,
                    detail={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": status_code,
                        "duration_ms": (datetime.now(UTC) - start_time).total_seconds() * 1000,
                    },
                    outcome="success" if status_code < 400 else "failure",
                )
            except Exception as log_exc:
                logger.warning("AuditMiddleware: Failed to log audit entry: %s", log_exc)

        return response

    async def _log_audit_entry(
        self,
        tenant_id: str | None,
        actor_id: str | None,
        action: str,
        resource_type: str,
        detail: dict,
        outcome: str,
    ) -> None:
        async with get_unit_of_work() as uow:
            repo = AuditLogRepository()
            log_entry = AuditLog(
                id=str(ObjectId()),
                tenant_id=tenant_id or "unknown",
                actor_id=actor_id or "anonymous",
                action=action,
                resource_type=resource_type,
                details=detail,
                outcome=outcome,
                ip_address="",
                user_agent="",
            )
            await repo.create(log_entry)
