from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ApiKeyCreateRequest(BaseModel):
    store_id: str
    name: str
    scopes: list[str] = []
    expires_at: Optional[datetime] = None


class ApiKeyResponse(BaseModel):
    key_prefix: str
    name: str
    scopes: list[str]
    is_active: bool
    expires_at: Optional[datetime] = None
    created_at: datetime


class ApiKeyListResponse(BaseModel):
    api_keys: list[ApiKeyResponse]


class AuditLogResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    action: str
    resource: str
    outcome: str
    timestamp: datetime
