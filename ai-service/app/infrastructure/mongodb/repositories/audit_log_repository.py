from typing import Optional, Any

from app.domain.auth.entities.audit_log import AuditLog
from app.domain.auth.repositories.audit_log_repository import AuditLogRepository as IAuditLogRepository
from app.infrastructure.mongodb.collections import get_audit_logs_collection
from app.infrastructure.mongodb.documents.audit_log_document import AuditLogDocument
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository


class AuditLogRepository(BaseMongoRepository[AuditLogDocument, AuditLog], IAuditLogRepository):
    """MongoDB implementation of the audit log repository."""

    def __init__(self):
        super().__init__(get_audit_logs_collection(), AuditLogDocument)

    async def create(self, entity: AuditLog, session: Any = None) -> AuditLog:
        return await super().create(entity, session=session)

    async def find_by_tenant_id(
        self, tenant_id: str, limit: int = 50, skip: int = 0
    ) -> list[AuditLog]:
        return await self.find_many({"tenant_id": tenant_id}, limit=limit, skip=skip)

    async def find_by_actor_id(
        self, actor_id: str, limit: int = 50, skip: int = 0
    ) -> list[AuditLog]:
        return await self.find_many({"actor_id": actor_id}, limit=limit, skip=skip)

    async def find_by_resource(
        self, resource_type: str, resource_id: str, limit: int = 50, skip: int = 0
    ) -> list[AuditLog]:
        return await self.find_many(
            {"resource_type": resource_type, "resource_id": resource_id},
            limit=limit,
            skip=skip,
        )
