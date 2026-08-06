"""Strongly typed authenticated user reconstructed from the .NET JWT claims (contract §8)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AuthenticatedUser(BaseModel):
    """Identity reconstructed from validated JWT claims.

    Claim mapping (contract section 8):
    - user_id          <- `sub` (or `nameid`)
    - email            <- `email`
    - role             <- ASP.NET role URI claim, normalized (Admin -> admin, SuperAdmin -> super_admin)
    - store_id         <- `store_id` (optional GUID)
    - organization_id  <- `org_id` (optional GUID)
    - permissions      <- repeatable `permission` claims
    """

    user_id: uuid.UUID
    email: str | None = Field(default=None)
    role: str = Field(default="")
    roles: list[str] = Field(default_factory=list)
    security_stamp: str | None = Field(default=None)
    jti: str | None = Field(default=None)
    store_id: uuid.UUID | None = Field(default=None)
    organization_id: uuid.UUID | None = Field(default=None)
    permissions: list[str] = Field(default_factory=list)
    issued_at: datetime | None = Field(default=None)
    expires_at: datetime | None = Field(default=None)

    @property
    def is_super_admin(self) -> bool:
        return self.role == "super_admin" or "super_admin" in self.roles

    @property
    def has_store(self) -> bool:
        return self.store_id is not None

    @property
    def has_organization(self) -> bool:
        return self.organization_id is not None
