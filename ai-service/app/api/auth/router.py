from fastapi import APIRouter, Depends

from app.api.auth.dependencies import get_audit_log_repository, require_super_admin_role
from app.api.auth.schemas import AuditLogResponse
from app.infrastructure.mongodb.repositories.audit_log_repository import AuditLogRepository

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.get("/audit-logs", response_model=list[AuditLogResponse], dependencies=[Depends(require_super_admin_role)])
async def list_audit_logs(
    skip: int = 0,
    limit: int = 50,
    repo: AuditLogRepository = Depends(get_audit_log_repository),
) -> list[AuditLogResponse]:
    logs = await repo.find_many({}, limit=limit, skip=skip, descending=True)
    return [
        AuditLogResponse(
            id=log.id,
            store_id=log.store_id or "",
            user_id=log.actor_id or "",
            action=log.action,
            resource=log.resource_type,
            outcome=log.outcome,
            timestamp=log.timestamp,
        )
        for log in logs
    ]
