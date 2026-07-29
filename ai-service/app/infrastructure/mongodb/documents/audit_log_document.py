from datetime import datetime
from typing import Optional, Any

from pydantic import Field

from app.domain.auth.entities.audit_log import AuditLog
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class AuditLogDocument(BaseMongoDocument):
    """MongoDB document model representing an AuditLog."""

    action: str = Field(..., index=True)
    actor_id: Optional[str] = Field(default=None, index=True)
    actor_type: str = Field(default="user")
    resource_type: str = Field(..., index=True)
    resource_id: Optional[str] = Field(default=None)
    tenant_id: Optional[str] = Field(default=None, index=True)
    details: dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = Field(default=None)
    user_agent: Optional[str] = Field(default=None)
    outcome: str = Field(default="success", index=True)
    failure_reason: Optional[str] = Field(default=None)
    timestamp: datetime = Field(default=..., index=True)
    updated_at: datetime = Field(default=...)

    def to_entity(self) -> AuditLog:
        return AuditLog(
            id=str(self.id),
            action=self.action,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            tenant_id=self.tenant_id,
            details=self.details,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            outcome=self.outcome,
            failure_reason=self.failure_reason,
            timestamp=self.timestamp,
            created_at=self.created_at,
        )

    @classmethod
    def from_entity(cls, entity: AuditLog) -> "AuditLogDocument":
        kwargs = {
            "action": entity.action,
            "actor_id": entity.actor_id,
            "actor_type": entity.actor_type,
            "resource_type": entity.resource_type,
            "resource_id": entity.resource_id,
            "tenant_id": entity.tenant_id,
            "details": entity.details,
            "ip_address": entity.ip_address,
            "user_agent": entity.user_agent,
            "outcome": entity.outcome,
            "failure_reason": entity.failure_reason,
            "timestamp": entity.timestamp,
            "created_at": entity.created_at,
            "updated_at": entity.created_at,
        }
        if entity.id:
            kwargs["_id"] = entity.id
        return cls(**kwargs)
