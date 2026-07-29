from abc import ABC, abstractmethod
from typing import Optional

from app.domain.auth.entities.audit_log import AuditLog
from app.shared.kernel.repository import AsyncRepository


class AuditLogRepository(AsyncRepository[AuditLog, str], ABC):
    """Domain repository interface for audit logs."""

    @abstractmethod
    async def find_by_tenant_id(
        self, tenant_id: str, limit: int = 50, skip: int = 0
    ) -> list[AuditLog]:
        """Find audit log entries for a tenant."""

    @abstractmethod
    async def find_by_actor_id(
        self, actor_id: str, limit: int = 50, skip: int = 0
    ) -> list[AuditLog]:
        """Find audit log entries by actor."""

    @abstractmethod
    async def find_by_resource(
        self, resource_type: str, resource_id: str, limit: int = 50, skip: int = 0
    ) -> list[AuditLog]:
        """Find audit log entries by resource."""
