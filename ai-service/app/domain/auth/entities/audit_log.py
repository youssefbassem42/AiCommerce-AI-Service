from datetime import datetime, UTC
from typing import Optional, Any

from pydantic import Field

from app.shared.kernel.entity import Entity


class AuditLog(Entity[str]):
    """Domain entity representing an audit log entry."""

    action: str = Field(..., description="Action performed")
    actor_id: Optional[str] = Field(default=None, description="Who performed the action")
    actor_type: str = Field(default="user", description="Type of actor (user, system, api_key)")
    resource_type: str = Field(..., description="Type of resource affected")
    resource_id: Optional[str] = Field(default=None, description="ID of the resource affected")
    tenant_id: Optional[str] = Field(default=None, description="Tenant/store context ID")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional details")
    ip_address: Optional[str] = Field(default=None, description="Client IP address")
    user_agent: Optional[str] = Field(default=None, description="Client user agent")
    outcome: str = Field(default="success", description="Outcome: success or failure")
    failure_reason: Optional[str] = Field(default=None, description="Reason if outcome is failure")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
