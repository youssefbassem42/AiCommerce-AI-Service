from datetime import datetime, UTC
from typing import Optional

from pydantic import Field

from app.shared.kernel.entity import Entity


class ApiKey(Entity[str]):
    """Domain entity representing an API key for tenant authentication."""

    key_hash: str = Field(..., description="Bcrypt hash of the raw API key")
    key_prefix: str = Field(..., description="First few characters for identification")
    name: str = Field(..., description="Friendly name for the API key")
    store_id: str = Field(..., description="Tenant/store context ID")
    scopes: list[str] = Field(default_factory=list, description="Permission scopes")
    is_active: bool = Field(default=True, description="Whether the key is active")
    expires_at: Optional[datetime] = Field(default=None, description="Key expiration timestamp")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: Optional[datetime] = Field(default=None)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    def has_scope(self, required_scope: str) -> bool:
        return required_scope in self.scopes or "*" in self.scopes
